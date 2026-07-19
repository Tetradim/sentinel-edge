# Continuous bracket replay — non-penny summary

Tested 15 symbols: AMD, MU, AMAT, KLAC, AVGO, TSLA, META, MSFT, GOOGL, AMZN, PLTR, SOFI, HOOD, COIN, and RIVN. BIYA, SLND, CJMB, BNRG, and BATL were excluded.

Scope: 19 sessions; $2,000 starting power per ticker; Pulse positive-profit compounding plus fixed-power controls; Pulse-only and actual 30-minute Edge BUY authorization; dollar gaps from $0.01 to $1.00; percentage gaps from 0.01% to 0.50%; re-bracket on/off; no trailing, delayed trailing, and trailing active at entry; 0, 1, 2, 5, and 10 basis-point round-trip cost cases.

The exact-threshold model credits target and stop fills at configured prices after a one-minute close crosses them. A separate sampled-close model stresses delayed stop execution. Neither model can count multiple oscillations within one minute.

Key results:

- A universal $0.01 target did not work on this higher-priced universe. Pulse with re-bracket on returned -0.11% even at zero cost. A cent is only about 0.058% to 0.001% of these symbols' prices.
- The best full-month Pulse profile was 0.30%, re-bracket on, trailing active at entry: +$5,756.16 on $30,000, or +19.19%, under ideal threshold fills.
- The matching fixed-power result was +$4,557.05, or +15.19%.
- The best fixed-dollar Pulse profile was $1.00, re-bracket on, trailing active at entry: +$4,421.79, or +14.74%.
- The first-10-session-selected 0.30% Pulse profile returned +$2,186.41, or +7.29%, on the untouched final nine sessions at zero cost; +4.86% at 1 bp. A 0.50% profile returned +2.45% at 2 bps.
- No sufficiently active profile remained profitable at 5 or 10 bps.
- Edge authorization reduced activity sharply. Its best full-month percentage profile returned +0.45% at zero cost; the untouched test returned +0.12%. Edge should remain an optional low-frequency gate, not replace Pulse.
- Re-bracketing helped only when paired with tight trailing risk. No trailing was negative; trailing active at entry was strongest.
- The sampled-close stress model turned the strongest exact-threshold profile negative, so quote, tick, or second-level validation is required before live use.

No live settings or orders were changed.
