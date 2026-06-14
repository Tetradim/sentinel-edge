# Sentinel Edge — Production Trading System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18+-blue?logo=react" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.115-blue?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/TypeScript-5-blue?logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

**Sentinel Edge** is a comprehensive, production-grade algorithmic trading system with real-time market data ingestion, multi-provider price feeds, backtesting engines, Monte Carlo risk simulation, strategy optimization, and automated decision-making capabilities.

This repository implements a complete trading pipeline from market data → signal generation → risk management → order execution with extensive safeguards, observability, and a modern React control interface.

---

## 🔗 Sentinel Pulse Integration

Sentinel Edge works in tandem with **Sentinel Pulse**, the execution worker that handles brokerage data streams and order execution. Edge analyzes market data, detects patterns, generates signals, and instructs Pulse on what to buy or sell. This creates a **bidirectional feedback loop** where Pulse reports back on order fills and position updates, enabling Edge to make risk-aware decisions with real position data.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SENTINEL PULSE ↔ EDGE INTEGRATION                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                           ┌─────────────────────────┐     │
│   │   PULSE     │                           │        EDGE             │     │
│   │ (Executor)  │                           │   (Brain / Analyzer)    │     │
│   └──────┬──────┘                           └───────────┬─────────────┘     │
│          │                                            │                    │
│          │  ORDER_FILLED (MongoDB)                     │                    │
│          │  POSITION_UPDATE ──────────────────────────►│                    │
│          │  ACCOUNT_UPDATE ──────────────────────────►│                    │
│          │                                            │                    │
│          │                                            │  BUY/SELL/STOP     │
│          │◄───────────────────────────────────────────┤  (REST API)         │
│          │         SIGNAL + DECISION                  │                    │
│          │                                            │                    │
│   ┌──────▼──────┐                           ┌──────────▼─────────────┐     │
│   │  Brokerage  │                           │  Market Data Providers │     │
│   │  (Orders)   │                           │  (Polygon, Finnhub)    │     │
│   └─────────────┘                           └─────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Communication Methods

| Direction | Method | Purpose |
|-----------|--------|---------|
| Edge → Pulse | REST API (`/api/tickers/{symbol}/decision`) | Send buy/sell/stop decisions |
| Edge → Pulse | REST API (`/control/override`) | Emergency stops, trailing stop management |
| Pulse → Edge | MongoDB Change Stream (`commands` collection) | Order fills, position updates, account state |
| (Optional) | WebSocket (`/ws/analyst`) | Real-time event streaming |

### Command Types (Shared Schema)

The `backend/shared/commands.py` module defines the contract for all Pulse ↔ Edge communication using Pydantic models:

#### Pulse → Edge Commands (Feedback Loop)

| Command | Description | Fields |
|---------|-------------|--------|
| `ORDER_FILLED` | Reports when an order is executed | `symbol`, `order_id`, `fill_price`, `quantity`, `side`, `pnl_realized`, `fees` |
| `POSITION_UPDATE` | Real-time position & PnL sync | `symbol`, `position_size`, `entry_price`, `current_pnl_pct`, `current_pnl_dollar`, `market_value` |
| `ACCOUNT_UPDATE` | Account-level updates | `symbol`, `buying_power`, `total_equity`, `day_pnl_pct`, `day_pnl_dollar` |
| `ORDER_REJECTED` | Order rejection handling | `symbol`, `order_id`, `reason` |
| `ORDER_CANCELLED` | Order cancellation tracking | `symbol`, `order_id`, `reason` |

#### Edge → Pulse Commands

| Command | Description | Fields |
|---------|-------------|--------|
| `SIGNAL_UPDATE` | Trading signal with action | `symbol`, `signal_score`, `action`, `confidence`, `reason` |
| `CORRELATION_ALERT` | Market breadth warnings | `symbol`, `correlated_symbols`, `cluster_strength`, `recommended_action` |
| `EMERGENCY_EXIT` | Immediate position closure | `symbol`, `reason` |

