"""Sentinel Edge — Main FastAPI Server"""
import asyncio
import json
import logging
import math
import os
import re
import secrets
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import REGISTRY, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

# Local modules
from atr import ATRCalculator
from engine import DecisionEngine
from market_hours import MarketHours
from notification_channels import (
    notification_channel_status,
    notification_confirmation_feedback,
    notification_confirmation_preview,
)
from orb import ORBTracker
from price_fetcher import PriceFetcher
from providers.catalog import active_provider_order, configured_key_sources, default_provider_order, provider_catalog
from pulse_client import PulseClient
from runtime_mode import is_dry_run_enabled
from scheduler import EvaluationScheduler
from signals import SignalEngine
from alert_handler import router as alert_handler_router, shutdown as alert_handler_shutdown
from automation import AutomationMode
from bot_event_bus_routes import router as bot_event_bus_router
from chrome_bridge_routes import router as chrome_bridge_router
from chart_workspace import build_chart_workspace_payload, build_market_map_context
from frontend_rum import FrontendRumRegistry, metric_label, normalise_rum_route
from shared.bot_event_bus import event_bus, publish_event
from shared.handoff import pulse_handoff_contract_document
from scanner_workbench_catalog import scanner_workbench_catalog, validate_scanner_watch_intent
from support_resistance import (
    DIRECTIVE_SCHEMA_VERSION,
    build_support_resistance_levels,
    evaluate_support_resistance_position,
    support_resistance_directive_state,
)
from simulation_lab import (
    SimulationLabDisabledError,
    require_simulation_lab_enabled,
    run_buying_power_allocation_experiment,
    run_orb_backtest_replay,
    run_stop_trailing_dca_comparison,
    simulation_lab_status,
)
from metrics import (
    edge_frontend_long_task_duration_ms,
    edge_frontend_rum_active_routes,
    edge_frontend_rum_dropped_metrics_total,
    edge_frontend_rum_last_received_timestamp_seconds,
    edge_frontend_rum_samples_total,
    edge_frontend_slow_interaction_duration_ms,
    edge_frontend_web_vital_value,
    edge_rate_limit_pruned_clients_total,
    edge_rate_limit_rejections_total,
    edge_rate_limit_tracked_clients,
    edge_readiness_check_status,
    edge_readiness_status,
    monte_carlo_expected_shortfall,
    monte_carlo_mean_drawdown,
    monte_carlo_median_equity,
    monte_carlo_probability_profit,
    monte_carlo_profit_prob,
    monte_carlo_ruin_prob,
    monte_carlo_var_5pct,
)

# NEW: Resilience & persistence modules
from state_persistence import StatePersistence, IdempotencyManager
from rate_limit import RateLimiter, CCTXRateLimiter
from json_logging import setup_json_logging, get_logger
from audit import AuditTrail
from config_audit import ConfigValidator, ConfigHasher
from drift_detection import DriftDetector
from export_api import router as export_router
from archive_general_api import GeneralApiConfigStore, GeneralApiDefaults, create_fastapi_router

# Sentinel Edge analyst package
from analyst.core import SentinelEdge
from analyst.observability.otel import instrument_fastapi
from analyst.webhook import webhook_router
import analyst.core as _analyst_core

# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
PROCESS_STARTED_AT = time.time()

# Production mode requires all configured dependencies. Reject the old
# environment switch explicitly so stale shells cannot start a partial runtime.
_removed_demo_mode_requested = os.environ.get("DEMO_MODE", "false").lower() in ("true", "1", "yes")
if _removed_demo_mode_requested:
    raise RuntimeError(
        "DEMO_MODE has been removed from Sentinel Edge. "
        "Unset DEMO_MODE and configure MongoDB/Pulse for production mode."
    )

# MongoDB — client created once; motor handles pooling internally.
# The service fails startup if MongoDB is unavailable; no in-memory fallback is used.
mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
logger.info("MongoDB configured for %s", mongo_url)
db = None
_mongo_client = None

# Global singletons populated during lifespan
scheduler: EvaluationScheduler = None
scheduler_task = None
edge: SentinelEdge = None
price_fetcher: PriceFetcher = None

# NEW: Resilience module singletons (initialized in lifespan)
state_persistence: StatePersistence = None
idempotency_manager: IdempotencyManager = None
audit_trail: AuditTrail = None
drift_detector: DriftDetector = None
config_hasher: ConfigHasher = None

# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")
_MONTE_CARLO_CHART_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,96}$")
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 120
_RATE_LIMIT_BUCKET_PRESSURE_WARNING_THRESHOLD = 500
_rate_limit_buckets: Dict[str, list[float]] = {}
_memory_ticker_configs: Dict[str, Dict[str, Any]] = {}
frontend_rum_registry = FrontendRumRegistry()
FRONTEND_RUM_WEB_VITAL_METRICS = {"inp", "lcp", "cls", "ttfb", "fcp"}
_OPERATOR_ACTION_SECRET_ENV = "EDGE_OPERATOR_ACTION_SECRET"
_OPERATOR_ACTION_SECRET_HEADER = "X-Edge-Operator-Secret"
_LIVE_AUTOMATION_SIGNOFF = "ENABLE LIVE AUTOMATION"
_LIVE_AUTOMATION_SIGNOFF_HEADER = "X-Edge-Live-Readiness-Signoff"
_LIVE_AUTOMATION_SIGNOFF_FIELD = "live_readiness_signoff"


class SupportResistanceEvaluateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    bars: List[Dict[str, Any]] = Field(default_factory=list)
    current_price: Optional[float] = None
    position: Optional[Dict[str, Any]] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    levels: List[Dict[str, Any]] = Field(default_factory=list)
    emit_event: bool = False


def _configured_cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ] or ["*"]


def _cors_allows_credentials(origins: list[str]) -> bool:
    return "*" not in origins


def _test_command_endpoints_enabled() -> bool:
    value = os.getenv("EDGE_TEST_COMMAND_ENDPOINTS_ENABLED", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_test_command_endpoints_enabled() -> None:
    if not _test_command_endpoints_enabled():
        raise HTTPException(
            status_code=404,
            detail="Test command endpoints are disabled.",
        )


def _require_operator_action_secret(request: Request) -> None:
    expected = os.getenv(_OPERATOR_ACTION_SECRET_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{_OPERATOR_ACTION_SECRET_ENV} is required before operator action endpoints are accepted.",
        )

    provided = request.headers.get(_OPERATOR_ACTION_SECRET_HEADER, "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid operator action secret.")


def _require_live_automation_readiness_signoff(
    request: Request,
    patch: Dict[str, Any] | None = None,
) -> None:
    provided = ""
    if patch is not None:
        provided = str(patch.get(_LIVE_AUTOMATION_SIGNOFF_FIELD) or "").strip()
    if not provided:
        provided = request.headers.get(_LIVE_AUTOMATION_SIGNOFF_HEADER, "").strip()
    if not provided or not secrets.compare_digest(provided, _LIVE_AUTOMATION_SIGNOFF):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "live_automation_readiness_signoff_required",
                "required_confirmation": _LIVE_AUTOMATION_SIGNOFF,
                "header": _LIVE_AUTOMATION_SIGNOFF_HEADER,
            },
        )


def _automation_mode_value(value: Any) -> str:
    if isinstance(value, AutomationMode):
        return value.value
    return str(value or AutomationMode.RECOMMEND_ONLY.value)


def _automation_settings_mode(settings: Any) -> str:
    return _automation_mode_value(getattr(settings, "mode", AutomationMode.RECOMMEND_ONLY))


def _automation_patch_requires_operator_secret(settings: Any, patch: Dict[str, Any]) -> bool:
    if _automation_mode_value(patch.get("mode")) == AutomationMode.LIVE.value:
        return True

    next_mode = _automation_mode_value(patch.get("mode", getattr(settings, "mode", AutomationMode.RECOMMEND_ONLY)))
    if next_mode != AutomationMode.LIVE.value:
        return False

    if bool(patch.get("global_enabled", False)):
        return True
    if bool(patch.get("default_ticker_enabled", False)):
        return True

    per_ticker = patch.get("per_ticker_enabled")
    if isinstance(per_ticker, dict) and any(bool(enabled) for enabled in per_ticker.values()):
        return True

    return False


def _ticker_handoff_requires_operator_secret(settings: Any, enabled: bool) -> bool:
    return (
        bool(enabled)
        and _automation_settings_mode(settings) == AutomationMode.LIVE.value
        and bool(getattr(settings, "global_enabled", False))
    )


def _add_ticker_requires_operator_secret(settings: Any) -> bool:
    return (
        _automation_settings_mode(settings) == AutomationMode.LIVE.value
        and bool(getattr(settings, "global_enabled", False))
        and bool(getattr(settings, "default_ticker_enabled", False))
    )


def _remove_ticker_requires_operator_secret(settings: Any) -> bool:
    return (
        _automation_settings_mode(settings) == AutomationMode.LIVE.value
        and bool(getattr(settings, "global_enabled", False))
    )


_CORS_ORIGINS = _configured_cors_origins()
READINESS_CHECK_DETAILS: Dict[str, Dict[str, Any]] = {
    "scheduler_initialized": {
        "label": "Scheduler initialized",
        "description": "The evaluation scheduler singleton was created during startup.",
        "required": True,
    },
    "scheduler_running": {
        "label": "Scheduler running",
        "description": "The scheduler is actively accepting evaluation cycles.",
        "required": True,
    },
    "scheduler_task_alive": {
        "label": "Scheduler task alive",
        "description": "The background scheduler task exists and has not stopped.",
        "required": True,
    },
    "price_fetcher_initialized": {
        "label": "Market data ready",
        "description": "The price fetcher was initialized and can route market-data requests.",
        "required": True,
    },
    "analyst_initialized": {
        "label": "Analyst initialized",
        "description": "The Sentinel Edge analyst orchestrator was created.",
        "required": True,
    },
    "mongo_available": {
        "label": "MongoDB available",
        "description": "MongoDB is connected and available for persistence.",
        "required": True,
    },
}


def _symbol(raw: str) -> str:
    """Uppercase and validate a ticker symbol.

    Accepts standard US equity formats (SPY, BRK.B, BF-B) up to 10 chars.
    Raises HTTP 422 on invalid input so the error surfaces in FastAPI's
    validation response rather than propagating as a silent 200.
    """
    s = raw.upper().strip()
    if not _SYMBOL_RE.match(s):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid symbol '{raw}'. Expected 1-10 characters: letters, digits, dot, or hyphen.",
        )
    return s


def _require_scheduler() -> EvaluationScheduler:
    """Return the running scheduler or raise HTTP 503."""
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialised")
    return scheduler


def _require_price_fetcher() -> PriceFetcher:
    """Return the price fetcher or raise HTTP 503."""
    if price_fetcher is None:
        raise HTTPException(status_code=503, detail="PriceFetcher not initialised")
    return price_fetcher


def _readiness_checks() -> Dict[str, bool]:
    """Return dependency checks used by /api/ready."""
    scheduler_task_alive = scheduler_task is not None and not scheduler_task.done()
    return {
        "scheduler_initialized": scheduler is not None,
        "scheduler_running": bool(scheduler and scheduler.running),
        "scheduler_task_alive": scheduler_task_alive,
        "price_fetcher_initialized": price_fetcher is not None,
        "analyst_initialized": edge is not None,
        "mongo_available": db is not None,
    }


