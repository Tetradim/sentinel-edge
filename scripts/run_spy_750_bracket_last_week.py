#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from run_spy_qqq_execution_validation import download_minute_bars,cents

START='2026-07-13'; END='2026-07-18'; HALF=.50; TRAIL=.0035; CHECK=200; ET=ZoneInfo('America/New_York')

def path_points(r,mode):
    o,h,l,c=map(float,(r.open,r.high,r.low,r.close)); up=c>=o
    if mode=='trend_path': return [o,l,h,c] if up else [o,h,l,c]
    return [o,h,l,c] if up else [o,l,h,c]

def run(bars,mode='trend_path',rebracket=True,cost_bps=0.0,fractional=True):
    cap=2000.; center=cents(float(bars.iloc[0].open)); gen=0; pos=None
    next_check=pd.Timestamp(bars.iloc[0].timestamp)+pd.Timedelta(seconds=CHECK)
    trades=[]; recenters=[]; eq=[cap]
    def levels(): return cents(center-HALF),cents(center+HALF)
    def qty(px):
        q=cap/px
        return q if fractional else math.floor(q)
    def open_pos(ts,px,day):
        nonlocal pos
        _,target=levels(); q=qty(px)
        if q>0: pos={'day':str(day),'entry_time':ts,'entry':px,'qty':q,'target':target,'peak':px,'trail':cents(px*(1-TRAIL)),'gen':gen}
    def close_pos(ts,px,reason):
        nonlocal pos,cap
        p=pos; gross=(px-p['entry'])*p['qty']; cost=(p['entry']+px)*p['qty']*cost_bps/10000; net=gross-cost; cap+=net
        trades.append({'day':p['day'],'entry_time':p['entry_time'].isoformat(),'exit_time':ts.isoformat(),'entry':p['entry'],'exit':px,'shares':p['qty'],'gross_pnl':gross,'cost':cost,'net_pnl':net,'reason':reason,'generation':p['gen'],'hold_seconds':int((ts-p['entry_time']).total_seconds())}); pos=None; eq.append(cap)
    prior_day=None
    for r in bars.itertuples(index=False):
        ts=pd.Timestamp(r.timestamp); day=r.day
        if prior_day is not None and day!=prior_day:
            if pos: close_pos(ts,cents(float(r.open)),'overnight_defensive')
            next_check=ts+pd.Timedelta(seconds=CHECK)
        prior_day=day
        while ts>=next_check:
            if rebracket and pos is None:
                buy,sell=levels(); obs=cents(float(r.open))
                if obs<buy or obs>sell:
                    old=center; center=obs; gen+=1; buy,sell=levels(); recenters.append({'timestamp':ts.isoformat(),'old_midpoint':old,'new_midpoint':center,'buy':buy,'sell':sell,'generation':gen})
            next_check+=pd.Timedelta(seconds=CHECK)
        if mode=='close_only':
            px=cents(float(r.close)); buy,_=levels()
            if pos is None:
                if px<=buy: open_pos(ts,px,day)
            else:
                pos['peak']=max(pos['peak'],px); pos['trail']=max(pos['trail'],cents(pos['peak']*(1-TRAIL)))
                if px>=pos['target']: close_pos(ts,px,'target_sampled')
                elif px<=pos['trail']: close_pos(ts,px,'trailing_stop_sampled')
        else:
            pts=path_points(r,mode)
            for a,b in zip(pts,pts[1:]):
                if a==b: continue
                rising=b>a
                if pos is None:
                    buy,_=levels()
                    if not rising and b<=buy<=a: open_pos(ts,buy,day)
                if pos is not None:
                    if rising:
                        if a<=pos['target']<=b: close_pos(ts,pos['target'],'target')
                        else:
                            pos['peak']=max(pos['peak'],b); pos['trail']=max(pos['trail'],cents(pos['peak']*(1-TRAIL)))
                    else:
                        if b<=pos['trail']<=a: close_pos(ts,pos['trail'],'trailing_stop')
        local=ts.tz_convert(ET)
        if local.hour*60+local.minute>=15*60+55 and pos: close_pos(ts,cents(float(r.close)),'end_of_day')
    if pos:
        r=bars.iloc[-1]; close_pos(pd.Timestamp(r.timestamp),cents(float(r.close)),'period_end')
    w=[x['net_pnl'] for x in trades if x['net_pnl']>0]; l=[x['net_pnl'] for x in trades if x['net_pnl']<0]
    peak=eq[0]; dd=0
    for x in eq: peak=max(peak,x); dd=max(dd,peak-x)
    return {'model':mode,'rebracket':rebracket,'cost_bps':cost_bps,'fractional':fractional,'start_capital':2000.,'final_capital':cap,'net_pnl':cap-2000.,'return_pct':100*(cap/2000-1),'trades':len(trades),'wins':len(w),'losses':len(l),'win_rate':100*len(w)/len(trades) if trades else 0,'profit_factor':sum(w)/abs(sum(l)) if l else (999 if w else 0),'recenters':len(recenters),'max_drawdown_dollars':dd,'avg_trade':np.mean([x['net_pnl'] for x in trades]) if trades else 0},trades,recenters

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=Path('artifacts/spy-750-bracket-last-week')); a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    bars=download_minute_bars('SPY',START,END)
    if bars.empty: raise SystemExit('no bars')
    rows=[]; all_t=[]; all_r=[]
    for mode in ('trend_path','reverse_path','close_only'):
      for rb in (True,False):
       for bps in (0.,1.,2.,5.,10.):
        for frac in (True,False):
         s,t,r=run(bars,mode,rb,bps,frac); rows.append(s); key=f'{mode}|rb={rb}|bps={bps}|frac={frac}'
         all_t.extend([{**x,'profile':key} for x in t]); all_r.extend([{**x,'profile':key} for x in r])
    pd.DataFrame(rows).to_csv(a.output/'summary.csv',index=False); pd.DataFrame(all_t).to_csv(a.output/'trades.csv',index=False); pd.DataFrame(all_r).to_csv(a.output/'recenters.csv',index=False); bars.to_csv(a.output/'spy-minute-bars.csv.gz',index=False,compression='gzip')
    df=pd.DataFrame(rows); primary=df[(df.model=='trend_path')&(df.rebracket)&(df.cost_bps==0)&(df.fractional)].iloc[0].to_dict()
    report={'period':{'start':START,'end_exclusive':END},'coverage':{'bars':len(bars),'sessions':int(bars.day.nunique())},'settings':{'edge':False,'starting_capital':2000,'half_width':.5,'buy':'midpoint - 0.50','sell':'midpoint + 0.50','target_distance':1.0,'trailing_stop_active_at_entry':True,'trailing_stop_pct':.35,'rebracket_check_seconds':200,'rebracket_rule':'flat only; recenter to observed price if outside existing zone','eod_exit':'15:55 ET','profit_reuse':'all realized P&L'},'primary':primary,'zero_cost_fractional':df[(df.cost_bps==0)&(df.fractional)].to_dict('records'),'limitations':['one-minute OHLC cannot reveal exact tick ordering','200-second checks use first minute observation at or after the boundary','path models fill exactly at configured thresholds','close-only is delayed execution stress']}
    (a.output/'latest.json').write_text(json.dumps(report,indent=2,default=str)); print(json.dumps(report,indent=2,default=str))
if __name__=='__main__': main()