### Key Files

| File | Purpose |
|------|---------|
| `backend/shared/commands.py` | Pydantic models for all command types with `command_from_dict()` helper |
| `backend/shared/commands_utils.py` | Command builders, serializers, and validation utilities |
| `backend/pulse_client.py` | Edge's HTTP client with circuit breaker pattern + retry queue |
| `backend/analyst/core.py` | SentinelEdge orchestrator with Change Stream listener |
| `backend/engine.py` | DecisionEngine with async methods for Pulse feedback |
| `backend/scheduler.py` | Evaluation loop using real position data from DecisionEngine |
| `backend/services/pulse_service.py` | High-level service abstraction for Edge ↔ Pulse communication |
| `backend/services/pulse_types.ts` | TypeScript types mirroring Python command models |
| `backend/shared/observations.py` | Pydantic models for real-time observations with scoring |

### Observation Feedback Loop

The observation system provides real-time feedback that weights into signal scoring:

**Schema Validation:**
All observations are validated via Pydantic models before processing:
- `PatternObservation` - Pattern detections (ORB, momentum, etc.)
- `ExecutionObservation` - Order fills, rejections, position updates
- `RiskObservation` - Risk limit triggers, correlation alerts
- `HealthObservation` - System health status

**Scoring Weights:**
```python
# Source weights
pulse_weight: 1.0      # Trust Pulse execution observations
edge_weight: 1.0       # Trust Edge pattern observations
external_weight: 0.5   # External needs more validation

# Confidence multipliers
high_confidence_multiplier: 1.25  # >0.8 confidence gets bonus
min_confidence_threshold: 0.3

# Timeframe alignment
timeframe_match_bonus: 0.2    # Observation timeframe matches eval
max_timeframe_diff_seconds: 60  # Max allowed desync
```

**Desync Handling:**
- `ObservationDesyncMonitor` tracks drift between observation time and eval time
- If drift > 60s: warning logged
- If drift > 120s: severity = HIGH
- Old observations (5+ min) are excluded from scoring

**Usage in DecisionEngine:**
```python
# Add observation from Pulse feedback
decision_engine.add_observation(execution_observation)

# Get impact for scoring
impact = decision_engine.get_observation_impact("NVDA")

# Apply to signal strength
adjusted_signal = decision_engine.apply_observation_adjustment(
    base_signal, "NVDA"
)
```

The `PulseService` in `backend/services/pulse_service.py` provides a high-level abstraction:

```python
from services.pulse_service import PulseService, get_pulse_service

# Send a buy signal
await pulse_service.send_buy_signal(
    symbol="NVDA",
    signal_score=8.5,
    confidence=0.8,
    reason="Strong momentum + ORB breakout"
)

# Get real position from DecisionEngine
position = await pulse_service.get_real_position("NVDA")

# Emergency exit
await pulse_service.emergency_exit("NVDA", "Drawdown exceeded threshold")
```

### API Endpoints for Pulse Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/pulse/health` | Pulse connection health status |
| GET | `/api/pulse/status` | Pulse availability and circuit state |
| GET | `/api/pulse/positions` | All positions from DecisionEngine |
| GET | `/api/pulse/positions/{symbol}` | Single position from DecisionEngine |
| GET | `/api/pulse/queue` | Retry queue status |
| GET | `/api/pulse/account` | Account status from Pulse |
| POST | `/api/pulse/emergency-exit/{symbol}` | Trigger emergency exit |
| POST | `/api/pulse/trailing-stop/{symbol}` | Enable trailing stop |

Edge listens to the `commands` collection in MongoDB using Change Streams, which provides real-time detection of new documents without polling:

```python
# backend/analyst/core.py - _watch_pulse_commands()
pipeline = [{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
async with self.db.commands.watch(pipeline) as stream:
    async for change in stream:
        await self._handle_pulse_command(cmd_type, symbol, doc)
```