def _readiness_check_details(checks: Dict[str, bool]) -> Dict[str, Dict[str, Any]]:
    """Return operator-facing readiness check metadata."""
    details: Dict[str, Dict[str, Any]] = {}
    for check_name, ready in checks.items():
        metadata = READINESS_CHECK_DETAILS.get(
            check_name,
            {
                "label": check_name.replace("_", " ").title(),
                "description": "No additional readiness detail is available for this check.",
                "required": True,
            },
        )
        details[check_name] = {
            "name": check_name,
            "label": metadata["label"],
            "description": metadata["description"],
            "required": metadata["required"],
            "ready": ready,
        }
    return details


def _publish_readiness_metrics(checks: Dict[str, bool], ready: bool) -> None:
    """Publish current readiness state using fixed low-cardinality labels."""
    edge_readiness_status.set(1 if ready else 0)
    for check_name, check_ready in checks.items():
        edge_readiness_check_status.labels(check=check_name).set(1 if check_ready else 0)


def _refresh_readiness_metrics() -> Dict[str, Any]:
    """Refresh readiness gauges and return the current readiness payload."""
    checks = _readiness_checks()
    ready = all(checks.values())
    failing_checks = [key for key, value in checks.items() if not value]
    check_details = _readiness_check_details(checks)
    failing_check_details = [check_details[key] for key in failing_checks]
    _publish_readiness_metrics(checks, ready)
    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "check_details": check_details,
        "failing_checks": failing_checks,
        "failing_check_details": failing_check_details,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _chart_workspace_bars_from_frame(frame: Any) -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    for timestamp, row in frame.iterrows():
        timestamp_value = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp
        bars.append(
            {
                "timestamp": timestamp_value,
                "open": row.get("Open"),
                "high": row.get("High"),
                "low": row.get("Low"),
                "close": row.get("Close"),
                "volume": row.get("Volume", 0.0),
            }
        )
    return bars


def _rate_limit_pressure(tracked_clients: int) -> str:
    """Return the aggregate rate-limit bucket pressure state."""
    if tracked_clients >= _RATE_LIMIT_BUCKET_PRESSURE_WARNING_THRESHOLD:
        return "warning"
    return "normal"


def _rate_limit_remaining(request: Request) -> int:
    """Return the current caller's remaining request budget without exposing identity."""
    client = request.client.host if request.client else "unknown"
    recent = _rate_limit_buckets.get(client, [])
    return max(0, _RATE_LIMIT_MAX_REQUESTS - len(recent))


def _rate_limit_reset_seconds(request: Request, now: float) -> int:
    """Return seconds until the current caller's fixed-window bucket starts resetting."""
    client = request.client.host if request.client else "unknown"
    recent = _rate_limit_buckets.get(client, [])
    if not recent:
        return 0
    return max(0, min(_RATE_LIMIT_WINDOW_SECONDS, int(recent[0] + _RATE_LIMIT_WINDOW_SECONDS - now) + 1))


def _prune_rate_limit_buckets(now: float) -> None:
    """Remove idle client buckets after their fixed window expires."""
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    stale_clients = [
        client
        for client, timestamps in _rate_limit_buckets.items()
        if not timestamps or timestamps[-1] < cutoff
    ]
    for client in stale_clients:
        del _rate_limit_buckets[client]
    edge_rate_limit_pruned_clients_total.inc(len(stale_clients))
    edge_rate_limit_tracked_clients.set(len(_rate_limit_buckets))


def _enforce_rate_limit(request: Request) -> None:
    """Simple fixed-window in-memory rate limiter (per client IP)."""
    client = request.client.host if request.client else "unknown"
    now = time.time()
    _prune_rate_limit_buckets(now)
    recent = _rate_limit_buckets.setdefault(client, [])
    edge_rate_limit_tracked_clients.set(len(_rate_limit_buckets))
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    while recent and recent[0] < cutoff:
        recent.pop(0)
    if len(recent) >= _RATE_LIMIT_MAX_REQUESTS:
        retry_after_seconds = max(1, min(_RATE_LIMIT_WINDOW_SECONDS, int(recent[0] + _RATE_LIMIT_WINDOW_SECONDS - now) + 1))
        edge_rate_limit_rejections_total.labels(scope="api").inc()
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_seconds": retry_after_seconds,
            },
            headers={
                "Retry-After": str(retry_after_seconds),
                "RateLimit-Limit": str(_RATE_LIMIT_MAX_REQUESTS),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(retry_after_seconds),
                "X-RateLimit-Limit": str(_RATE_LIMIT_MAX_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(retry_after_seconds),
            },
        )
    recent.append(now)


class MetricToggles(BaseModel):
    """Per-ticker Prometheus metric enable/disable flags."""
    orb:       bool = Field(True,  description="ORB high/low/range metrics")
    atr:       bool = Field(True,  description="ATR value and volatility percentile")
    signal:    bool = Field(True,  description="Signal strength and trend direction")
    volume:    bool = Field(True,  description="Volume ratio and z-score")
    price:     bool = Field(True,  description="Current price gauge")
    breakouts: bool = Field(True,  description="ORB breakout counter")


class RiskConfig(BaseModel):
    """Per-ticker decision-risk thresholds."""
    max_consecutive_losses: int = Field(3, ge=1, le=20)
    max_drawdown_pct: float = Field(10.0, ge=0.1, le=100.0)
    trailing_stop_profit_threshold: float = Field(2.0, ge=0.1, le=50.0)


class TickerConfigBody(BaseModel):
    """Request body for PUT /api/tickers/{symbol}/config."""
    metrics: MetricToggles = Field(default_factory=MetricToggles)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    price_providers: List[str] = Field(default_factory=lambda: ["yfinance"])


def _normalise_price_providers(providers: Optional[List[str]]) -> List[str]:
    """Keep provider lists deduped and limited to runtime-supported names."""
    supported = set(default_provider_order())
    normalised: List[str] = []
    for provider in providers or ["yfinance"]:
        key = str(provider).strip().lower()
        if key in supported and key not in normalised:
            normalised.append(key)
    return normalised or ["yfinance"]


async def _get_ticker_config_doc(sym: str) -> Optional[Dict[str, Any]]:
    """Read ticker config from MongoDB or demo-mode memory."""
    if db is None:
        return _memory_ticker_configs.get(sym)
    return await db.ticker_configs.find_one({"symbol": sym}, {"_id": 0})


async def _save_ticker_config(sym: str, config: Dict[str, Any]) -> None:
    """Persist ticker config to MongoDB or demo-mode memory."""
    if db is None:
        _memory_ticker_configs[sym] = config
        return
    await db.ticker_configs.update_one(
        {"symbol": sym},
        {"$set": config},
        upsert=True,
    )


class AutomationSettingsBody(BaseModel):
    """Global autonomous Edge -> Pulse handoff settings."""
    global_enabled: Optional[bool] = None
    mode: Optional[AutomationMode] = None
    default_ticker_enabled: Optional[bool] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    cooldown_seconds: Optional[int] = Field(None, ge=0, le=3600)
    quiet_when_pulse_absent: Optional[bool] = None
    per_ticker_enabled: Optional[Dict[str, bool]] = None
    live_readiness_signoff: Optional[str] = Field(None, max_length=64)


class TickerAutomationBody(BaseModel):
    """Per-ticker autonomous handoff toggle."""
    enabled: bool
    live_readiness_signoff: Optional[str] = Field(None, max_length=64)


class NotificationConfirmationPreviewBody(BaseModel):
    """Request body for POST /api/notifications/confirmation/preview."""
    action_type: str = Field(..., min_length=1, max_length=64)
    symbol: Optional[str] = Field(None, min_length=1, max_length=10)
    mode: str = Field("paper", pattern="^(recommend_only|paper|live)$")
    channel_ids: List[str] = Field(default_factory=list, max_length=8)
    reason: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationConfirmationFeedbackBody(BaseModel):
    """Request body for POST /api/notifications/confirmation/feedback."""
    idempotency_key: str = Field(..., min_length=1, max_length=160)
    action_type: str = Field(..., min_length=1, max_length=64)
    decision: str = Field(..., min_length=1, max_length=32)
    channel_id: str = Field(..., min_length=1, max_length=32)
    operator_ref: Optional[str] = Field(None, max_length=120)
    reason: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FrontendRumMetric(BaseModel):
    """Single browser-side Web Vital value."""
    name: str = Field(..., min_length=1, max_length=16)
    value: Optional[float] = Field(None, ge=0)
    unit: str = Field(..., min_length=1, max_length=16)
    rating: str = Field("pending", min_length=1, max_length=32)


class FrontendRumInteraction(BaseModel):
    """Slow interaction observation from the browser Event Timing API."""
    type: str = Field("interaction", min_length=1, max_length=64)
    duration: float = Field(..., ge=0)


class FrontendRumLongTask(BaseModel):
    """Long task observation from the browser PerformanceObserver API."""
    duration: float = Field(..., ge=0)


class FrontendRumSnapshot(BaseModel):
    """Request body for POST /api/frontend/rum."""
    route: str = Field("/", min_length=1, max_length=128)
    metrics: List[FrontendRumMetric] = Field(default_factory=list, max_length=12)
    slowInteractions: List[FrontendRumInteraction] = Field(default_factory=list, max_length=10)
    longTasks: List[FrontendRumLongTask] = Field(default_factory=list, max_length=12)


class BacktestRequest(BaseModel):
    """Request body for POST /api/backtest."""
    symbol: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    initial_capital: float = 10000.0
    slippage_pct: float = 0.05
    commission_pct: float = 0.1
    num_simulations: int = 1000
    volatility_multiplier: float = 1.0
    monte_carlo_enabled: bool = True
    monte_carlo_method: str = Field("bootstrap", pattern="^(bootstrap|shuffle|normal|block_bootstrap)$")
    monte_carlo_confidence_level: float = Field(0.95, ge=0.50, le=0.999)
    monte_carlo_random_seed: Optional[int] = None
    monte_carlo_include_paths: bool = True
    monte_carlo_saved_charts: bool = True
    monte_carlo_sample_path_count: int = Field(25, ge=0, le=200)
    monte_carlo_histogram_bins: int = Field(20, ge=5, le=100)
    monte_carlo_ruin_threshold_pct: float = Field(50.0, ge=0.0, le=100.0)
    monte_carlo_block_size: int = Field(5, ge=1, le=100)
    dry_run: bool = True


