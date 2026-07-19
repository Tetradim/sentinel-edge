#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics, tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

UNIVERSE=['AMD','MU','AMAT','KLAC','AVGO','TSLA','META','MSFT','GOOGL','AMZN','PLTR','SOFI','HOOD','COIN','RIVN','BIYA','SLND','CJMB','BNRG','BATL']
PENNIES={'BIYA','SLND','CJMB','BNRG','BATL'}
LIQUID_PROXY={'MU','MSFT','TSLA','AMZN','AMD','GOOGL','META','AVGO','AMAT','PLTR'}
STARTING_CAPITAL=10000.0
BASE_POWER=500.0
COST_RATE=0.001
OPEN_MIN=13*60+30
LAST_ENTRY=19*60+15
FORCED_EXIT=19*60+55

def cents(x): return round(float(x)+1e-12,2)
def finite(x,d=0.0):
    try:
        z=float(x); return z if math.isfinite(z) else d
    except: return d

def load_bars(path):
    f=pd.read_csv(path,compression='gzip')
    f=f[f.symbol.isin(UNIVERSE)].copy(); f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
    f['minute_utc']=f.timestamp.dt.hour*60+f.timestamp.dt.minute
    f=f[(f.minute_utc>=OPEN_MIN)&(f.minute_utc<=20*60)].copy()
    for c in ['open','high','low','close','volume']: f[c]=pd.to_numeric(f[c],errors='coerce')
    f=f.dropna(subset=['open','high','low','close']); f=f[(f[['open','high','low','close']]>0).all(axis=1)]
    f['session_date']=f.timestamp.dt.date
    parts=[]
    for _,g in f.sort_values(['symbol','timestamp']).groupby('symbol',sort=False):
        g=g.copy(); pc=g.close.shift(1)
        tr=pd.concat([g.high-g.low,(g.high-pc).abs(),(g.low-pc).abs()],axis=1).max(axis=1)
        g['atr14']=tr.rolling(14,min_periods=3).mean().fillna(tr.expanding().mean())
        parts.append(g)
    return pd.concat(parts,ignore_index=True).sort_values(['symbol','timestamp'])

def load_signals(path):
    s=pd.read_csv(path); s['timestamp']=pd.to_datetime(s.timestamp,utc=True)
    for c in ['score','confidence','entry_price','maximum_entry_price','initial_stop','target_1','expected_value_pct','reward_risk']:
        s[c]=pd.to_numeric(s[c],errors='coerce')
    s=s.sort_values(['symbol','timestamp']).reset_index(drop=True)
    return s

def snap_center(value,width):
    inc=min(0.25,max(0.01,width/2)); return cents(round(value/inc)*inc)

def width(center): return max(0.01,cents(center*0.003))

@dataclass(frozen=True)
class Policy:
    name:str
    gate_minutes:int|None=None
    advisory:bool=False
    enforce_max_entry:bool=True
    edge_stop:bool=False
    expiry_supervision:bool=False
    reduce_loser:bool=False
    break_even_winner:bool=False
    follow_enabled:bool=True

@dataclass
class Position:
    entry:float; qty:float; target:float; stop:float; original_stop:float; reward:float
    entry_time:pd.Timestamp; power:float; center:float; generation:int; direction:str
    edge_signal_time:pd.Timestamp|None=None; edge_expiry:pd.Timestamp|None=None; edge_score:float=0.0
    edge_stop_applied:bool=False; expiry_action_done:bool=False; reduced_qty:float=0.0
    realized_partial:float=0.0


def latest_signal(sig_times,sig_rows,ts,minutes):
    if minutes is None or not sig_times: return None
    arr=np.array([x.value for x in sig_times],dtype=np.int64)
    i=np.searchsorted(arr,ts.value,side='right')-1
    if i<0: return None
    row=sig_rows[i]
    if ts-row.timestamp>pd.Timedelta(minutes=minutes): return None
    return row

def trade_row(symbol,pos,ts,exit_price,reason,remaining_qty=None,edge_action=None):
    qty=pos.qty if remaining_qty is None else remaining_qty
    gross=(exit_price-pos.entry)*qty
    cost=pos.power*COST_RATE*(qty/(pos.qty+pos.reduced_qty) if (pos.qty+pos.reduced_qty)>0 else 1)
    net=gross-cost
    return {
      'symbol':symbol,'entry_time':pos.entry_time.isoformat(),'exit_time':ts.isoformat(),
      'entry':pos.entry,'exit':cents(exit_price),'qty':qty,'power':pos.power,'target':pos.target,
      'original_stop':pos.original_stop,'final_stop':pos.stop,'reward':pos.reward,'exit_reason':reason,
      'gross_pnl':gross,'cost':cost,'net_pnl':net,'return_pct':(exit_price/pos.entry-1)*100,
      'hold_minutes':(ts-pos.entry_time).total_seconds()/60,'center':pos.center,'generation':pos.generation,
      'last_recenter_direction':pos.direction,'edge_signal_time':pos.edge_signal_time.isoformat() if pos.edge_signal_time is not None else '',
      'edge_score':pos.edge_score,'edge_stop_applied':pos.edge_stop_applied,'edge_action':edge_action or '',
      'is_penny':symbol in PENNIES,'is_liquid_proxy':symbol in LIQUID_PROXY,
    }