When Pulse inserts a command (like `ORDER_FILLED`), Edge:
1. **Detects** the change via MongoDB Change Stream (sub-second latency)
2. **Parses** the command using shared Pydantic models from `commands.py`
3. **Updates** DecisionEngine state (positions, trade history, PnL tracking)
4. **Logs** the event for observability and debugging

The handler supports both `insert` and `update` operations, extracting document data from either `fullDocument` (inserts) or `updateDescription.updatedFields` (updates).

### DecisionEngine Integration

The `DecisionEngine` in `backend/engine.py` maintains a real-time view of positions synced from Pulse. It has both async methods for Change Stream updates and sync methods for legacy compatibility:

```python
# Async methods for Change Stream processing
await self.decisions.record_trade_result(
    symbol="NVDA", fill_price=142.35, quantity=50, side="BUY", realized_pnl=0.0
)

await self.decisions.update_position_state_simple(
    symbol="NVDA", position_size=50, pnl_pct=2.5, pnl_dollar=125.0
)

# Query current position state
position = self.decisions.get_position("NVDA")
has_position = position is not None
pnl_pct = position.get("current_pnl_pct", 0.0) if position else 0.0
```

The DecisionEngine tracks:
- **Per-symbol positions**: Current position size, entry price, entry time
- **Trade history**: All executed trades with timestamps, prices, PnL
- **Consecutive losses**: For risk-based buy throttling
- **Win rates**: Per-symbol performance metrics
- **Global kill switch**: Emergency trading halt

### Scheduler Integration

The evaluation scheduler in `backend/scheduler.py` uses real position data from the DecisionEngine rather than relying on local estimates:

```python
# Step 6: Get real position state from DecisionEngine (synced from Pulse)
position = self.decisions.get_position(symbol)
has_position = position is not None
pnl_pct = position.get("current_pnl_pct", 0.0) if position else 0.0
pnl_dollar = position.get("current_pnl_dollar", 0.0) if position else 0.0

# Step 7: Make decision with accurate position data
decision = self.decisions.decide(
    symbol=symbol,
    trend=trend,
    signal_strength=signal_strength,
    pnl=pnl_dollar,
    pnl_pct=pnl_pct,  # Real PnL from Pulse
    has_position=has_position,  # Real position state
    ...
)
```

This ensures risk guards (consecutive loss limits, drawdown protection) fire based on actual position state.

### Circuit Breaker & Retry Queue

The `pulse_client.py` implements a circuit breaker pattern for resilience:

- **CLOSED**: Normal operation, requests go through
- **OPEN**: Too many failures (≥5), requests are suppressed
- **HALF_OPEN**: After 60s, allows test requests to check recovery

Failed decisions are queued in `retry_queue.py` for retry when the circuit closes or Pulse becomes available again.

### Testing the Integration

Use the test endpoint to simulate Pulse commands:

```bash
curl -X POST http://localhost:8000/api/test/pulse-command \
  -H "Content-Type: application/json" \
  -d '{
    "command_type": "ORDER_FILLED",
    "symbol": "NVDA",
    "order_id": "test_001",
    "fill_price": 142.35,
    "quantity": 50,
    "side": "BUY"
  }'
```

Expected Edge logs:
```
📤 Test command inserted: ORDER_FILLED | NVDA
📍 Position sync from Pulse → NVDA | size=50 pnl%=0.00%
✅ Edge received ORDER_FILLED from Pulse → NVDA | fill=142.35 qty=50
Trade recorded: BUY 50 NVDA @ 142.35 | PnL: 0.0
```

---