class BacktestRunRequest(BaseModel):
    """Enhanced request for POST /api/backtest/run - with strategy selection"""
    symbols: List[str] = Field(default_factory=lambda: ["AAPL"])
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    timeframe: str = Field("1d", pattern="^(1m|5m|15m|1h|1d|1wk)$")
    strategy: str = "sma"  # sma, rsi, breakout, rsi_with_patterns, sma_with_patterns, puzzle_key_strategy
    initial_capital: float = 100000.0
    position_size_pct: float = 0.10
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15
    trailing_stop: bool = True
    trailing_pct: float = 0.03
    # Strategy-specific params
    fast_period: Optional[int] = 10
    slow_period: Optional[int] = 30
    rsi_period: Optional[int] = 14
    rsi_oversold: Optional[int] = 30
    rsi_overbought: Optional[int] = 70
    breakout_lookback: Optional[int] = 20
    # Pattern mode (for pattern-enhanced strategies)
    pattern_mode: Optional[str] = "filter"
    # Puzzle Key Strategy params
    puzzle_key_mode: str = Field("combined", pattern="^(night|day|combined)$")
    puzzle_key_night_session: str = "18:00-07:00"
    puzzle_key_day_session: str = "07:00-15:00"
    puzzle_key_night_bar_minutes: int = Field(105, ge=1, le=1440)
    puzzle_key_day_bar_minutes: int = Field(60, ge=1, le=1440)
    puzzle_key_reversal_lookback: int = Field(3, ge=2, le=200)
    puzzle_key_atr_period: int = Field(14, ge=2, le=200)
    puzzle_key_atr_multiplier: float = Field(0.75, ge=0.0, le=10.0)
    puzzle_key_trend_period: int = Field(20, ge=2, le=500)
    puzzle_key_trade_direction: str = Field("both", pattern="^(long|short|both)$")
    puzzle_key_confidence_floor: float = Field(0.55, ge=0.0, le=1.0)
    puzzle_key_no_new_entries_after: str = ""
    num_simulations: int = 1000
    volatility_multiplier: float = 1.0
    monte_carlo_enabled: bool = True
    monte_carlo_method: str = Field("bootstrap", pattern="^(bootstrap|shuffle|normal|block_bootstrap)$")
    monte_carlo_confidence_level: float = Field(0.95, ge=0.50, le=0.999)
    monte_carlo_random_seed: Optional[int] = None
    monte_carlo_include_paths: bool = True
    monte_carlo_saved_charts: bool = True
    monte_carlo_sample_path_count: int = Field(25, ge=0, le=200)
    monte_carlo_histogram_bins: int = Field(20, ge=5, le=100)
    monte_carlo_ruin_threshold_pct: float = Field(50.0, ge=0.0, le=100.0)
    monte_carlo_block_size: int = Field(5, ge=1, le=100)


class BacktestReportRequest(BaseModel):
    """Request for GET /api/backtest/report/{run_id}"""
    run_id: str


class SimulationLabOrbBar(BaseModel):
    """One OHLC bar for Simulation Lab ORB replay."""
    timestamp: str
    open: Optional[float] = None
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class SimulationLabOrbBacktestRequest(BaseModel):
    """Request body for POST /api/simulation-lab/orb/backtest."""
    symbol: str = "SPY"
    session_id: str = Field("market_open", pattern="^(premarket_30m|market_open)$")
    timeframe_minutes: int = Field(30, ge=1, le=390)
    breakout_side: str = Field("both", pattern="^(both|long|short)$")
    target_r_multiple: float = Field(2.0, gt=0.0, le=100.0)
    bars: List[SimulationLabOrbBar] = Field(..., min_length=1, max_length=50000)


class SimulationLabAllocationCandidate(BaseModel):
    """One candidate trade for Simulation Lab buying-power allocation."""
    symbol: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    requested_notional: float = Field(..., gt=0.0)
    current_exposure: float = Field(0.0, ge=0.0)


class SimulationLabBuyingPowerAllocationRequest(BaseModel):
    """Request body for POST /api/simulation-lab/buying-power/allocation."""
    buying_power: float = Field(..., gt=0.0)
    cash_reserve_pct: float = Field(0.0, ge=0.0, le=1.0)
    max_position_pct: float = Field(1.0, gt=0.0, le=1.0)
    mode: str = Field("confidence_weighted", pattern="^(confidence_weighted|equal_weight|priority_fill)$")
    candidates: List[SimulationLabAllocationCandidate] = Field(..., min_length=1, max_length=5000)


class SimulationLabStopTrailingDcaBar(BaseModel):
    """One price-path bar for Simulation Lab stop/trailing-stop/DCA comparison."""
    timestamp: str
    high: Optional[float] = None
    low: Optional[float] = None
    close: float


class SimulationLabStopTrailingDcaRequest(BaseModel):
    """Request body for POST /api/simulation-lab/stop-trailing-dca/compare."""
    entry_price: float = Field(..., gt=0.0)
    quantity: float = Field(1.0, gt=0.0)
    stop_loss_pct: float = Field(0.05, gt=0.0, le=1.0)
    trailing_pct: float = Field(0.03, gt=0.0, le=1.0)
    dca_steps: int = Field(1, ge=0, le=50)
    dca_drop_pct: float = Field(0.03, gt=0.0, le=1.0)
    dca_allocation_multiplier: float = Field(1.0, gt=0.0, le=10.0)
    price_path: List[SimulationLabStopTrailingDcaBar] = Field(..., min_length=1, max_length=50000)


def _monte_carlo_settings_from_request(request: Any):
    """Build Monte Carlo settings from a backtest request."""
    from backtest.monte_carlo import MonteCarloSettings

    return MonteCarloSettings(
        enabled=getattr(request, "monte_carlo_enabled", True),
        num_simulations=getattr(request, "num_simulations", 1000),
        method=getattr(request, "monte_carlo_method", "bootstrap"),
        volatility_multiplier=getattr(request, "volatility_multiplier", 1.0),
        confidence_level=getattr(request, "monte_carlo_confidence_level", 0.95),
        random_seed=getattr(request, "monte_carlo_random_seed", None),
        include_paths=getattr(request, "monte_carlo_include_paths", True),
        saved_charts=getattr(request, "monte_carlo_saved_charts", True),
        sample_path_count=getattr(request, "monte_carlo_sample_path_count", 25),
        histogram_bins=getattr(request, "monte_carlo_histogram_bins", 20),
        ruin_threshold_pct=getattr(request, "monte_carlo_ruin_threshold_pct", 50.0),
        block_size=getattr(request, "monte_carlo_block_size", 5),
    )


def _monte_carlo_chart_root() -> Path:
    """Return the root directory for saved Monte Carlo chart JSON."""
    return Path(os.getenv("SENTINEL_EDGE_MONTE_CARLO_CHART_DIR", "data/monte_carlo_charts")).resolve()


def _safe_monte_carlo_chart_name(value: str) -> str:
    """Validate a saved chart run id or chart name before using it in paths."""
    if not _MONTE_CARLO_CHART_NAME_RE.fullmatch(value):
        raise HTTPException(status_code=422, detail="Invalid Monte Carlo chart identifier")
    return value


def _monte_carlo_chart_api_path(run_id: str, chart_name: str) -> str:
    return f"/api/backtest/monte-carlo/charts/{run_id}/{chart_name}"


def _attach_monte_carlo_chart_api_paths(monte_carlo: Dict[str, Any]) -> None:
    chart_set = monte_carlo.get("saved_chart_set")
    if not isinstance(chart_set, dict):
        return

    run_id = chart_set.get("run_id")
    charts = chart_set.get("charts")
    if not isinstance(run_id, str) or not isinstance(charts, list):
        return

    for chart in charts:
        if not isinstance(chart, dict) or not isinstance(chart.get("name"), str):
            continue
        chart["api_path"] = _monte_carlo_chart_api_path(run_id, chart["name"])


