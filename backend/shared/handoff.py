"""Shared Edge -> Pulse handoff contract models."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PulseHandoffAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    STOP_BUYING = "stop_buying"
    STOP_ALL = "stop_all"
    REGULAR_STOP = "regular_stop"
    TRAILING_STOP = "trailing_stop"
    OPENING_TRAILING_STOP = "opening_trailing_stop"
    TIGHTEN_STOP = "tighten_stop"
    TIGHTEN_TRAILING_STOP = "tighten_trailing_stop"
    DCA = "dca"
    EMERGENCY_EXIT = "emergency_exit"


class PulseHandoffMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class PulseHandoffStopType(str, Enum):
    REGULAR = "regular"
    TRAILING = "trailing"
    TIGHTEN = "tighten"
    TIGHTEN_TRAILING = "tighten_trailing"


class PulseHandoffSessionContext(str, Enum):
    PREMARKET_30M = "premarket_30m"
    MARKET_OPEN = "market_open"
    PUZZLE_KEY = "puzzle_key"


class PulseHandoffDcaPlan(BaseModel):
    """Optional scale-in plan for Pulse-side DCA handling."""

    steps: Optional[int] = Field(default=None, ge=1)
    interval_seconds: Optional[int] = Field(default=None, ge=0)
    allocation_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    model_config = ConfigDict(extra="allow")


class PulseHandoffRequest(BaseModel):
    """Versioned HTTP payload for `PULSE_HANDOFF_ENDPOINT`."""

    contract_version: Literal["edge.pulse.handoff.v1"] = "edge.pulse.handoff.v1"
    symbol: str
    action: PulseHandoffAction
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    mode: PulseHandoffMode
    orb_session: PulseHandoffSessionContext = PulseHandoffSessionContext.MARKET_OPEN
    stop_type: Optional[PulseHandoffStopType] = None
    trailing_percent: Optional[float] = Field(default=None, gt=0.0)
    dca: Optional[PulseHandoffDcaPlan] = None
    idempotency_key: str = Field(min_length=1)
    source: Literal["sentinel_edge"] = "sentinel_edge"
    created_at: float = Field(gt=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_edge_payload(cls, payload: Dict[str, Any]) -> "PulseHandoffRequest":
        return cls(**payload)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise_symbol(cls, value: Any) -> str:
        symbol = str(value or "").strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        return symbol

    @field_validator("reason", "orb_session", "idempotency_key", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def _validate_action_context(self) -> "PulseHandoffRequest":
        required_stop_types = {
            PulseHandoffAction.REGULAR_STOP: PulseHandoffStopType.REGULAR,
            PulseHandoffAction.TRAILING_STOP: PulseHandoffStopType.TRAILING,
            PulseHandoffAction.OPENING_TRAILING_STOP: PulseHandoffStopType.TRAILING,
            PulseHandoffAction.TIGHTEN_STOP: PulseHandoffStopType.TIGHTEN,
            PulseHandoffAction.TIGHTEN_TRAILING_STOP: PulseHandoffStopType.TIGHTEN_TRAILING,
        }
        trailing_actions = {
            PulseHandoffAction.TRAILING_STOP,
            PulseHandoffAction.OPENING_TRAILING_STOP,
            PulseHandoffAction.TIGHTEN_TRAILING_STOP,
        }
        required_stop_type = required_stop_types.get(self.action)
        if required_stop_type is not None:
            if self.stop_type is None:
                raise ValueError(f"stop_type is required for {self.action.value} handoff actions")
            if self.stop_type != required_stop_type:
                raise ValueError(
                    f"stop_type must be {required_stop_type.value} for {self.action.value} handoff actions"
                )
        if self.action in trailing_actions and self.trailing_percent is None:
            raise ValueError("trailing_percent is required for trailing handoff actions")
        if self.stop_type in {
            PulseHandoffStopType.TRAILING,
            PulseHandoffStopType.TIGHTEN_TRAILING,
        } and self.trailing_percent is None:
            raise ValueError("trailing_percent is required when stop_type is trailing")
        if self.action == PulseHandoffAction.DCA and self.dca is None:
            raise ValueError("dca is required for dca handoff actions")
        self._validate_idempotency_key_scope()
        return self

    def _validate_idempotency_key_scope(self) -> None:
        parts = self.idempotency_key.split(":")
        expected_format = "edge:{symbol}:{action}:{orb_session}:{minute_bucket}:{nonce}"
        if len(parts) != 6:
            raise ValueError(f"idempotency_key must match {expected_format}")

        prefix, symbol, action, orb_session, minute_bucket, nonce = parts
        if prefix != "edge":
            raise ValueError(f"idempotency_key must match {expected_format}")
        if symbol.upper() != self.symbol:
            raise ValueError("idempotency_key symbol must match payload symbol")
        if action != self.action.value:
            raise ValueError("idempotency_key action must match payload action")
        if orb_session != self.orb_session.value:
            raise ValueError("idempotency_key orb_session must match payload orb_session")
        if not minute_bucket.isdigit():
            raise ValueError("idempotency_key minute_bucket must be numeric")
        if not nonce.strip():
            raise ValueError("idempotency_key nonce is required")


def pulse_handoff_contract_document() -> Dict[str, Any]:
    """Return the public Edge -> Pulse handoff contract document."""
    action_values = [action.value for action in PulseHandoffAction]
    mode_values = [mode.value for mode in PulseHandoffMode]
    stop_type_values = [stop_type.value for stop_type in PulseHandoffStopType]
    session_context_values = [context.value for context in PulseHandoffSessionContext]

    return {
        "contract_version": "edge.pulse.handoff.v1",
        "endpoint_env": "PULSE_HANDOFF_ENDPOINT",
        "recommended_endpoint": "/api/edge/handoff",
        "request_schema": PulseHandoffRequest.model_json_schema(),
        "transport_headers": {
            "Idempotency-Key": "Same value as request.idempotency_key.",
            "X-Edge-Mode": "Same value as request.mode, either paper or live.",
            "X-Edge-Contract-Version": "Same value as request.contract_version.",
        },
        "response_contract": {
            "accepted_response": {
                "accepted": True,
                "status": "accepted",
                "reason": "pulse_accepted",
                "handoff_id": "optional Pulse handoff identifier",
            },
            "rejected_response": {
                "accepted": False,
                "status": "rejected",
                "reason": "Pulse rejection reason such as risk_limit",
                "message": "optional operator-facing explanation",
            },
            "failed_response": {
                "accepted": False,
                "status": "failed",
                "error": "Pulse processing or schema failure reason",
                "message": "optional operator-facing explanation",
            },
        },
        "semantics": {
            "mode": "Only paper or live handoffs may be sent to Pulse; recommend_only is suppressed by Edge.",
            "idempotency_key": "Required and generated by Edge per symbol/action/session/time bucket.",
            "action": "One of the versioned PulseHandoffAction values.",
            "global_symbol": "GLOBAL is reserved for Pulse-supported portfolio-wide handoffs such as stop_all, emergency_exit, and global trailing-stop changes.",
            "trailing_percent": "Required for trailing_stop and tighten_trailing_stop handoffs.",
            "dca": "Required for dca handoffs and preserved as a structured plan.",
        },
        "field_semantics": {
            "contract_version": {
                "required": False,
                "default": "edge.pulse.handoff.v1",
                "transport_header": "X-Edge-Contract-Version",
            },
            "symbol": {
                "required": True,
                "normalization": "uppercased_by_edge",
                "reserved_values": {
                    "GLOBAL": "Portfolio-wide handoff scope for Pulse-supported global actions.",
                },
            },
            "action": {
                "required": True,
                "allowed_values": action_values,
                "conditional_fields": {
                    "regular_stop": ["stop_type"],
                    "trailing_stop": ["stop_type", "trailing_percent"],
                    "opening_trailing_stop": ["stop_type", "trailing_percent"],
                    "tighten_stop": ["stop_type"],
                    "tighten_trailing_stop": ["stop_type", "trailing_percent"],
                    "dca": ["dca"],
                },
            },
            "confidence": {
                "required": True,
                "range": [0.0, 1.0],
            },
            "mode": {
                "required": True,
                "allowed_values": mode_values,
                "paper_semantics": "Pulse may simulate or route to a paper account; Edge still records accepted/rejected feedback.",
                "live_semantics": "Pulse may route to live execution only after Pulse-side risk checks accept the handoff.",
                "recommend_only_semantics": "suppressed_by_edge",
            },
            "orb_session": {
                "required": False,
                "default": PulseHandoffSessionContext.MARKET_OPEN.value,
                "known_edge_values": session_context_values,
                "known_orb_session_values": ["premarket_30m", "market_open"],
                "strategy_context_values": {
                    "puzzle_key": "non-ORB strategy context used by the Puzzle Key plugin handoff path."
                },
            },
            "stop_type": {
                "required": False,
                "allowed_values": stop_type_values,
                "required_when": [
                    "action=regular_stop",
                    "action=trailing_stop",
                    "action=opening_trailing_stop",
                    "action=tighten_stop",
                    "action=tighten_trailing_stop",
                ],
                "required_values_by_action": {
                    "regular_stop": "regular",
                    "trailing_stop": "trailing",
                    "opening_trailing_stop": "trailing",
                    "tighten_stop": "tighten",
                    "tighten_trailing_stop": "tighten_trailing",
                },
            },
            "trailing_percent": {
                "required": False,
                "unit": "percent",
                "required_when": [
                    "action=trailing_stop",
                    "action=opening_trailing_stop",
                    "action=tighten_trailing_stop",
                    "stop_type=trailing",
                    "stop_type=tighten_trailing",
                ],
            },
            "dca": {
                "required": False,
                "required_when": ["action=dca"],
                "shape": {
                    "steps": "optional integer >= 1",
                    "interval_seconds": "optional integer >= 0",
                    "allocation_pct": "optional percentage from 0 to 100",
                },
            },
            "idempotency_key": {
                "required": True,
                "transport_header": "Idempotency-Key",
                "format": "edge:{symbol}:{action}:{orb_session}:{minute_bucket}:{nonce}",
                "validation": "must_match_payload_scope",
                "dedupe_scope": ["symbol", "action", "orb_session", "minute_bucket", "nonce"],
                "pulse_requirement": "Pulse should treat duplicate keys as the same handoff attempt.",
            },
            "metadata": {
                "required": False,
                "semantics": "Edge may include decision context, ORB context, price, ATR, PnL, and strategy-specific fields.",
            },
        },
        "feedback_semantics": {
            "accepted": {
                "edge_sent": True,
                "pulse_side_effect": "Pulse accepted the handoff for paper/live processing.",
                "expected_fields": ["accepted", "status", "reason"],
            },
            "rejected": {
                "edge_sent": False,
                "pulse_side_effect": "Pulse intentionally declined the handoff; Edge must not mutate local position state.",
                "expected_fields": ["accepted", "status", "reason"],
            },
            "failed": {
                "edge_sent": False,
                "pulse_side_effect": "Pulse transport or processing failed; Edge records the failure and may use legacy fallback behavior.",
                "expected_fields": ["accepted", "status", "error"],
            },
        },
    }