## 📊 System Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              SENTINEL EDGE ARCHITECTURE                        │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                            FRONTEND (React)                              │  │
│  │   Dashboard │ Ticker Config │ Backtest Results │ Health Status          │  │
│  └──────────────────────────────────┬───────────────────────────────────────┘  │
│                                     │                                             │
│                                     ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         FASTAPI SERVER (backend/server.py)              │  │
│  │   REST Endpoints │ WebSocket │ Metrics │ Authentication                 │  │
│  └──────────────────────────────────┬───────────────────────────────────────┘  │
│                                     │                                             │
│          ┌──────────────────────────┼──────────────────────────┐               │
│          ▼                          ▼                          ▼               │
│  ┌─────────────┐           ┌─────────────────┐          ┌──────────────┐       │
│  │ Scheduler   │           │ Decision Engine │          │ Pulse Client│       │
│  │ (eval loop) │           │ (risk logic)    │          │ (HTTP+WS)   │       │
│  └──────┬──────┘           └────────┬────────┘          └──────┬───────┘       │
│         │                           │                        │               │
│         ▼                           │                        │               │
│  ┌─────────────┐                    │                        │               │
│  │ Position    │                    │                        │               │
│  │ Tracker     │◄───────────────────┘                        │               │
│  └─────────────┘                                             │               │
│         │                                                     │               │
│         │                    ┌────────────────────────────────┘               │
│         │                    │                                                 │
│         ▼                    ▼                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │                     MARKET DATA LAYER                                  │   │
│  │  Price Fetchers │ ORB │ ATR │ Signal Engine │ Correlation Engine       │   │
│  └────────────────────────────────┬───────────────────────────────────────┘   │
│                                   │                                           │
│         ┌──────────────────────────┼──────────────────────────┐              │
│         ▼                          ▼                          ▼              │
│  ┌─────────────┐          ┌─────────────┐           ┌──────────────┐        │
│  │ Polygon.io  │          │  Finnhub    │           │  (Fallback)  │        │
│  └─────────────┘          └─────────────┘           └──────────────┘        │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```
sentinel-edge/
├── backend/
│   ├── server.py                    # FastAPI main entry point + all REST endpoints
│   ├── engine.py                    # DecisionEngine with Pulse feedback loop
│   ├── scheduler.py                 # Evaluation scheduler with position awareness
│   ├── pulse_client.py             # Circuit breaker HTTP client for Pulse
│   ├── price_fetcher.py            # Multi-provider price aggregation
│   ├── position_tracker.py         # Local position state management
│   ├── retry_queue.py              # Priority queue for failed decisions
│   ├── signals.py                  # Signal scoring engine
│   ├── orb.py                       # Opening Range Breakout detection
│   ├── atr.py                       # Average True Range calculator
│   ├── metrics.py                  # Prometheus metrics exports
│   ├── state_persistence.py        # MongoDB state storage
│   ├── shared/
│   │   └── commands.py             # Pydantic models for Pulse ↔ Edge commands
│   ├── analyst/
│   │   ├── core.py                  # SentinelEdge orchestrator + Change Streams
│   │   ├── correlation/
│   │   │   └── engine.py            # Market correlation detection
│   │   ├── signals/
│   │   │   └── *.py                 # Signal plugins
│   │   ├── exporters/
│   │   │   └── prometheus.py        # Prometheus metrics server
│   │   └── observability/
│   │       └── otel.py              # OpenTelemetry tracing
│   ├── providers/
│   │   ├── base.py                  # BasePriceProvider abstract class
│   │   ├── polygon_provider.py      # Polygon.io integration
│   │   ├── finnhub_provider.py      # Finnhub integration
│   │   └── health.py                # Provider health monitoring
│   ├── backtest/
│   │   ├── engine.py                # BacktestEngine with slippage/commission
│   │   ├── monte_carlo.py          # Monte Carlo simulation
│   │   └── runner.py                # Backtest CLI runner
│   ├── strategies/
│   │   ├── versioning.py            # Strategy version manager
│   │   └── optimizer.py             # Grid search optimizer
│   ├── routes/
│   │   ├── analyze.ts              # Analysis endpoints
│   │   ├── emergencyStop.ts        # Emergency stop endpoints
│   │   └── webhook.ts              # Webhook handlers
│   ├── services/
│   │   ├── logService.ts           # Logging service
│   │   ├── orbEvaluator.ts         # ORB evaluation service
│   │   └── pulseClient.ts          # Pulse client (TypeScript)
│   └── tests/
│       ├── test_engine_risk_overrides.py
│       ├── test_pulse_retry_queue.py
│       └── test_decision_feed_and_tickers.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx        # Main trading dashboard
│   │   │   ├── TickerConfigModal.tsx
│   │   │   ├── BacktestResultsChart.tsx
│   │   │   └── HealthStatusCard.tsx
│   │   ├── lib/
│   │   │   ├── api.ts              # REST API client
│   │   │   ├── ws.ts               # WebSocket client
│   │   │   └── hooks.ts            # React hooks
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml              # Full stack orchestration
├── docker-compose.monitoring.yml   # Prometheus + Grafana
├── prometheus/
│   ├── prometheus.yml              # Prometheus configuration
│   └── rules.yml                   # Alerting rules
├── grafana/
│   └── dashboards/                  # Pre-built dashboards
└── README.md                        # This file
```