def _record_monte_carlo_metrics(symbol: str, monte_carlo: Dict[str, Any]) -> None:
    """Publish the latest Monte Carlo tail-risk summary to Prometheus."""
    if monte_carlo.get("status") != "completed":
        return

    label = symbol.upper()
    probability_ratio = float(monte_carlo.get("probability_of_profit", 0) or 0) / 100
    monte_carlo_probability_profit.labels(symbol=label).set(probability_ratio)
    monte_carlo_profit_prob.labels(symbol=label).set(probability_ratio)
    monte_carlo_var_5pct.labels(symbol=label).set(float(monte_carlo.get("value_at_risk_pct", 0) or 0) / 100)
    monte_carlo_expected_shortfall.labels(symbol=label).set(
        float(monte_carlo.get("conditional_value_at_risk_pct", 0) or 0) / 100
    )
    monte_carlo_median_equity.labels(symbol=label).set(float(monte_carlo.get("median_final_equity", 0) or 0))
    monte_carlo_mean_drawdown.labels(symbol=label).set(float(monte_carlo.get("mean_max_drawdown", 0) or 0) / 100)
    monte_carlo_ruin_prob.labels(symbol=label).set(float(monte_carlo.get("probability_of_ruin", 0) or 0) / 100)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire all components, start background tasks, then tear down cleanly."""
    global scheduler, scheduler_task, edge, db, _mongo_client, price_fetcher
    global state_persistence, idempotency_manager, audit_trail, drift_detector, config_hasher, audit_logger

    logger.info("🚀 Starting Sentinel Edge...")
    
    try:
        _mongo_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
        await _mongo_client.admin.command("ping")
        db = _mongo_client[os.environ.get("DB_NAME", "sentinel_edge")]
        logger.info("MongoDB connected to %s", mongo_url)
    except Exception as e:
        logger.error("MongoDB connection failed: %s", e)
        raise

    pulse_url = os.getenv("PULSE_API_URL", "http://localhost:8002")

    retry_queue_log_dir = os.getenv("RETRY_QUEUE_LOG_DIR", "/app/logs")
    pulse_client   = PulseClient(
        base_url=pulse_url,
        api_key=os.getenv("PULSE_API_KEY"),
        retry_queue_log_dir=retry_queue_log_dir,
    )
    price_fetcher  = PriceFetcher()
    orb_tracker    = ORBTracker()
    atr_calculator = ATRCalculator(period=14)
    signal_engine  = SignalEngine()
    decision_engine = DecisionEngine()
    market_hours   = MarketHours()

    # ── Startup Pulse probe ────────────────────────────────────────────────
    # Non-blocking: Edge starts regardless of the result, but it always probes Pulse.
    pulse_available = await pulse_client.check_pulse()
    if pulse_available:
        logger.info("🔗 Pulse connected — running in connected mode")
    else:
        logger.warning(
            "🔌 Pulse not available — running in standalone mode. "
            "All analysis runs normally. Decisions will be sent once Pulse comes online."
        )
    pulse_client.start_retry_drain_loop()

    # SentinelEdge orchestrator — OTel tracing, WebSocket, MongoDB change stream
    edge = SentinelEdge(db=db, pulse_url=pulse_url)

    scheduler = EvaluationScheduler(
        pulse_client=pulse_client,
        price_fetcher=price_fetcher,
        orb_tracker=orb_tracker,
        atr_calculator=atr_calculator,
        signal_engine=signal_engine,
        decision_engine=decision_engine,
        market_hours=market_hours,
        db=db,
    )
    # Share the correlation engine and wire plugin discovery
    edge.set_scheduler(scheduler)

    # ── Initialize new resilience modules ─────────────────────────────────────
    global state_persistence, idempotency_manager, audit_trail, drift_detector, config_hasher
    
    # JSON structured logging for Loki
    setup_json_logging(json_output=os.getenv("LOG_JSON", "true").lower() == "true")
    audit_logger = get_logger("sentinel.audit")
    
    # State persistence (SQLite)
    state_persistence = StatePersistence()
    await state_persistence.init()
    
    # Idempotency manager for orders
    idempotency_manager = IdempotencyManager()
    await idempotency_manager.init()
    
    # Audit trail
    audit_trail = AuditTrail()
    await audit_trail.init()
    
    # Drift detection
    drift_detector = DriftDetector()
    await drift_detector.init()
    
    # Config validator (for validation endpoint)
    config_hasher = ConfigHasher()
    
    logger.info("✅ Resilience modules initialized (persistence, audit, drift detection)")

    # Expose live instance to the webhook alert handler
    _analyst_core.analyst_instance = edge

    scheduler_task = asyncio.create_task(scheduler.run())
    await edge.start_background_tasks()

    logger.info(
        "✅ Sentinel Edge started (Pulse: %s, position tracking: %s)",
        "connected" if pulse_available else "standalone",
        scheduler.position_tracker.mode_name,
    )
    yield

    # ── Graceful shutdown ──────────────────────────────────────────────────
    logger.info("🛑 Shutting down Sentinel Edge...")
    
    # Cleanup new resilience modules
    state_persistence.close()
    idempotency_manager.close()
    audit_trail.close()
    drift_detector.close()
    
    edge.stop()
    scheduler.stop()
    if scheduler_task and not scheduler_task.done():
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    await alert_handler_shutdown()  # close alert handler HTTP session
    await pulse_client.aclose()   # release httpx connection pool
    if _mongo_client is not None:
        _mongo_client.close()
    logger.info("👋 Sentinel Edge stopped")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sentinel Edge",
    description="Trading analyst sidecar for Sentinel Pulse",
    version="1.0.0",
    lifespan=lifespan,
)

instrument_fastapi(app)          # OTel request spans

api_router = APIRouter(prefix="/api")


# ═══════════════════════════════════════════════════════════════════════════
# Status / health
# ═══════════════════════════════════════════════════════════════════════════

@api_router.get("/")
async def root():
    return {
        "name": "Sentinel Edge",
        "version": "1.0.0",
        "status": "running" if scheduler and scheduler.running else "stopped",
    }


@api_router.get("/live")
async def liveness():
    """Return process liveness without checking runtime dependencies."""
    now = time.time()
    return {
        "status": "alive",
        "service": "sentinel-edge",
        "pid": os.getpid(),
        "uptime_seconds": round(now - PROCESS_STARTED_AT, 3),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@api_router.get("/health")
async def health():
    sched = _require_scheduler()
    return {
        "status":                 "healthy",
        "running":                sched.running,
        "paused":                 sched.paused,
        "active_tickers":         len(sched.active_tickers),
        "pulse_available":        sched.pulse.pulse_available,
        "position_tracking_mode": sched.position_tracker.mode_name,
    }


@api_router.get("/ready")
async def readiness():
    """Return 200 only when Edge core runtime dependencies are ready."""
    readiness_state = _refresh_readiness_metrics()
    ready = readiness_state["ready"]
    if not ready:
        raise HTTPException(status_code=503, detail=readiness_state)
    return readiness_state


@api_router.post("/frontend/rum")
async def ingest_frontend_rum(snapshot: FrontendRumSnapshot, request: Request):
    """Ingest browser RUM snapshots and expose them through /metrics."""
    _enforce_rate_limit(request)
    route = normalise_rum_route(snapshot.route)
    edge_frontend_rum_samples_total.labels(route=route).inc()

    accepted_metrics = 0
    for item in snapshot.metrics:
        if item.value is None:
            continue
        metric_name = metric_label(item.name, fallback="unknown", limit=24)
        if metric_name not in FRONTEND_RUM_WEB_VITAL_METRICS:
            edge_frontend_rum_dropped_metrics_total.labels(reason="unknown_metric").inc()
            continue
        rating = metric_label(item.rating, fallback="unknown", limit=32)
        edge_frontend_web_vital_value.labels(
            route=route,
            metric=metric_name,
            rating=rating,
        ).set(item.value)
        accepted_metrics += 1

    for item in snapshot.slowInteractions:
        edge_frontend_slow_interaction_duration_ms.labels(
            route=route,
            type=metric_label(item.type, fallback="interaction", limit=32),
        ).observe(item.duration)

    for item in snapshot.longTasks:
        edge_frontend_long_task_duration_ms.labels(route=route).observe(item.duration)

    frontend_rum_registry.record(
        route,
        metrics=accepted_metrics,
        slow_interactions=len(snapshot.slowInteractions),
        long_tasks=len(snapshot.longTasks),
    )
    rum_status = frontend_rum_registry.status()
    edge_frontend_rum_last_received_timestamp_seconds.set(time.time())
    edge_frontend_rum_active_routes.set(rum_status["route_count"])

    return {
        "status": "accepted",
        "route": route,
        "metrics": accepted_metrics,
        "slow_interactions": len(snapshot.slowInteractions),
        "long_tasks": len(snapshot.longTasks),
    }


@api_router.get("/frontend/rum/status")
async def get_frontend_rum_status(request: Request):
    """Return recent frontend RUM ingestion health for the UI."""
    _enforce_rate_limit(request)
    return frontend_rum_registry.status()


@api_router.get("/rate-limit/status")
async def get_rate_limit_status(request: Request):
    """Return aggregate API rate limiter state without client identifiers."""
    _enforce_rate_limit(request)
    tracked_clients = len(_rate_limit_buckets)
    return {
        "tracked_clients": tracked_clients,
        "window_seconds": _RATE_LIMIT_WINDOW_SECONDS,
        "max_requests_per_window": _RATE_LIMIT_MAX_REQUESTS,
        "bucket_pressure_warning_threshold": _RATE_LIMIT_BUCKET_PRESSURE_WARNING_THRESHOLD,
        "pressure": _rate_limit_pressure(tracked_clients),
        "remaining_requests": _rate_limit_remaining(request),
        "reset_seconds": _rate_limit_reset_seconds(request, time.time()),
    }


@api_router.get("/stats")
async def get_stats(request: Request):
    _enforce_rate_limit(request)
    sched = _require_scheduler()
    return {
        "active_tickers":      sched.active_tickers,
        "running":             sched.running,
        "paused":              sched.paused,
        "orb_levels_count":    len(sched.orb.get_all_levels()),
        "pulse_available":        sched.pulse.pulse_available,
        "pulse_circuit_state":    sched.pulse.state.name,
        "pulse_failures":         sched.pulse.failure_count,
        "retry_queue":            sched.pulse.queue_stats(),
        "position_tracking_mode": sched.position_tracker.mode_name,
        # Seconds since last successful yfinance fetch per symbol.
        # Values consistently > OHLCV_CACHE_TTL indicate stale data.
        "price_cache_age_s":      sched.prices.cache_ages(),
    }


@api_router.get("/notifications/status")
async def get_notifications_status():
    """Return redacted operator notification channel discovery for Settings."""
    return notification_channel_status()


@api_router.post("/notifications/confirmation/preview")
async def preview_notification_confirmation(body: NotificationConfirmationPreviewBody):
    """Return a redacted operator confirmation preview without sending notifications."""
    symbol = _symbol(body.symbol) if body.symbol else None
    try:
        return notification_confirmation_preview(
            body.action_type,
            symbol=symbol,
            mode=body.mode,
            channel_ids=body.channel_ids or None,
            reason=body.reason,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/notifications/confirmation/feedback")
async def record_notification_confirmation_feedback(body: NotificationConfirmationFeedbackBody):
    """Normalize operator confirmation feedback without triggering Pulse side effects."""
    try:
        return notification_confirmation_feedback(
            idempotency_key=body.idempotency_key,
            action_type=body.action_type,
            decision=body.decision,
            channel_id=body.channel_id,
            operator_ref=body.operator_ref,
            reason=body.reason,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.get("/markets")
async def get_market_status():
    sched = _require_scheduler()
    return sched.market_hours.get_all_status()


@api_router.get("/queue")
async def get_retry_queue(request: Request, limit: int = 100):
    _enforce_rate_limit(request)
    sched = _require_scheduler()
    return {
        "stats": sched.pulse.queue_stats(),
        "items": await sched.pulse.queue_snapshot(limit=limit),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Scheduler control
# ═══════════════════════════════════════════════════════════════════════════

@api_router.post("/control/pause")
async def pause_scheduler():
    _require_scheduler().pause()
    return {"message": "Scheduler paused"}


@api_router.post("/control/resume")
async def resume_scheduler(request: Request):
    _require_operator_action_secret(request)
    _require_scheduler().resume()
    return {"message": "Scheduler resumed"}


# ═══════════════════════════════════════════════════════════════════════════
# Tickers
# ═══════════════════════════════════════════════════════════════════════════

@api_router.get("/tickers")
async def get_tickers():
    """All active tickers with enriched live state."""
    sched = _require_scheduler()
    enriched = []
    for sym in sched.active_tickers:
        state = sched.ticker_state.get(sym) or {
            "symbol":        sym,
            "enabled":       True,
            "current_price": None,
            "orb_levels":    {},
            "orb_session_status": sched.orb.get_session_status(sym),
            "signal_strength": 0.0,
            "trend":         "neutral",
            "atr":           None,
            "volume_ratio":  None,
            "last_decision": None,
            "confidence":    0.0,
            "last_updated":  None,
        }
        enriched.append(state)
    return {"tickers": enriched, "count": len(enriched)}


@api_router.post("/tickers/{symbol}", status_code=201)
async def add_ticker(symbol: str, request: Request):
    """Add a ticker to the watch list."""
    sched = _require_scheduler()
    sym = _symbol(symbol)
    if _add_ticker_requires_operator_secret(sched.automation.settings):
        _require_operator_action_secret(request)
        _require_live_automation_readiness_signoff(request)
    sched.add_ticker(sym)
    return {"message": f"Added {sym} to watch list"}


@api_router.delete("/tickers/{symbol}")
async def remove_ticker(symbol: str, request: Request):
    """Remove a ticker from the watch list."""
    sched = _require_scheduler()
    sym = _symbol(symbol)
    if _remove_ticker_requires_operator_secret(sched.automation.settings):
        _require_operator_action_secret(request)
        _require_live_automation_readiness_signoff(request)
    if sym not in sched.active_tickers:
        raise HTTPException(status_code=404, detail=f"{sym} is not on the watch list")
    sched.remove_ticker(sym)
    return {"message": f"Removed {sym} from watch list"}


@api_router.put("/tickers/{symbol}/config")
async def update_ticker_config(symbol: str, body: TickerConfigBody = Body(...)):
    """
    Enable or disable individual Prometheus metrics for a ticker.

    The flags are persisted to MongoDB (ticker_configs collection) and applied
    immediately to the running scheduler — no restart required.
    """
    sched = _require_scheduler()
    sym = _symbol(symbol)

    metrics_dict = body.metrics.model_dump()
    risk_dict = body.risk.model_dump()
    price_providers = _normalise_price_providers(body.price_providers)

    config = {
        "symbol": sym,
        "metrics": metrics_dict,
        "risk": risk_dict,
        "price_providers": price_providers,
        "updated_at": datetime.utcnow(),
    }
    await _save_ticker_config(sym, config)
    sched.ticker_configs[sym] = {
        "metrics": metrics_dict,
        "risk": risk_dict,
        "price_providers": price_providers,
    }

    return {
        "symbol": sym,
        "metrics": metrics_dict,
        "risk": risk_dict,
        "price_providers": price_providers,
    }


@api_router.get("/tickers/{symbol}/config")
async def get_ticker_config(symbol: str):
    """Return the metric configuration for a ticker, defaulting all flags to True."""
    sym = _symbol(symbol)

    # Exclude _id — ObjectId is not JSON-serialisable
    doc = await _get_ticker_config_doc(sym)
    if doc:
        return {
            "symbol": sym,
            "metrics": doc.get("metrics", MetricToggles().model_dump()),
            "risk": doc.get("risk", RiskConfig().model_dump()),
            "price_providers": _normalise_price_providers(doc.get("price_providers")),
            "updated_at": doc.get("updated_at"),
        }

    # Return defaults rather than 404 — callers can treat missing config as "all on"
    return {
        "symbol": sym,
        "metrics": MetricToggles().model_dump(),
        "risk": RiskConfig().model_dump(),
        "price_providers": ["yfinance"],
        "updated_at": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ORB levels
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Provider health
# ═══════════════════════════════════════════════════════════════════════════


@api_router.get("/providers/health")
async def get_providers_health(price_fetcher: PriceFetcher = Depends(_require_price_fetcher)):
    """Return legacy health status for all price providers."""
    return price_fetcher.get_provider_health()


@api_router.get("/market-data/providers")
async def get_market_data_providers():
    """Return browser-safe metadata for supported market-data providers.

    This endpoint never returns API-key values. It only exposes provider names,
    capabilities, free-tier notes, configured key presence, and the current
    intraday fallback order so Settings can guide users without leaking secrets.
    """
    return {
        "providers": provider_catalog(),
        "fallback_order": active_provider_order(),
        "configured_order": active_provider_order(),
        "configured_keys": configured_key_sources(),
        "supported_order": default_provider_order(),
    }


@api_router.get("/providers")
async def list_providers():
    """Compatibility alias for market-data provider metadata."""
    return await get_market_data_providers()


@api_router.get("/providers/config")
async def get_providers_config():
    """Return provider config metadata with secret values redacted."""
    return {
        "fallback_order": active_provider_order(),
        "configured_order": active_provider_order(),
        "configured_keys": configured_key_sources(),
        "supported_order": default_provider_order(),
        "secret_values": "redacted",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Autonomous Edge -> Pulse handoff controls
# ═══════════════════════════════════════════════════════════════════════════


@api_router.get("/automation")
async def get_automation_status():
    """Return global/per-ticker autonomous Pulse handoff settings and status."""
    sched = _require_scheduler()
    return sched.automation.status()


@api_router.put("/automation")
async def update_automation_settings(body: AutomationSettingsBody, request: Request):
    """Update autonomous Pulse handoff settings without erasing ticker overrides."""
    sched = _require_scheduler()
    patch = body.model_dump(exclude_unset=True)
    if _automation_patch_requires_operator_secret(sched.automation.settings, patch):
        _require_operator_action_secret(request)
        _require_live_automation_readiness_signoff(request, patch)
    patch.pop(_LIVE_AUTOMATION_SIGNOFF_FIELD, None)
    if "mode" in patch and patch["mode"] is not None:
        patch["mode"] = patch["mode"].value
    settings = sched.automation.update_settings(patch)
    return sched.automation.status() | {"settings": settings.public_dict()}


@api_router.put("/automation/tickers/{symbol}")
async def update_ticker_automation(symbol: str, body: TickerAutomationBody, request: Request):
    """Enable/disable autonomous Pulse handoff for one ticker."""
    sched = _require_scheduler()
    sym = _symbol(symbol)
    if _ticker_handoff_requires_operator_secret(sched.automation.settings, body.enabled):
        _require_operator_action_secret(request)
        _require_live_automation_readiness_signoff(
            request,
            {_LIVE_AUTOMATION_SIGNOFF_FIELD: body.live_readiness_signoff},
        )
    sched.automation.set_ticker(sym, body.enabled)
    return sched.automation.status()


@api_router.get("/price/{symbol}")
async def get_current_market_price(
    symbol: str,
    request: Request,
    price_fetcher: PriceFetcher = Depends(_require_price_fetcher),
):
    """Return current observed price from Edge's market-data cache/providers."""
    _enforce_rate_limit(request)
    sym = _symbol(symbol)
    price = await price_fetcher.get_current_price(sym)
    if price is None:
        raise HTTPException(status_code=503, detail=f"No price available for {sym}")
    return {"symbol": sym, "price": price}