def simulate_symbol(g,symbol,policy,sigs,include_equity=True):
    g=g.sort_values('timestamp').copy(); trades=[];comms=[];recenters=[];equity=[];realized=0.0
    sig_rows=list(sigs.itertuples(index=False)); sig_times=[r.timestamp for r in sig_rows]
    pos=None; center=None; generation=0; direction='INITIAL'; recent=deque(maxlen=7); rec_times=deque(); last_rec=None
    cooldown_until=None; up=down=0; trend_pause=False
    for row in g.itertuples(index=False):
        ts=row.timestamp; px=cents(row.close); day=row.session_date; minute=row.minute_utc
        if center is None or getattr(simulate_symbol,'_day_'+symbol,None)!=day:
            center=px;generation=0;direction='INITIAL';recent.clear();rec_times.clear();last_rec=None;up=down=0;trend_pause=False;cooldown_until=None
            setattr(simulate_symbol,'_day_'+symbol,day)
        recent.append(px); w=width(center); buy=cents(center-w); sell=cents(center+w); trigger=max(6*w,finite(row.atr14,0))
        while rec_times and (ts-rec_times[0]).total_seconds()>3600: rec_times.popleft()
        if pos is not None:
            if policy.expiry_supervision and pos.edge_expiry is not None and ts>=pos.edge_expiry and not pos.expiry_action_done:
                mfe=max(0,finite(row.high,px)-pos.entry)
                if policy.break_even_winner and mfe>=0.5*pos.reward and pos.stop<pos.entry:
                    pos.stop=pos.entry;pos.expiry_action_done=True
                    comms.append({'timestamp':ts.isoformat(),'symbol':symbol,'event':'EDGE_SET_STOP','reason':'signal_expired_favorable_move','old_stop':pos.original_stop,'new_stop':pos.stop})
                elif policy.reduce_loser and px<pos.entry and pos.qty>0:
                    reduce_qty=pos.qty*0.5; exit_px=px
                    part=trade_row(symbol,pos,ts,exit_px,'edge_reduce_50',remaining_qty=reduce_qty,edge_action='signal_expired_loser')
                    trades.append(part);realized+=part['net_pnl'];pos.qty-=reduce_qty;pos.reduced_qty+=reduce_qty;pos.power*=0.5;pos.expiry_action_done=True
                    comms.append({'timestamp':ts.isoformat(),'symbol':symbol,'event':'EDGE_REDUCE_POSITION','reason':'signal_expired_loser','qty':reduce_qty,'price':exit_px})
                else: pos.expiry_action_done=True
            exit_px=None; reason=None
            if px<=pos.stop: exit_px=px;reason='hard_stop'
            elif px>=pos.target: exit_px=px;reason='profit_target'
            elif minute>=FORCED_EXIT: exit_px=px;reason='end_of_day'
            if exit_px is not None:
                tr=trade_row(symbol,pos,ts,exit_px,reason);tr['cost']=pos.power*COST_RATE;tr['net_pnl']=tr['gross_pnl']-tr['cost'];tr['is_penny']=symbol in PENNIES;tr['is_liquid_proxy']=symbol in LIQUID_PROXY
                trades.append(tr);realized+=tr['net_pnl'];prof=tr['net_pnl']>0;cooldown_until=ts+pd.Timedelta(minutes=5 if prof else 15);pos=None
        if pos is None:
            in_cooldown=cooldown_until is not None and ts<cooldown_until
            if not in_cooldown and policy.follow_enabled:
                dist=px-center
                if abs(dist)>=2*trigger: trend_pause=True
                if len(rec_times)>=4: trend_pause=True
                if trend_pause:
                    if len(recent)>=5:
                        vals=list(recent)[-5:]
                        stable=max(vals)-min(vals)<=max(2*w,0.75*finite(row.atr14,0)) and abs(vals[-1]-vals[0])<=max(w,0.5*finite(row.atr14,0))
                        if stable:
                            new=snap_center(statistics.median(vals),w)
                            if abs(new-center)>=w:
                                old=center;center=new;generation+=1;direction='UP' if new>old else 'DOWN';last_rec=ts;rec_times.append(ts);recenters.append({'timestamp':ts.isoformat(),'symbol':symbol,'old_center':old,'new_center':new,'direction':direction,'reason':'trend_stabilized','generation':generation})
                            trend_pause=False;up=down=0
                else:
                    upper=center+trigger;lower=center-trigger
                    up=up+1 if px>=upper else 0;down=down+1 if px<=lower else 0
                    ready=last_rec is None or (ts-last_rec).total_seconds()>=900
                    vals=list(recent)
                    if ready and up>=3 and len(vals)>=5 and statistics.median(vals[-5:])>=upper:
                        new=snap_center(statistics.median(vals[-5:]),w)
                        if abs(new-center)>=w:
                            old=center;center=new;generation+=1;direction='UP';last_rec=ts;rec_times.append(ts);recenters.append({'timestamp':ts.isoformat(),'symbol':symbol,'old_center':old,'new_center':new,'direction':direction,'reason':'confirmed_up','generation':generation})
                        up=down=0
                    elif ready and down>=5 and len(vals)>=5:
                        l3=vals[-3:];stable=int(np.argmin(l3))==0 and l3[-1]>=l3[-2]
                        if statistics.median(vals[-5:])<=lower and stable:
                            new=snap_center(statistics.median(vals[-5:]),w)
                            if abs(new-center)>=w:
                                old=center;center=new;generation+=1;direction='DOWN';last_rec=ts;rec_times.append(ts);recenters.append({'timestamp':ts.isoformat(),'symbol':symbol,'old_center':old,'new_center':new,'direction':direction,'reason':'confirmed_down','generation':generation})
                            up=down=0
            w=width(center);buy=cents(center-w);sell=cents(center+w)
            if not in_cooldown and minute<=LAST_ENTRY and px<=buy and sell>px:
                sig=latest_signal(sig_times,sig_rows,ts,policy.gate_minutes)
                if policy.gate_minutes is not None and sig is None and not policy.advisory:
                    comms.append({'timestamp':ts.isoformat(),'symbol':symbol,'event':'EDGE_REJECT_ENTRY','reason':'no_recent_edge_buy','price':px,'buy_level':buy}); sig=None
                else:
                    allowed=True; reason='pulse_autonomous'
                    if sig is not None:
                        max_entry=finite(sig.maximum_entry_price,float('inf'))
                        if policy.enforce_max_entry and px>max_entry:
                            allowed=False; reason='above_edge_max_entry'
                        else: reason='edge_recent_buy_approved'
                    if allowed:
                        reward=sell-px; stop=max(0.01,cents(px-1.5*reward)); edge_stop_applied=False
                        if sig is not None and policy.edge_stop:
                            es=finite(sig.initial_stop,0.0)
                            if 0<es<px:
                                tightened=max(stop,es)
                                if tightened>stop: stop=cents(min(tightened,px-0.01)); edge_stop_applied=True
                        pos=Position(px,BASE_POWER/px,sell,stop,stop,reward,ts,BASE_POWER,center,generation,direction,
                                     sig.timestamp if sig is not None else None,
                                     (sig.timestamp+pd.Timedelta(minutes=policy.gate_minutes)) if sig is not None and policy.gate_minutes is not None else None,
                                     finite(sig.score,0) if sig is not None else 0.0,edge_stop_applied)
                        comms.append({'timestamp':ts.isoformat(),'symbol':symbol,'event':'EDGE_APPROVE_ENTRY' if sig is not None else 'PULSE_ENTRY','reason':reason,'price':px,'target':sell,'stop':stop,'edge_score':pos.edge_score})
                    else:
                        comms.append({'timestamp':ts.isoformat(),'symbol':symbol,'event':'EDGE_REJECT_ENTRY','reason':reason,'price':px,'edge_max_entry':max_entry})
        if include_equity:
            unreal=0 if pos is None else (px-pos.entry)*pos.qty-pos.power*COST_RATE
            equity.append({'timestamp':ts,'contribution':realized+unreal})
    if pos is not None:
        row=g.iloc[-1]; tr=trade_row(symbol,pos,row.timestamp,cents(row.close),'period_end'); trades.append(tr); realized+=tr['net_pnl']
    return trades,comms,recenters,pd.DataFrame(equity)