---

## 🛠️ Features

### Phase 1: Core Metrics
- **Opening Range Breakout (ORB)** — Track 9:30-9:45 AM volatility window
- **Average True Range (ATR)** — Volatility-adjusted position sizing
- **Momentum Signals** — Composite signal scoring engine (-10 to +10 scale)
- **Real-time price updates** — Multi-timeframe analysis with WebSocket

### Phase 2: Scheduler
- **Config-driven evaluation** — Per-symbol parameter overrides
- **Scheduled execution** — Configurable intervals per ticker
- **Market hours filtering** — US market open detection (9:30 AM - 4:00 PM ET)

### Phase 3: WebSocket Integration
- **Real-time price feeds** — Live market data streaming
- **Exponential backoff** — Reconnection resilience (5s → 120s max)
- **Dynamic subscriptions** — Per-symbol update management

### Phase 4: Provider Health
- **Multi-provider fallback** — Primary/secondary/tertiary price sources
- **Health monitoring** — Provider latency & failure tracking
- **Drag-to-reorder** — UI for provider priority management

### Phase 5: Backtest & Dry-Run
- **Historical simulation** — Replay strategy on historical data
- **Dry-run mode** — Simulated trading without capital
- **Equity curve** — Track portfolio growth over time

### Phase 6: Provider Implementations
- **Polygon.io** — Full REST + WebSocket support
- **Finnhub** — Quote + candle endpoints
- **Slippage modeling** — Realistic execution costs
- **Commission tracking** — Per-trade cost accounting

### Phase 7: Monte Carlo
- **Probabilistic simulation** — 1000+ outcome paths
- **Risk metrics** — Value at Risk (VaR), profit probability
- **Stress testing** — Volatility multiplier scenarios

### Phase 8: Strategy Optimization
- **Grid search** — Automated parameter tuning
- **Strategy versioning** — Performance history tracking
- **Production safeguards** — Circuit breaker + kill switch
- **Daily loss limits** — Automatic trading pause at -5%

### Phase 9: Pulse Integration (NEW)
- **Bidirectional command bus** — MongoDB Change Streams
- **Real-time position sync** — Actual PnL from broker
- **Order fill tracking** — Closed-loop trade result recording
- **Circuit breaker** — Graceful degradation when Pulse unavailable

---

## 🧰 Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend Framework | FastAPI | 0.115+ |
| Async Runtime | asyncio / uvicorn | Python 3.11+ |
| Database | MongoDB (Motor) | 6.0+ |
| Frontend | React + TypeScript | 18+ / 5.0+ |
| Build Tool | Vite | 5.0+ |
| HTTP Client | httpx | 0.27+ |
| Data Handling | pandas / numpy | latest |
| Validation | Pydantic | 2.0+ |
| Observability | OpenTelemetry | 1.0+ |
| Metrics | Prometheus | 2.0+ |

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/Tetradim/sentinel-edge.git
cd sentinel-edge
```

### 2. Backend Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

### 3. Run Backend
```bash
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000
```

### 4. Run Frontend
```bash
cd frontend
npm install
npm run dev
```

### 5. Docker Deployment
```bash
docker-compose up -d
```

---

## 📡 API Endpoints

### Market Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/markets` | List available markets |
| GET | `/api/markets/{symbol}/price` | Current price for symbol |
| GET | `/api/orb/{symbol}` | ORB levels for all timeframes |
| GET | `/api/markets/{symbol}/ohlcv` | OHLCV candles |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tickers` | List all ticker configurations |
| POST | `/api/tickers/{symbol}` | Add new ticker |
| DELETE | `/api/tickers/{symbol}` | Remove ticker |
| PUT | `/api/tickers/{symbol}/config` | Update ticker config |

### Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/control/pause` | Pause evaluation loop |
| POST | `/api/control/resume` | Resume evaluation loop |
| POST | `/api/control/start` | Start scheduler |
| POST | `/api/control/stop` | Stop scheduler |