@api_router.get("/quote/{symbol}")
async def get_market_quote(
    symbol: str,
    request: Request,
    price_fetcher: PriceFetcher = Depends(_require_price_fetcher),
):
    """Return current observed price and volume for a symbol."""
    _enforce_rate_limit(request)
    sym = _symbol(symbol)
    quote = await price_fetcher.get_price_with_volume(sym)
    if quote is None:
        raise HTTPException(status_code=503, detail=f"No quote available for {sym}")
    price, volume = quote
    return {"symbol": sym, "price": price, "volume": volume}


# ═══════════════════════════════════════════════════════════════════════════
# Backtest
# ═══════════════════════════════════════════════════════════════════════════


# Global backtest engine (initialized in lifespan)
_backtest_engine = None


def get_backtest_engine():
    """Dependency to get backtest engine."""
    return _backtest_engine


@api_router.post("/backtest")
async def run_backtest(
    request: BacktestRequest,
    price_fetcher: PriceFetcher = Depends(_require_price_fetcher),
):
    """Run historical backtest for a symbol."""
    # Lazy initialization of backtest engine
    global _backtest_engine
    if _backtest_engine is None:
        from backtest.engine import BacktestEngine
        from engine import DecisionEngine
        _backtest_engine = BacktestEngine(price_fetcher, DecisionEngine())
    
    result = await _backtest_engine.run_backtest(
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        slippage_pct=request.slippage_pct,
        commission_pct=request.commission_pct,
        num_simulations=request.num_simulations,
        volatility_multiplier=request.volatility_multiplier
    )
    result["initial_capital"] = request.initial_capital
    if "error" not in result:
        from backtest.monte_carlo import MonteCarloEngine, MonteCarloSettings

        monte_carlo_settings: MonteCarloSettings = _monte_carlo_settings_from_request(request)
        result["monte_carlo"] = await MonteCarloEngine().run_simulation(result, monte_carlo_settings)
        _attach_monte_carlo_chart_api_paths(result["monte_carlo"])
        _record_monte_carlo_metrics(request.symbol, result["monte_carlo"])
    return result