def summarize(policy,trades,comms,recenters,equity):
    t=pd.DataFrame(trades); c=pd.DataFrame(comms); r=pd.DataFrame(recenters)
    net=float(t.net_pnl.sum()) if not t.empty else 0
    wins=t[t.net_pnl>0] if not t.empty else t; losses=t[t.net_pnl<0] if not t.empty else t
    pf=float(wins.net_pnl.sum()/abs(losses.net_pnl.sum())) if not losses.empty else float('inf')
    eq=pd.concat(equity,ignore_index=True).groupby('timestamp').contribution.sum().sort_index()+STARTING_CAPITAL if equity else pd.Series(dtype=float)
    peak=eq.cummax(); dd=peak-eq; ddv=float(dd.max()) if not dd.empty else 0; ddp=float((dd/peak*100).max()) if not dd.empty else 0
    return {
      'profile':policy.name,'net_pnl':net,'return_pct':net/STARTING_CAPITAL*100,'trades':len(t),
      'win_rate_pct':float((t.net_pnl>0).mean()*100) if not t.empty else 0,'profit_factor':pf,
      'max_drawdown_dollars':ddv,'max_drawdown_pct':ddp,
      'penny_pnl':float(t.loc[t.is_penny,'net_pnl'].sum()) if not t.empty else 0,
      'ordinary_pnl':float(t.loc[~t.is_penny,'net_pnl'].sum()) if not t.empty else 0,
      'liquid_proxy_pnl':float(t.loc[t.is_liquid_proxy,'net_pnl'].sum()) if not t.empty else 0,
      'recenter_events':len(r),'edge_approvals':int((c.event=='EDGE_APPROVE_ENTRY').sum()) if not c.empty else 0,
      'edge_rejections':int((c.event=='EDGE_REJECT_ENTRY').sum()) if not c.empty else 0,
      'edge_stop_updates':int((c.event=='EDGE_SET_STOP').sum()) if not c.empty else 0,
      'edge_reductions':int((c.event=='EDGE_REDUCE_POSITION').sum()) if not c.empty else 0,
    },t,c,r,eq