### Backtest & Optimization
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest` | Run historical simulation |
| GET | `/api/dry-run/status` | Check dry-run state |
| POST | `/api/backtest/optimize` | Grid search optimization |

### Emergency & Testing
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/emergency/kill-switch` | Toggle global kill switch |
| POST | `/api/test/pulse-command` | **Test Pulse → Edge integration** |

### Metrics & Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/stats` | Runtime statistics |
| GET | `/api/providers/health` | Provider health status |
| GET | `/api/queue` | Retry queue status |

---

## 📈 Backtest Engine

Run historical simulation with realistic modeling:

```json
{
  "symbol": "SPY",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 10000,
  "slippage_pct": 0.05,
  "commission_pct": 0.1,
  "num_simulations": 1000
}
```

Returns:
- **Equity curve** — Portfolio value over time
- **Trade log** — Every entry/exit with P&L
- **Performance metrics** — Sharpe, Sortino, max drawdown
- **Monte Carlo analysis** — Probabilistic outcomes

---

## 🎲 Monte Carlo Simulation

| Metric | Description |
|--------|-------------|
| `median_final_equity` | 50th percentile outcome |
| `worst_case_equity` | 5th percentile (VaR at 95%) |
| `probability_of_profit` | % of runs with positive return |
| `mean_max_drawdown` | Average peak-to-trough |
| `best_case_equity` | 95th percentile |

---

## 🛡️ Production Safeguards

| Safeguard | Description | Trigger |
|-----------|-------------|---------|
| **Kill Switch** | Instantly halts all trading | Manual toggle via API |
| **Daily Loss Limit** | Auto-pause at -5% daily loss | Every evaluation cycle |
| **Max Consecutive Losses** | Exit after 3+ consecutive losses | Risk check in decide() |
| **Max Drawdown** | Emergency exit at -10% drawdown | Per-position drawdown |
| **Circuit Breaker** | Provider fallback on failure | 5+ failures triggers OPEN state |
| **Retry Queue** | Persist failed decisions | Retry when circuit closes |
| **Position Size Limits** | Max position sizing | Config per ticker |

---

## 🔍 Testing

```bash
# Run all tests
pytest backend/tests/ -v

# Run specific test file
pytest backend/tests/test_pulse_retry_queue.py -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

### Test Integration with Pulse

```bash
# Test 1: Simulate ORDER_FILLED from Pulse
curl -X POST http://localhost:8000/api/test/pulse-command \
  -H "Content-Type: application/json" \
  -d '{"command_type": "ORDER_FILLED", "symbol": "AAPL", "order_id": "test_1", "fill_price": 175.50, "quantity": 100, "side": "BUY"}'

# Test 2: Simulate POSITION_UPDATE
curl -X POST http://localhost:8000/api/test/pulse-command \
  -H "Content-Type: application/json" \
  -d '{"command_type": "POSITION_UPDATE", "symbol": "AAPL", "position_size": 100, "current_pnl_pct": 2.5, "current_pnl_dollar": 250.0}'