@api_router.get("/backtest/monte-carlo/charts")
async def list_monte_carlo_chart_sets():
    """List saved Monte Carlo chart bundles with API paths for each chart."""
    root = _monte_carlo_chart_root()
    if not root.exists():
        return {"chart_sets": []}

    chart_sets: List[Dict[str, Any]] = []
    for manifest_path in sorted(root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        try:
            safe_run_id = _safe_monte_carlo_chart_name(run_id)
        except HTTPException:
            continue

        safe_charts = []
        for chart in manifest.get("charts", []):
            if not isinstance(chart, dict):
                continue
            chart_name = str(chart.get("name") or "")
            try:
                safe_chart_name = _safe_monte_carlo_chart_name(chart_name)
            except HTTPException:
                continue
            safe_charts.append(
                {
                    **chart,
                    "name": safe_chart_name,
                    "api_path": _monte_carlo_chart_api_path(safe_run_id, safe_chart_name),
                }
            )

        chart_sets.append(
            {
                **manifest,
                "run_id": safe_run_id,
                "chart_count": len(safe_charts),
                "charts": safe_charts,
                "manifest_path": str(manifest_path.resolve()),
            }
        )

    return {"chart_sets": chart_sets}


@api_router.get("/backtest/monte-carlo/charts/{run_id}/{chart_name}")
async def get_monte_carlo_chart(run_id: str, chart_name: str):
    """Return one saved Monte Carlo chart JSON payload."""
    safe_run_id = _safe_monte_carlo_chart_name(run_id)
    safe_chart_name = _safe_monte_carlo_chart_name(chart_name)
    root = _monte_carlo_chart_root()
    chart_path = (root / safe_run_id / f"{safe_chart_name}.json").resolve()

    if root not in chart_path.parents:
        raise HTTPException(status_code=403, detail="Chart path is outside the Monte Carlo chart directory")
    if not chart_path.exists():
        raise HTTPException(status_code=404, detail="Monte Carlo chart not found")

    try:
        return json.loads(chart_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Saved Monte Carlo chart JSON is invalid") from exc


@api_router.get("/simulation-lab/status")
async def get_simulation_lab_status():
    """Return the default-off Simulation Lab feature gate and roadmap experiments."""
    return simulation_lab_status()


@api_router.post("/simulation-lab/orb/backtest")
async def run_simulation_lab_orb_backtest(request: SimulationLabOrbBacktestRequest):
    """Run a gated ORB replay against explicit OHLC bars."""
    try:
        require_simulation_lab_enabled()
        bars = [bar.model_dump() if hasattr(bar, "model_dump") else bar.dict() for bar in request.bars]
        return run_orb_backtest_replay(
            symbol=request.symbol,
            session_id=request.session_id,
            timeframe_minutes=request.timeframe_minutes,
            breakout_side=request.breakout_side,
            target_r_multiple=request.target_r_multiple,
            bars=bars,
        )
    except SimulationLabDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/simulation-lab/buying-power/allocation")
async def run_simulation_lab_buying_power_allocation(request: SimulationLabBuyingPowerAllocationRequest):
    """Run a gated buying-power allocation experiment against candidate trades."""
    try:
        require_simulation_lab_enabled()
        candidates = [
            candidate.model_dump() if hasattr(candidate, "model_dump") else candidate.dict()
            for candidate in request.candidates
        ]
        return run_buying_power_allocation_experiment(
            buying_power=request.buying_power,
            cash_reserve_pct=request.cash_reserve_pct,
            max_position_pct=request.max_position_pct,
            mode=request.mode,
            candidates=candidates,
        )
    except SimulationLabDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/simulation-lab/stop-trailing-dca/compare")
async def run_simulation_lab_stop_trailing_dca_comparison(request: SimulationLabStopTrailingDcaRequest):
    """Run a gated stop/trailing-stop/DCA comparison against an explicit price path."""
    try:
        require_simulation_lab_enabled()
        price_path = [
            bar.model_dump() if hasattr(bar, "model_dump") else bar.dict()
            for bar in request.price_path
        ]
        return run_stop_trailing_dca_comparison(
            entry_price=request.entry_price,
            quantity=request.quantity,
            stop_loss_pct=request.stop_loss_pct,
            trailing_pct=request.trailing_pct,
            dca_steps=request.dca_steps,
            dca_drop_pct=request.dca_drop_pct,
            dca_allocation_multiplier=request.dca_allocation_multiplier,
            price_path=price_path,
        )
    except SimulationLabDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/backtest/run")
async def run_backtest_enhanced(
    request: BacktestRunRequest
):
    """Enhanced backtest with strategy selection and patterns.
    
    Use this endpoint for full backtesting with:
    - Strategy selection (sma, rsi, breakout, rsi_with_patterns, sma_with_patterns)
    - Configurable risk parameters (stop loss, take profit, trailing)
    - Pattern-enhanced strategies that filter/boost signals with chart patterns
    
    Returns run_id for fetching report later.
    """
    from backtest.engine import BacktestConfig, BacktestEngine
    from strategies.registry import create_strategy, StrategyRegistry
    
    # Create config
    config = BacktestConfig(
        symbols=request.symbols,
        start_date=request.start_date,
        end_date=request.end_date,
        timeframe=request.timeframe,
        initial_capital=request.initial_capital,
        position_size_pct=request.position_size_pct,
        stop_loss_pct=request.stop_loss_pct,
        take_profit_pct=request.take_profit_pct,
        trailing_stop=request.trailing_stop,
        trailing_pct=request.trailing_pct
    )
    
    # Create strategy based on selection
    strategy_params = {}
    if request.strategy == "sma":
        strategy_params = {"fast": request.fast_period, "slow": request.slow_period}
    elif request.strategy == "rsi":
        strategy_params = {
            "period": request.rsi_period,
            "oversold": request.rsi_oversold,
            "overbought": request.rsi_overbought
        }
    elif request.strategy == "breakout":
        strategy_params = {"lookback": request.breakout_lookback}
    elif request.strategy in ["rsi_with_patterns", "sma_with_patterns"]:
        strategy_params = {
            "period": request.rsi_period,
            "oversold": request.rsi_oversold,
            "overbought": request.rsi_overbought,
            "pattern_mode": request.pattern_mode
        }
    elif request.strategy == "puzzle_key_strategy":
        strategy_params = {
            "mode": request.puzzle_key_mode,
            "night_session": request.puzzle_key_night_session,
            "day_session": request.puzzle_key_day_session,
            "night_bar_minutes": request.puzzle_key_night_bar_minutes,
            "day_bar_minutes": request.puzzle_key_day_bar_minutes,
            "reversal_lookback": request.puzzle_key_reversal_lookback,
            "atr_period": request.puzzle_key_atr_period,
            "atr_multiplier": request.puzzle_key_atr_multiplier,
            "trend_period": request.puzzle_key_trend_period,
            "trade_direction": request.puzzle_key_trade_direction,
            "confidence_floor": request.puzzle_key_confidence_floor,
            "no_new_entries_after": request.puzzle_key_no_new_entries_after,
        }
    
    strategy = create_strategy(request.strategy, config, **strategy_params)
    
    # Run backtest
    engine = BacktestEngine(config, strategy)
    metrics = await engine.run()
    symbol_label = ",".join(symbol.upper() for symbol in request.symbols)
    from backtest.monte_carlo import MonteCarloEngine

    monte_carlo_base = {
        "symbol": symbol_label or "MULTI",
        "initial_capital": request.initial_capital,
        "total_return_pct": metrics.total_return_pct,
        "trades": [{"pnl_pct": t.pnl_pct} for t in metrics.trades],
    }
    monte_carlo = await MonteCarloEngine().run_simulation(
        monte_carlo_base,
        _monte_carlo_settings_from_request(request),
    )
    _attach_monte_carlo_chart_api_paths(monte_carlo)
    _record_monte_carlo_metrics(symbol_label or "MULTI", monte_carlo)
    
    # Store result for later retrieval
    run_id = f"bt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    _backtest_runs[run_id] = {
        "config": request.dict(),
        "metrics": metrics.to_dict(),
        "trades": [
            {
                "entry": t.entry_date.isoformat() if t.entry_date else None,
                "exit": t.exit_date.isoformat() if t.exit_date else None,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct
            } for t in metrics.trades
        ],
        "equity_curve": metrics.equity_curve,
        "monte_carlo": monte_carlo,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {
        "run_id": run_id,
        "status": "completed",
        "summary": {
            "total_return_pct": metrics.total_return_pct,
            "annualized_return": metrics.annualized_return,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "total_trades": metrics.total_trades,
            "win_rate": metrics.win_rate
        },
        "monte_carlo": monte_carlo
    }


@api_router.get("/backtest/runs")
async def list_backtest_runs():
    """List all backtest runs"""
    return {
        "runs": [
            {"run_id": k, "created_at": v.get("created_at")}
            for k, v in _backtest_runs.items()
        ]
    }


@api_router.get("/backtest/report/{run_id}")
async def get_backtest_report(run_id: str):
    """Get full backtest report with trades and equity curve"""
    run = _backtest_runs.get(run_id)
    if not run:
        return {"error": "Run not found"}
    
    return {
        "run_id": run_id,
        "config": run["config"],
        "metrics": run["metrics"],
        "trades": run["trades"],
        "equity_curve": run["equity_curve"][:100],  # Limit for display
        "monte_carlo": run.get("monte_carlo"),
        "created_at": run["created_at"]
    }


@api_router.get("/strategies")
async def list_strategies():
    """List all available strategies with their parameters"""
    from strategies.registry import StrategyRegistry
    return StrategyRegistry.list_strategies()


@api_router.get("/strategies/puzzle-key/status")
async def get_puzzle_key_status():
    """Return active Puzzle Key Strategy feature flag and runtime configuration."""
    enabled = os.getenv("EDGE_PUZZLE_KEY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    automation = None
    if scheduler is not None and getattr(scheduler, "automation", None) is not None:
        automation = scheduler.automation.settings.public_dict()

    return {
        "strategy": "puzzle_key_strategy",
        "enabled": enabled,
        "source": "environment",
        "env": {
            "EDGE_PUZZLE_KEY_ENABLED": os.getenv("EDGE_PUZZLE_KEY_ENABLED", "false"),
            "EDGE_PUZZLE_KEY_MODE": os.getenv("EDGE_PUZZLE_KEY_MODE", "combined"),
            "EDGE_PUZZLE_KEY_NIGHT_SESSION": os.getenv("EDGE_PUZZLE_KEY_NIGHT_SESSION", "18:00-07:00"),
            "EDGE_PUZZLE_KEY_DAY_SESSION": os.getenv("EDGE_PUZZLE_KEY_DAY_SESSION", "07:00-15:00"),
            "EDGE_PUZZLE_KEY_NIGHT_BAR_MINUTES": os.getenv("EDGE_PUZZLE_KEY_NIGHT_BAR_MINUTES", "105"),
            "EDGE_PUZZLE_KEY_DAY_BAR_MINUTES": os.getenv("EDGE_PUZZLE_KEY_DAY_BAR_MINUTES", "60"),
            "EDGE_PUZZLE_KEY_REVERSAL_LOOKBACK": os.getenv("EDGE_PUZZLE_KEY_REVERSAL_LOOKBACK", "3"),
            "EDGE_PUZZLE_KEY_ATR_PERIOD": os.getenv("EDGE_PUZZLE_KEY_ATR_PERIOD", "14"),
            "EDGE_PUZZLE_KEY_ATR_MULTIPLIER": os.getenv("EDGE_PUZZLE_KEY_ATR_MULTIPLIER", "0.75"),
            "EDGE_PUZZLE_KEY_TREND_PERIOD": os.getenv("EDGE_PUZZLE_KEY_TREND_PERIOD", "20"),
            "EDGE_PUZZLE_KEY_TRADE_DIRECTION": os.getenv("EDGE_PUZZLE_KEY_TRADE_DIRECTION", "both"),
            "EDGE_PUZZLE_KEY_CONFIDENCE_FLOOR": os.getenv("EDGE_PUZZLE_KEY_CONFIDENCE_FLOOR", "0.55"),
            "EDGE_PUZZLE_KEY_NO_NEW_ENTRIES_AFTER": os.getenv("EDGE_PUZZLE_KEY_NO_NEW_ENTRIES_AFTER", ""),
        },
        "automation": automation,
        "backtest": {
            "endpoint": "/api/backtest/run",
            "strategy": "puzzle_key_strategy",
        },
    }


@api_router.get("/strategies/{strategy_name}")
async def get_strategy_info(strategy_name: str):
    """Get detailed info about a specific strategy"""
    from strategies.registry import StrategyRegistry
    info = StrategyRegistry.get_strategy_info(strategy_name)
    if not info:
        return {"error": "Strategy not found"}
    return info


# In-memory storage for backtest runs
_backtest_runs: Dict[str, Dict] = {}


@api_router.get("/dry-run/status")
async def get_dry_run_status():
    """Get current dry-run mode status."""
    return {"dry_run_enabled": is_dry_run_enabled()}


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Strategy Optimization
# ─────────────────────────────────────────────────────────────────────────────


class OptimizeRequest(BaseModel):
    """Request body for POST /api/backtest/optimize."""
    symbol: str
    start_date: str
    end_date: str
    param_grid: Dict[str, List[float]]
    initial_capital: float = 10000.0


_optimizer = None


def get_strategy_optimizer():
    """Dependency to get strategy optimizer."""
    return _optimizer


@api_router.post("/backtest/optimize")
async def optimize_strategy(
    request: OptimizeRequest,
    price_fetcher: PriceFetcher = Depends(_require_price_fetcher),
):
    """Run grid search optimization over parameter combinations."""
    global _optimizer
    if _optimizer is None:
        from strategies.optimizer import StrategyOptimizer
        from engine import DecisionEngine
        _optimizer = StrategyOptimizer(
            BacktestEngine(price_fetcher, DecisionEngine())
        )
    
    result = await _optimizer.optimize(
        symbol=request.symbol,
        param_grid=request.param_grid,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
    )
    return result


@api_router.post("/emergency/kill-switch")
async def toggle_kill_switch(state: bool, request: Request):
    """Toggle the global kill switch to instantly halt all trading."""
    import os
    if state is False:
        _require_operator_action_secret(request)
    os.environ["GLOBAL_KILL_SWITCH"] = str(state).lower()
    logger.warning(f"🚨 Kill switch set to {state}")
    return {"status": f"kill switch set to {state}", "kill_switch_active": state}


@api_router.get("/emergency/kill-switch")
async def get_kill_switch_status():
    """Return the global kill switch state without mutating it."""
    return {
        "kill_switch_active": os.getenv("GLOBAL_KILL_SWITCH", "false").lower() == "true",
        "mode": "read_only_status",
    }


@api_router.post("/test/pulse-command")
async def test_pulse_command(command: dict):
    """For testing: simulate Pulse sending a command to Edge via MongoDB.
    
    This inserts a command into the shared `commands` collection, which
    Edge's change stream listener will pick up and process.
    
    Example curl:
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
    """
    _require_test_command_endpoints_enabled()
    from datetime import datetime
    
    global db
    await db.commands.insert_one({
        **command,
        "timestamp": datetime.utcnow()
    })
    logger.info(f"📤 Test command inserted: {command.get('command_type')} | {command.get('symbol')}")
    return {"status": "sent", "type": command.get("command_type")}


# ====================== Pulse Integration Endpoints ======================

@api_router.get("/pulse/health")
async def get_pulse_health():
    """Get Pulse connection health status.
    
    Returns circuit breaker state, failure count, retry queue status.
    """
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        return await sched.pulse.health_check_detailed()
    return {"error": "Pulse not configured"}


@api_router.get("/pulse/handoff/schema")
async def get_pulse_handoff_schema():
    """Return the versioned Edge -> Pulse handoff request and response contract."""
    return pulse_handoff_contract_document()


@api_router.get("/pulse/status")
async def get_pulse_status():
    """Get Pulse availability and connection state."""
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        return {
            "available": sched.pulse.pulse_available,
            "circuit_state": sched.pulse.state.name,
            "base_url": sched.pulse.base_url,
        }
    return {"error": "Pulse not configured"}


@api_router.get("/pulse/positions")
async def get_pulse_positions():
    """Get all positions from DecisionEngine (synced from Pulse)."""
    sched = _require_scheduler()
    if hasattr(sched, 'decisions'):
        return sched.decisions.get_all_positions()
    return {}


@api_router.get("/pulse/positions/{symbol}")
async def get_pulse_position(symbol: str):
    """Get position for a specific symbol from DecisionEngine."""
    sched = _require_scheduler()
    if hasattr(sched, 'decisions'):
        position = sched.decisions.get_position(symbol)
        if position:
            return position
        return {"status": "no_position", "symbol": symbol}
    return {"error": "Decision engine not configured"}


@api_router.get("/pulse/queue")
async def get_pulse_queue():
    """Get retry queue status for failed decisions."""
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        return sched.pulse.queue_stats()
    return {"error": "Pulse not configured"}


@api_router.get("/pulse/account")
async def get_pulse_account():
    """Get account status from Pulse (buying power, equity, etc.)."""
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        account = await sched.pulse.get_account_status()
        if account:
            return account
        return {"status": "unavailable"}
    return {"error": "Pulse not configured"}


@api_router.post("/pulse/emergency-exit/{symbol}")
async def pulse_emergency_exit(symbol: str, request: Request, reason: str = "Manual trigger"):
    """Trigger emergency exit for a symbol via Pulse."""
    _require_operator_action_secret(request)
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        result = await sched.pulse.send_emergency_exit(symbol.upper(), reason)
        return {"status": "sent" if result else "failed", "symbol": symbol, "reason": reason}
    return {"error": "Pulse not configured"}


@api_router.post("/pulse/trailing-stop/{symbol}")
async def pulse_enable_trailing(symbol: str, request: Request, percent: float = 1.5):
    """Enable trailing stop for a symbol via Pulse."""
    _require_operator_action_secret(request)
    if not math.isfinite(percent):
        raise HTTPException(status_code=422, detail="trailing percent must be finite")
    if percent <= 0:
        raise HTTPException(status_code=422, detail="trailing percent must be greater than 0")
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        result = await sched.pulse.enable_trailing_stop(symbol.upper(), percent)
        return {"status": "sent" if result else "failed", "symbol": symbol, "percent": percent}
    return {"error": "Pulse not configured"}


@api_router.post("/pulse/bot/start")
async def pulse_start_bot(request: Request, enable_all: bool = True):
    """Start the Pulse bot lifecycle through Edge operator control."""
    _require_operator_action_secret(request)
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        result = await sched.pulse.start_bot(enable_all=enable_all)
        return {"status": "sent" if result else "failed", "action": "start", "enable_all": enable_all}
    return {"error": "Pulse not configured"}


@api_router.post("/pulse/bot/stop")
async def pulse_stop_bot(request: Request, disable_all: bool = True):
    """Stop the Pulse bot lifecycle through Edge operator control."""
    _require_operator_action_secret(request)
    sched = _require_scheduler()
    if hasattr(sched, 'pulse'):
        result = await sched.pulse.stop_bot(disable_all=disable_all)
        return {"status": "sent" if result else "failed", "action": "stop", "disable_all": disable_all}
    return {"error": "Pulse not configured"}


@api_router.get("/orb/{symbol}")
async def get_orb_levels(symbol: str):
    """
    Return ORB high/low/range for every tracked timeframe (5m, 15m, 30m).

    Fields per timeframe
    ────────────────────
    high        : locked opening range high
    low         : locked opening range low
    range_width : high − low
    locked      : True once the opening window has elapsed
    is_valid    : True when both high and low have been set
    date        : trading date the levels were established (YYYY-MM-DD)
    start_time  : datetime the tracker started collecting for this timeframe
    lock_time   : datetime the range was locked (null until locked)
    """
    sched = _require_scheduler()
    sym = _symbol(symbol)

    levels = sched.orb.get_levels(sym)
    if not levels:
        raise HTTPException(status_code=404, detail=f"No ORB data for {sym} — market may be closed or ticker not yet evaluated")

    session_status = sched.orb.get_session_status(sym)
    result = {}
    for timeframe, level in levels.items():
        result[f"{timeframe}m"] = {
            "high":        level.high if level.is_valid else None,
            "low":         level.low  if level.is_valid else None,
            "range_width": level.range_width,
            "locked":      level.locked,
            "is_valid":    level.is_valid,
            "date":        level.date,
            "session_id":   level.session_id,
            "start_time":  level.start_time.isoformat() if level.start_time else None,
            "lock_time":   level.lock_time.isoformat()  if level.lock_time  else None,
        }

    return {
        "symbol": sym,
        "active_session": session_status["active_session"],
        "active_label": session_status["active_label"],
        "active_status": session_status["active_status"],
        "orb_levels": result,
        "orb_sessions": session_status["sessions"],
    }


@api_router.get("/chart-workspace/{symbol}")
async def get_chart_workspace(
    symbol: str,
    indicators: str = Query("ema_9,ema_20,sma_20,rsi_14,macd", min_length=1, max_length=160),
    limit: int = Query(240, ge=1, le=2000),
):
    """Return chart-ready candles, indicators, and ORB overlays for a symbol."""
    sym = _symbol(symbol)
    fetcher = _require_price_fetcher()
    frame = await fetcher.get_ohlcv(sym, period="2d", interval="1m")
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail=f"No chart workspace OHLCV data for {sym}")

    orb_status = None
    if scheduler is not None and getattr(scheduler, "orb", None) is not None:
        orb_status = scheduler.orb.get_session_status(sym)

    try:
        return build_chart_workspace_payload(
            symbol=sym,
            bars=_chart_workspace_bars_from_frame(frame),
            indicators=[part.strip() for part in indicators.split(",") if part.strip()],
            limit=limit,
            orb_status=orb_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.get("/market-map/proof-markers/{symbol}")
async def get_market_map_proof_markers(
    symbol: str,
    limit: int = Query(100, ge=1, le=500),
):
    """Return read-only alert and decision proof markers for Market Map."""
    requested_symbol = _symbol(symbol)
    markers = []
    for event in event_bus.recent(limit=limit):
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_symbol = str(
            payload.get("symbol")
            or payload.get("ticker")
            or payload.get("underlying")
            or ""
        ).upper()
        if event_symbol and event_symbol != requested_symbol:
            continue
        if not event_symbol:
            continue

        parsed = payload.get("parsed") if isinstance(payload.get("parsed"), dict) else {}
        parser_confidence = payload.get("parser_confidence", parsed.get("confidence"))
        markers.append(
            {
                "id": str(event.get("event_id") or payload.get("event_id") or payload.get("id") or len(markers) + 1),
                "symbol": requested_symbol,
                "timestamp": str(
                    payload.get("timestamp")
                    or payload.get("received_at")
                    or payload.get("created_at")
                    or event.get("created_at")
                    or ""
                ),
                "kind": str(payload.get("kind") or payload.get("event_type") or event.get("event_type") or "event"),
                "label": str(payload.get("label") or payload.get("decision") or payload.get("action") or "Event"),
                "status": str(payload.get("status") or payload.get("decision_status") or "review"),
                "parser_confidence": parser_confidence,
                "raw_text": payload.get("raw_text") or payload.get("content") or payload.get("message"),
                "proof": payload,
            }
        )
    return {
        "schema_version": "edge.market_map.proof_markers.v1",
        "symbol": requested_symbol,
        "items": markers,
    }


@api_router.get("/market-map/context/{symbol}")
async def get_market_map_context(
    symbol: str,
    limit: int = Query(240, ge=1, le=2000),
):
    """Return read-only Market Map context and explainable pass/review/block reasons."""
    sym = _symbol(symbol)
    fetcher = _require_price_fetcher()
    frame = await fetcher.get_ohlcv(sym, period="2d", interval="1m")
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail=f"No Market Map OHLCV data for {sym}")

    orb_status = None
    if scheduler is not None and getattr(scheduler, "orb", None) is not None:
        orb_status = scheduler.orb.get_session_status(sym)

    try:
        payload = build_chart_workspace_payload(
            symbol=sym,
            bars=_chart_workspace_bars_from_frame(frame),
            limit=limit,
            orb_status=orb_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    latest_bar = payload["bars"][-1] if payload.get("bars") else {}
    return build_market_map_context(
        symbol=sym,
        latest_price=latest_bar.get("close"),
        levels=payload.get("levels", {}).get("items", []),
    )


@api_router.post("/support-resistance/evaluate")
async def evaluate_support_resistance(request: SupportResistanceEvaluateRequest):
    """Evaluate supplied OHLCV and an option position against S/R levels."""
    sym = _symbol(request.symbol)
    if request.current_price is None:
        raise HTTPException(status_code=422, detail="current_price is required for S/R evaluation")

    try:
        if request.levels:
            levels_payload = {
                "schema_version": "edge.support_resistance.levels.v1",
                "symbol": sym,
                "current_price": request.current_price,
                "items": request.levels,
            }
        else:
            if not request.bars:
                raise ValueError("bars are required when levels are not supplied")
            levels_payload = build_support_resistance_levels(
                symbol=sym,
                bars=request.bars,
                current_price=request.current_price,
                settings=request.settings,
            )

        directive = None
        if request.position is not None:
            directive = evaluate_support_resistance_position(
                position=request.position,
                levels=levels_payload.get("items", []),
                current_price=float(request.current_price),
                settings=request.settings,
                bars=request.bars,
                state=support_resistance_directive_state if request.emit_event else None,
            )

        published_event = None
        if request.emit_event and directive is not None:
            event = publish_event(
                DIRECTIVE_SCHEMA_VERSION,
                payload=directive,
                correlation_id=str(directive.get("directive_id") or ""),
                dedupe_key=str(directive.get("directive_id") or ""),
                target_bots=["sentinel-echo"],
                trace={"symbol": sym, "source": "support_resistance_evaluate"},
            )
            published_event = event.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "schema_version": "edge.support_resistance.evaluation.v1",
        "symbol": sym,
        "current_price": request.current_price,
        "levels": levels_payload,
        "directive": directive,
        "event": published_event,
    }


@api_router.get("/scanner-workbench/catalog")
async def get_scanner_workbench_catalog():
    """Return Edge-native scanner, ticker, strategy, and indicator catalog metadata."""
    return scanner_workbench_catalog()


@api_router.post("/scanner-workbench/watch-intent/validate")
async def validate_scanner_workbench_watch_intent(intent: Dict[str, Any] = Body(...)):
    """Validate saved Scanner Workbench watch intent against the current catalog."""
    return validate_scanner_watch_intent(intent)


# ═══════════════════════════════════════════════════════════════════════════
# Decisions & correlation
# ═══════════════════════════════════════════════════════════════════════════

@api_router.get("/decisions")
async def get_decisions():
    """Last 50 non-HOLD trading decisions (decision feed)."""
    sched = _require_scheduler()
    return {
        "decisions": sched.recent_decisions[:50],
        "count":     len(sched.recent_decisions),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Config validation
# ═══════════════════════════════════════════════════════════════════════════

@api_router.post("/config/validate")
async def validate_config(config: dict = Body(...)):
    """Validate trading config and return hash for audit."""
    validator = ConfigValidator()
    issues = validator.validate(config)
    
    # Generate config hash
    config_hash = config_hasher.hash_config(config) if config_hasher else None
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "config_hash": config_hash,
    }


@api_router.get("/config/hash")
async def get_config_hash():
    """Get current config hash for audit trail."""
    if not config_hasher:
        return {"error": "Config hasher not initialized"}
    
    # Get config from scheduler or edge
    try:
        current_config = getattr(scheduler, 'config', {})
        config_hash = config_hasher.hash_config(current_config)
        return {"config_hash": config_hash}
    except Exception as e:
        return {"error": str(e)}


@api_router.get("/correlation")
async def get_correlation():
    """Correlation cluster list, market breadth summary, and latest cluster."""
    sched = _require_scheduler()
    return {
        "clusters": sched.correlation.get_recent_clusters(),
        "breadth":  sched.correlation.get_current_breadth(),
        "latest":   sched.correlation.get_latest_cluster(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Command Bus Test Endpoints (for testing Pulse → Edge communication)
# ═══════════════════════════════════════════════════════════════════════════

@api_router.post("/test/send-command")
async def test_send_command(command: dict = Body(...)):
    """Send a command to Edge via the Command Bus.
    
    This endpoint allows Pulse (or you) to simulate sending commands
    that would normally come via MongoDB Change Stream.
    
    Example - send ORDER_FILLED:
    ```json
    {
      "command_type": "ORDER_FILLED",
      "symbol": "BTCUSDT",
      "order_id": "se-order-123",
      "fill_price": 42000.0,
      "quantity": 0.1,
      "side": "BUY",
      "pnl_realized": 50.0
    }
    ```
    
    Example - send POSITION_UPDATE:
    ```json
    {
      "command_type": "POSITION_UPDATE",
      "symbol": "BTCUSDT",
      "position_size": 0.5,
      "entry_price": 41900.0,
      "current_pnl_pct": 2.38,
      "current_pnl_dollar": 50.0
    }
    ```
    """
    _require_test_command_endpoints_enabled()
    from datetime import datetime, timezone
    from shared.commands import COMMANDS_COLLECTION
    
    # Add timestamp if not provided
    if "timestamp" not in command:
        command["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Insert into commands collection (triggers change stream)
    result = await db[COMMANDS_COLLECTION].insert_one(command)
    
    return {
        "status": "command sent to Edge via Change Stream",
        "command_type": command.get("command_type"),
        "symbol": command.get("symbol"),
        "inserted_id": str(result.inserted_id),
    }


@api_router.get("/test/commands")
async def list_commands(limit: int = 10):
    """List recent commands in the Command Bus."""
    _require_test_command_endpoints_enabled()
    from shared.commands import COMMANDS_COLLECTION
    
    commands = await db[COMMANDS_COLLECTION].find() \
        .sort("timestamp", -1) \
        .limit(limit) \
        .to_list(limit)
    
    return {
        "count": len(commands),
        "commands": commands,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Prometheus scrape endpoint (outside the /api prefix)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics():
    """Prometheus text-format scrape endpoint."""
    _refresh_readiness_metrics()
    return generate_latest(REGISTRY).decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Router registration
# ─────────────────────────────────────────────────────────────────────────────

general_api_store = GeneralApiConfigStore(
    Path(__file__).parent / "data" / "general_api.json",
    GeneralApiDefaults(
        bot_id="sentinel-edge",
        display_name="Sentinel Edge",
        roles=("observer", "risk_controller"),
    ),
)
general_api_router = create_fastapi_router(general_api_store)

app.include_router(api_router)
app.include_router(general_api_router, prefix="/api")
app.include_router(bot_event_bus_router, prefix="/api")
app.include_router(chrome_bridge_router, prefix="/api")

# Alertmanager webhook receiver — /api/webhook/alert, /api/webhook/health
app.include_router(webhook_router, prefix="/api")

# Prometheus Alertmanager webhook receiver — /alerts
app.include_router(alert_handler_router, prefix="")

# Trade export endpoints — /export/trades, /export/pnl
app.include_router(export_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_cors_allows_credentials(_CORS_ORIGINS),
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Retry-After",
        "RateLimit-Limit",
        "RateLimit-Remaining",
        "RateLimit-Reset",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Static Files
# ─────────────────────────────────────────────────────────────────────────────

# Get frontend build directories for source, installed, and PyInstaller layouts.
root_dir = Path(__file__).parent.parent
if not root_dir.exists():
    root_dir = Path.cwd()

exe_dir = Path(sys.executable).parent if getattr(sys, "executable", None) else root_dir
bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))

frontend_dist = root_dir / "frontend" / "dist"
frontend_src = root_dir / "frontend" / "public"
backend_static = root_dir / "backend" / "static"
installed_static = exe_dir / "static"
bundled_static = bundle_dir / "static"

static_candidates = [
    backend_static,
    installed_static,
    bundled_static,
    frontend_dist,
    frontend_src,
]
actual_static = next((path for path in static_candidates if path.exists()), None)

print(f"Root dir: {root_dir}")
print(f"Exe dir: {exe_dir}")
print(f"Bundle dir: {bundle_dir}")
print(f"Frontend dist exists: {frontend_dist.exists()}")
print(f"Frontend src exists: {frontend_src.exists()}")
print(f"Backend static exists: {backend_static.exists()}")
print(f"Installed static exists: {installed_static.exists()}")
print(f"Bundled static exists: {bundled_static.exists()}")
print(f"Actual static path: {actual_static}")

frontend_mounted = False

if actual_static is not None:
    app.mount("/", StaticFiles(directory=str(actual_static), html=True), name="static")
    print(f"Frontend mounted from {actual_static}")
    frontend_mounted = True
else:
    print("WARNING: No frontend found - attempting to build automatically...")
    import subprocess
    import shutil
    import sys
    
    # Try to find npm - check PATH and common locations
    npm_cmd = None
    
    # First try shutil.which (works on Linux/Mac)
    npm_path = shutil.which("npm")
    if npm_path:
        npm_cmd = "npm"
    else:
        # On Windows, try npm.cmd or check common install locations
        if sys.platform == "win32":
            # Try npm.cmd
            npm_path = shutil.which("npm.cmd")
            if npm_path:
                npm_cmd = "npm.cmd"
            else:
                # Check Node.js common install paths
                node_paths = [
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files") + "\\nodejs"),
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)") + "\\nodejs"),
                    Path(os.environ.get("LOCALAPPDATA", "") + "\\Programs\\nodejs"),
                ]
                for node_path in node_paths:
                    if node_path.exists():
                        npm_candidate = node_path / "npm.cmd"
                        if npm_candidate.exists():
                            npm_cmd = str(npm_candidate)
                            break
    
    if npm_cmd:
        print(f"Found npm: {npm_cmd}")
        # Try to find frontend folder - check multiple locations
        frontend_dir = None
        possible_frontend_dirs = [
            root_dir / "frontend",
            exe_dir / "frontend",
            Path.cwd() / "frontend",
        ]
        for dir_check in possible_frontend_dirs:
            if dir_check.exists():
                pkg_check = dir_check / "package.json"
                if pkg_check.exists():
                    frontend_dir = dir_check
                    break
        
        if frontend_dir:
            try:
                print(f"Building frontend from {frontend_dir}")
                # Install dependencies using shell=True for Windows compatibility
                install_result = subprocess.run(
                    f'"{npm_cmd}" install',
                    cwd=str(frontend_dir),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print(f"npm install result: {install_result.returncode}")
                
                if install_result.returncode == 0:
                    # Build the frontend
                    build_result = subprocess.run(
                        f'"{npm_cmd}" run build',
                        cwd=str(frontend_dir),
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    print(f"npm build result: {build_result.returncode}")
                    
                    # Build outputs to frontend/dist - copy to exe folder
                    built_dist = frontend_dir / "dist"
                    if build_result.returncode == 0 and built_dist.exists():
                        # Copy to exe directory for persistence
                        exe_static = exe_dir / "static"
                        exe_static.mkdir(exist_ok=True)
                        import shutil as sh
                        # Copy files
                        for f in built_dist.iterdir():
                            dest = exe_static / f.name
                            if f.is_dir():
                                sh.copytree(f, dest, dirs_exist_ok=True)
                            else:
                                sh.copy2(f, dest)
                        app.mount("/", StaticFiles(directory=str(exe_static), html=True), name="frontend")
                        print(f"Frontend built and mounted from {exe_static}")
                        frontend_mounted = True
                    else:
                        print(f"Frontend build output: {build_result.stdout}")
                        print(f"Frontend build error: {build_result.stderr}")
                else:
                    print(f"npm install output: {install_result.stdout}")
                    print(f"npm install error: {install_result.stderr}")
            except Exception as e:
                print(f"Auto-build error: {e}")
    
    if not frontend_mounted:
        print("ERROR: No frontend found!")
        print("=" * 50)
        print("To fix this, either:")
        print("  1. Install Node.js from https://nodejs.org and restart Sentinel Edge")
        print("  2. OR copy frontend/dist to backend/static manually")
        print("  3. OR download the latest SentinelEdge-Setup.exe from GitHub releases")
        print("=" * 50)


def _open_browser_when_ready(url: str, timeout_seconds: float = 30.0) -> None:
    """Open the desktop UI once the local FastAPI server accepts requests."""
    if os.getenv("SENTINEL_EDGE_OPEN_BROWSER", "true").lower() in ("0", "false", "no", "off"):
        logger.info("Browser auto-open disabled by SENTINEL_EDGE_OPEN_BROWSER")
        return

    def _worker() -> None:
        import urllib.request
        import webbrowser

        deadline = time.time() + timeout_seconds
        health_url = f"{url.rstrip('/')}/api/ready"
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=1):
                    break
            except Exception:
                time.sleep(0.5)
        else:
            logger.warning("Sentinel Edge UI did not become ready before browser open timeout")
            return

        try:
            webbrowser.open(url, new=2)
            logger.info("Opened Sentinel Edge UI in browser: %s", url)
        except Exception as exc:
            logger.warning("Unable to open Sentinel Edge UI in browser: %s", exc)

    import threading
    threading.Thread(target=_worker, name="sentinel-edge-browser-open", daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SENTINEL_EDGE_PORT", os.getenv("PORT", "8001")))
    host = os.getenv("SENTINEL_EDGE_HOST", "0.0.0.0")
    ui_url = os.getenv("SENTINEL_EDGE_UI_URL", f"http://localhost:{port}")
    _open_browser_when_ready(ui_url)
    uvicorn.run(app, host=host, port=port)