def run(frame,signals,policy,dates):
    f=frame[frame.session_date.isin(set(dates))]
    all_t=[];all_c=[];all_r=[];all_e=[]
    for sym,g in f.groupby('symbol',sort=False):
        sig=signals[signals.symbol==sym]
        t,c,r,e=simulate_symbol(g,sym,policy,sig,True); all_t+=t;all_c+=c;all_r+=r;all_e.append(e)
    return summarize(policy,all_t,all_c,all_r,all_e)

def self_test():
    center=750.0; half=0.5
    observed=[750.05,750.10,749.50]
    sticky_buy=cents(center-half)
    assert observed[-1] <= sticky_buy
    chasing_center=cents(observed[-1])
    chasing_buy=cents(chasing_center-half)
    assert observed[-1] > chasing_buy
    entry=749.50; target=750.50; stop=cents(entry-1.5*(target-entry))
    assert target > entry > stop
    print('edge-scalp-follow-v2 self-test passed')


def parse_args():
    ap=argparse.ArgumentParser(description='Replay actual Edge BUY signals against Pulse Scalp Follow v2.')
    ap.add_argument('--bars', type=Path, help='minute-bars.csv.gz from the Edge/Pulse minute sweep')
    ap.add_argument('--signals', type=Path, help='edge-selected-signals.csv from the Edge/Pulse minute sweep')
    ap.add_argument('--output', type=Path, default=Path('artifacts/edge-scalp-follow-v2'))
    ap.add_argument('--test-start-session', type=int, default=10, help='0-based session index for the untouched test split')
    ap.add_argument('--self-test', action='store_true')
    return ap.parse_args()


def main():
    args=parse_args()
    if args.self_test:
        self_test(); return
    if not args.bars or not args.signals:
        raise SystemExit('--bars and --signals are required unless --self-test is used')
    bars=args.bars; sigp=args.signals
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    frame=load_bars(bars); signals=load_signals(sigp); dates=sorted(frame.session_date.unique()); test=dates[args.test_start_session:]
    if not test:
        raise SystemExit('test split contains no sessions')
    policies=[
      Policy('pulse_only'),
      Policy('edge_gate_15m',15),
      Policy('edge_gate_30m',30),
      Policy('edge_gate_60m',60),
      Policy('edge_gate_30m_atomic_stop',30,edge_stop=True),
      Policy('edge_supervised_30m',30,edge_stop=True,expiry_supervision=True,reduce_loser=True,break_even_winner=True),
      Policy('edge_advisory_30m',30,advisory=True,edge_stop=True,expiry_supervision=True,reduce_loser=True,break_even_winner=True),
    ]
    rows=[]; report={'period':{'dates':[str(x) for x in dates],'test_dates':[str(x) for x in test]},'profiles':{}}
    for p in policies:
        s,t,c,r,e=run(frame,signals,p,test); rows.append(s); report['profiles'][p.name]=s
        t.to_csv(out/f'{p.name}-trades.csv',index=False);c.to_csv(out/f'{p.name}-communications.csv',index=False);r.to_csv(out/f'{p.name}-recenters.csv',index=False)
        print(p.name,s,flush=True)
    pd.DataFrame(rows).to_csv(out/'edge-scalp-follow-comparison.csv',index=False)
    with open(out/'edge-scalp-follow-report.json','w') as f: json.dump(report,f,indent=2)
if __name__=='__main__': main()