```

---

## 📊 Monitoring

### Prometheus Metrics

Key metrics exported:
- `edge_decision_total` — Decision count by symbol and type
- `edge_consecutive_losses` — Current loss streak per symbol
- `edge_win_rate` — Win rate percentage per symbol
- `broker_circuit_state` — Pulse circuit breaker state (0=closed, 1=half-open, 2=open)
- `broker_failure_rate` — Failure rate percentage
- `edge_api_latency` — API call latency histogram
- `edge_api_calls_total` — API call count by endpoint and status

### Grafana Dashboards

Pre-built dashboards available in `grafana/dashboards/`:
- **Trading Overview** — P&L, trade count, win rate
- **Risk Metrics** — Drawdown, consecutive losses, position sizes
- **Provider Health** — Latency, uptime, fallback status

---

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_NAME` | MongoDB database name | `sentinel_edge` |
| `DB_HOST` | MongoDB host | `localhost` |
| `DB_PORT` | MongoDB port | `27017` |
| `PULSE_API_URL` | Sentinel Pulse URL | `http://pulse:8001` |
| `POLYGON_API_KEY` | Polygon.io API key | (required) |
| `FINNHUB_API_KEY` | Finnhub API key | (optional) |
| `GLOBAL_KILL_SWITCH` | Kill switch state | `false` |
| `ANALYST_START_METRICS_SERVER` | Start Prometheus on port 8002 | `false` |

---

## 📝 Disclaimer

This software is for educational purposes. Past backtest results do not guarantee future performance. Always use paper trading before deploying with live capital. Trading involves substantial risk of loss.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

## 🚀 Quick Start — Local Source Mode

Start Edge from the local source tree with production dependencies configured:

```bash
# Start the backend
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --reload

# Start the frontend
cd frontend
npm install
npm start
```

### Advisor Health

Access the **Advisor Health** tab in the frontend to:
- Check live Edge scheduler state
- Check Pulse link and circuit state
- Review provider health
- Review autonomous handoff status

### Portfolio Analytics

Access the **Portfolio** tab to see:
- Live Pulse equity and buying power
- Live positions reported by Pulse
- Realized and unrealized P&L when Pulse provides those fields

### Settings

Configure behavior in the **Settings** tab:
- Market data provider order
- Risk parameters (position size, stop loss, take profit)
- Rate limiting configuration

---

## 📊 New Features Summary

### Backend (`backend/price_fetcher.py`)

| Feature | Description |
|---------|-------------|
| **Market Data** | Live provider fallback order with yfinance default |
| **Provider Health** | Runtime provider success/failure tracking |
| **Shared OHLCV Cache** | One cached 1m OHLCV fetch path per symbol |

### Backend (`backend/signals_enhanced.py`)

| Feature | Description |
|---------|-------------|
| **Advanced Patterns** | 60+ TA-Lib candlestick patterns + complex (H&S, Double Top/Bottom) |
| **Multi-Timeframe** | Higher timeframe confirmation |
| **Confidence Scoring** | Volume, trend, momentum, RSI weighted |
| **Synthetic Data** | Test data generator for patterns |

### Backend (`backend/backtest/engine.py`)

| Feature | Description |
|---------|-------------|
| **Strategies** | SMA, RSI, Breakout, Pattern-enhanced |
| **Strategy Registry** | Factory for strategy creation |
| **Observation Replay** | Simulate Pulse feedback in backtests |
| **Monte Carlo** | Probabilistic simulation |

### Frontend (`frontend/src/components/dashboards/`)

| Dashboard | Features |
|-----------|----------|
| `AdvisorHealth.tsx` | Live Edge/Pulse/provider status |
| `PortfolioAnalytics.tsx` | Live Pulse account and positions |
| `SettingsDashboard.tsx` | Config UI, localStorage persistence |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/pulse/account` | Live Pulse account state |
| `GET /api/pulse/status` | Pulse link and circuit state |
| `POST /api/backtest/run` | Run enhanced backtest |
| `GET /api/strategies` | List available strategies |
| `GET /api/strategies/{name}` | Strategy details |

---

## 📄 License

MIT License - See LICENSE file for details
