"""Sentinel Pulse API Client — circuit-breaker HTTP client."""

import logging
import os
import time
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from pydantic import ValidationError

from metrics import (
    broker_circuit_state,
    broker_failure_rate,
    edge_api_calls_total,
    edge_api_latency,
)
from retry_queue import DecisionQueue
from shared.handoff import PulseHandoffRequest

logger = logging.getLogger(__name__)

HEALTH_PROBE_TIMEOUT = 3.0


class CircuitState(Enum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class PulseClient:
    """HTTP client for Sentinel Pulse with circuit breaker and retry queue."""

    FAILURE_THRESHOLD = 5
    SUCCESS_THRESHOLD = 2
    TIMEOUT_SECONDS = 5.0
    CIRCUIT_OPEN_DURATION = 60
    DEFAULT_RETRY_TTL_SECONDS = 60.0
    EMERGENCY_EXIT_RETRY_TTL_SECONDS = 300.0

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        api_key: Optional[str] = None,
        retry_queue_log_dir: str = "/app/logs",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.broker_id = "pulse"

        self.pulse_available: bool = False
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0

        self._client = httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS,
            headers=self._build_headers(),
        )
        self.retry_queue = DecisionQueue(
            log_dir=retry_queue_log_dir,
            default_ttl_seconds=self.DEFAULT_RETRY_TTL_SECONDS,
            emergency_ttl_seconds=self.EMERGENCY_EXIT_RETRY_TTL_SECONDS,
        )

        broker_circuit_state.labels(broker_id=self.broker_id).set(self.state.value)
        broker_failure_rate.labels(broker_id=self.broker_id).set(0.0)
        logger.info("PulseClient initialised → %s (awaiting health probe)", self.base_url)

    async def check_pulse(self) -> bool:
        url = f"{self.base_url}/api/health"
        try:
            async with httpx.AsyncClient(timeout=HEALTH_PROBE_TIMEOUT) as probe:
                resp = await probe.get(url)
            if resp.status_code == 200:
                self.pulse_available = True
                logger.info("pulse_health_check ok base_url=%s", self.base_url)
            else:
                self.pulse_available = False
                logger.warning(
                    "pulse_health_check non_200 status=%d base_url=%s",
                    resp.status_code,
                    self.base_url,
                )
        except Exception as exc:
            self.pulse_available = False
            logger.warning(
                "pulse_health_check error=%s mode=standalone",
                exc,
            )
        return self.pulse_available

    def start_retry_drain_loop(self) -> None:
        self.retry_queue.start(
            can_send=lambda: self.state == CircuitState.CLOSED and self.pulse_available,
            send_func=self._post,
        )

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _should_allow_request(self) -> bool:
        if not self.pulse_available:
            return False

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.CIRCUIT_OPEN_DURATION:
                logger.info("Circuit breaker → HALF_OPEN (re-probing Pulse)")
                self.state = CircuitState.HALF_OPEN
                broker_circuit_state.labels(broker_id=self.broker_id).set(self.state.value)
                return True
            return False

        return True

    def _record_success(self) -> None:
        self.failure_count = 0
        if not self.pulse_available:
            self.pulse_available = True
            logger.info("Pulse responded — switching to connected mode")

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.SUCCESS_THRESHOLD:
                logger.info("Circuit breaker → CLOSED after %d successes", self.success_count)
                self.state = CircuitState.CLOSED
                self.success_count = 0
                broker_circuit_state.labels(broker_id=self.broker_id).set(self.state.value)
                self.retry_queue.notify_circuit_closed()

    def _record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0
        if self.failure_count >= self.FAILURE_THRESHOLD:
            logger.error("Circuit breaker → OPEN after %d failures", self.failure_count)
            self.state = CircuitState.OPEN
            broker_circuit_state.labels(broker_id=self.broker_id).set(self.state.value)

        total = max(self.failure_count, 1)
        broker_failure_rate.labels(broker_id=self.broker_id).set((self.failure_count / total) * 100)

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> bool:
        if not self._should_allow_request():
            if self.pulse_available:
                logger.debug("Circuit %s — POST %s suppressed", self.state.name, endpoint)
            else:
                logger.debug("Standalone mode — POST %s suppressed", endpoint)
            return False

        url = f"{self.base_url}{endpoint}"
        start = time.time()
        try:
            response = await self._client.post(url, json=payload)
            edge_api_latency.labels(endpoint=endpoint).observe(time.time() - start)
            if response.status_code in (200, 201, 202, 204):
                edge_api_calls_total.labels(endpoint=endpoint, status="success").inc()
                self._record_success()
                return True
            edge_api_calls_total.labels(endpoint=endpoint, status="failure").inc()
            self._record_failure()
            logger.error("Pulse %s → HTTP %d", endpoint, response.status_code)
            return False
        except httpx.TimeoutException:
            edge_api_calls_total.labels(endpoint=endpoint, status="timeout").inc()
            self._record_failure()
            logger.error("Pulse %s timed out", endpoint)
            return False
        except Exception as exc:
            edge_api_calls_total.labels(endpoint=endpoint, status="error").inc()
            self._record_failure()
            logger.error("Pulse %s error: %s", endpoint, exc)
            return False

    @staticmethod
    def _response_body(response: httpx.Response) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {"value": body}

    @staticmethod
    def normalise_handoff_feedback(
        endpoint: str,
        status_code: Optional[int],
        response_body: Optional[Dict[str, Any]] = None,
        *,
        legacy_fallback: bool = False,
    ) -> Dict[str, Any]:
        body = response_body if isinstance(response_body, dict) else {}
        status_text = str(body.get("status") or body.get("result") or "").lower()
        accepted_flag = body.get("accepted")
        sent_flag = body.get("sent")
        ok = status_code in (200, 201, 202, 204)
        rejected_statuses = {"rejected", "denied", "declined", "ignored"}
        failed_statuses = {"failed", "error"}

        if ok and status_text in failed_statuses:
            reason = body.get("error") or body.get("reason") or body.get("message") or "pulse_failed"
            return PulseClient._enrich_handoff_feedback(
                {
                    "sent": False,
                    "status": "failed",
                    "reason": str(reason),
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "response": body,
                    "legacy_fallback": legacy_fallback,
                }
            )

        if ok and (accepted_flag is False or sent_flag is False or status_text in rejected_statuses):
            reason = (
                body.get("rejection_reason")
                or body.get("reason")
                or body.get("error")
                or body.get("message")
                or "pulse_rejected"
            )
            return PulseClient._enrich_handoff_feedback(
                {
                    "sent": False,
                    "status": "rejected",
                    "reason": str(reason),
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "response": body,
                    "legacy_fallback": legacy_fallback,
                }
            )

        if ok:
            return PulseClient._enrich_handoff_feedback(
                {
                    "sent": True,
                    "status": "accepted",
                    "reason": "pulse_accepted",
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "response": body,
                    "legacy_fallback": legacy_fallback,
                }
            )

        reason = (
            body.get("error")
            or body.get("reason")
            or (f"http_{status_code}" if status_code is not None else "pulse_send_failed")
        )
        return PulseClient._enrich_handoff_feedback(
            {
                "sent": False,
                "status": "failed",
                "reason": str(reason),
                "endpoint": endpoint,
                "status_code": status_code,
                "response": body,
                "legacy_fallback": legacy_fallback,
            }
        )

    @staticmethod
    def _enrich_handoff_feedback(feedback: Dict[str, Any]) -> Dict[str, Any]:
        response = feedback.get("response")
        if not isinstance(response, dict):
            return feedback

        handoff_id = response.get("handoff_id") if "handoff_id" in response else response.get("id")
        if handoff_id is not None:
            feedback["handoff_id"] = str(handoff_id)

        message = response.get("message") if "message" in response else response.get("detail")
        if message is not None:
            feedback["message"] = str(message)

        return feedback

    @staticmethod
    def suppressed_handoff_feedback(endpoint: str, reason: str) -> Dict[str, Any]:
        return {
            "sent": False,
            "status": "suppressed",
            "reason": reason,
            "endpoint": endpoint,
            "status_code": None,
            "response": {},
            "legacy_fallback": False,
        }

    @staticmethod
    def legacy_handoff_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "reason": payload.get("reason", ""),
            "confidence": payload.get("confidence", 0.0),
            "idempotency_key": payload.get("idempotency_key"),
            "source": payload.get("source", "sentinel_edge"),
            "mode": payload.get("mode"),
            "orb_session": payload.get("orb_session"),
            "stop_type": payload.get("stop_type"),
            "trailing_percent": payload.get("trailing_percent"),
            "dca": payload.get("dca"),
            "metadata": payload.get("metadata", {}),
        }

    @staticmethod
    def _json_safe_validation_errors(exc: ValidationError) -> list[Dict[str, Any]]:
        safe_errors = []
        for error in exc.errors():
            safe_error = dict(error)
            ctx = safe_error.get("ctx")
            if isinstance(ctx, dict):
                safe_error["ctx"] = {key: str(value) for key, value in ctx.items()}
            safe_errors.append(safe_error)
        return safe_errors

    @staticmethod
    def handoff_headers(payload: Dict[str, Any]) -> Dict[str, str]:
        return {
            "Idempotency-Key": str(payload.get("idempotency_key", "")),
            "X-Edge-Mode": str(payload.get("mode", "")),
            "X-Edge-Contract-Version": str(
                payload.get("contract_version", "edge.pulse.handoff.v1")
            ),
        }

    async def _post_with_feedback(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if not self._should_allow_request():
            if self.pulse_available:
                logger.debug("Circuit %s - POST %s suppressed", self.state.name, endpoint)
                return self.suppressed_handoff_feedback(endpoint, "circuit_open")
            logger.debug("Standalone mode - POST %s suppressed", endpoint)
            return self.suppressed_handoff_feedback(endpoint, "pulse_unavailable")

        url = f"{self.base_url}{endpoint}"
        start = time.time()
        try:
            response = await self._client.post(url, json=payload, headers=headers)
            edge_api_latency.labels(endpoint=endpoint).observe(time.time() - start)
            if response.status_code in (200, 201, 202, 204):
                edge_api_calls_total.labels(endpoint=endpoint, status="success").inc()
                self._record_success()
                return self.normalise_handoff_feedback(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_body=self._response_body(response),
                )

            edge_api_calls_total.labels(endpoint=endpoint, status="failure").inc()
            self._record_failure()
            logger.error("Pulse %s - HTTP %d", endpoint, response.status_code)
            return self.normalise_handoff_feedback(
                endpoint=endpoint,
                status_code=response.status_code,
                response_body=self._response_body(response),
            )
        except httpx.TimeoutException:
            edge_api_calls_total.labels(endpoint=endpoint, status="timeout").inc()
            self._record_failure()
            logger.error("Pulse %s timed out", endpoint)
            return {
                **self.normalise_handoff_feedback(endpoint, None),
                "reason": "pulse_timeout",
            }
        except Exception as exc:
            edge_api_calls_total.labels(endpoint=endpoint, status="error").inc()
            self._record_failure()
            logger.error("Pulse %s error: %s", endpoint, exc)
            return {
                **self.normalise_handoff_feedback(endpoint, None),
                "reason": exc.__class__.__name__,
            }

    async def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        if not self._should_allow_request():
            return None

        url = f"{self.base_url}{endpoint}"
        start = time.time()
        try:
            response = await self._client.get(url)
            edge_api_latency.labels(endpoint=endpoint).observe(time.time() - start)
            if response.status_code == 200:
                edge_api_calls_total.labels(endpoint=endpoint, status="success").inc()
                self._record_success()
                return response.json()
            if response.status_code == 404:
                self._record_success()
                return None
            edge_api_calls_total.labels(endpoint=endpoint, status="failure").inc()
            self._record_failure()
            return None
        except httpx.TimeoutException:
            edge_api_calls_total.labels(endpoint=endpoint, status="timeout").inc()
            self._record_failure()
            return None
        except Exception as exc:
            edge_api_calls_total.labels(endpoint=endpoint, status="error").inc()
            self._record_failure()
            logger.error("Pulse GET %s error: %s", endpoint, exc)
            return None

    async def send_decision(self, symbol: str, decision: str, **kwargs) -> bool:
        endpoint = f"/api/edge/tickers/{symbol}/decision"
        payload = {"symbol": symbol, "decision": decision, **kwargs}
        sent = await self._post(endpoint, payload)
        if (not sent) and self.pulse_available and self.state == CircuitState.OPEN:
            await self.retry_queue.enqueue(symbol, decision, endpoint, payload)
        if not sent and not self.pulse_available:
            logger.info("STANDALONE: would have sent %s → %s", decision, symbol)
        return sent

    async def send_handoff_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a structured autonomous handoff command to Pulse.

        The versioned `/api/edge/handoff` contract is the primary broker-control
        path. Set `PULSE_HANDOFF_ENDPOINT` to an empty string to force the
        legacy per-ticker decision fallback for older Pulse builds.
        """
        symbol = str(payload.get("symbol", "")).upper()
        if not symbol:
            logger.warning("Pulse handoff suppressed: missing symbol")
            return self.suppressed_handoff_feedback("/api/edge/handoff", "missing_symbol")

        try:
            handoff_request = PulseHandoffRequest.from_edge_payload(payload)
        except ValidationError as exc:
            logger.warning("Pulse handoff suppressed: invalid contract for %s: %s", symbol, exc)
            feedback = self.suppressed_handoff_feedback("/api/edge/handoff", "invalid_handoff_contract")
            feedback["validation_errors"] = self._json_safe_validation_errors(exc)
            return feedback

        payload = handoff_request.model_dump(mode="json", exclude_none=True)
        symbol = payload["symbol"]
        action = payload["action"]

        if not self.pulse_available or self.state == CircuitState.OPEN:
            logger.debug("Pulse handoff suppressed: Pulse unavailable/circuit open")
            reason = "pulse_unavailable" if not self.pulse_available else "circuit_open"
            return self.suppressed_handoff_feedback("/api/edge/handoff", reason)

        handoff_endpoint = os.getenv("PULSE_HANDOFF_ENDPOINT", "/api/edge/handoff").strip()
        if handoff_endpoint:
            if not handoff_endpoint.startswith("/"):
                handoff_endpoint = f"/{handoff_endpoint}"
            handoff_feedback = await self._post_with_feedback(
                handoff_endpoint,
                payload,
                headers=self.handoff_headers(payload),
            )
            if handoff_feedback.get("status") != "failed":
                return handoff_feedback
        else:
            handoff_feedback = None

        legacy_endpoint = f"/api/edge/tickers/{symbol}/decision"
        legacy_payload = self.legacy_handoff_payload(payload)
        legacy_sent = await self.send_decision(symbol, action, **legacy_payload)
        legacy_feedback = self.normalise_handoff_feedback(
            endpoint=legacy_endpoint,
            status_code=200 if legacy_sent else None,
            response_body={"accepted": legacy_sent},
            legacy_fallback=bool(handoff_endpoint),
        )
        if handoff_feedback is not None:
            legacy_feedback["primary_feedback"] = handoff_feedback
        return legacy_feedback

    async def send_signal(
        self,
        symbol: str,
        signal_score: float,
        action: str,
        confidence: float = 0.5,
        reason: str = "",
        risk_size: float = 0.0,
        stop_loss: float = 0.0,
    ) -> bool:
        """Send a full signal to Pulse with all decision parameters.
        
        This is the primary method for Edge → Pulse communication when
        making trading decisions.
        
        Args:
            symbol: Trading symbol (e.g., "NVDA", "AAPL")
            signal_score: Signal strength (-10 to +10)
            action: Trading action ("BUY", "SELL", "HOLD", "EMERGENCY_SELL")
            confidence: Confidence level (0.0 to 1.0)
            reason: Human-readable reason for the decision
            risk_size: Recommended position size (fraction of portfolio)
            stop_loss: Stop loss price if entering position
            
        Returns:
            True if signal was sent successfully, False otherwise
        """
        from shared.commands import SignalUpdateCommand
        
        # Create the command object for serialization
        cmd = SignalUpdateCommand(
            symbol=symbol.upper(),
            signal_score=signal_score,
            action=action,
            confidence=confidence,
            reason=reason,
            metadata={
                "risk_size": risk_size,
                "stop_loss": stop_loss,
                "source": "sentinel_edge",
            }
        )
        
        payload = cmd.model_dump()
        endpoint = f"/api/edge/signals/{symbol}"
        sent = await self._post(endpoint, payload)
        
        if sent:
            logger.info(
                f"📤 Signal sent to Pulse: {action} {symbol} | score={signal_score:.1f} conf={confidence:.2f}"
            )
        else:
            logger.warning(f"⚠️ Failed to send signal to Pulse: {action} {symbol}")
            
        return sent

    async def send_correlation_alert(
        self,
        cluster_id: str,
        correlated_symbols: list[str],
        cluster_strength: float,
        alert_type: str = "BREADTH_EXTREME",
        recommended_action: str = "REDUCE_SIZE",
    ) -> bool:
        """Send correlation cluster alert to Pulse for risk management.
        
        Called when correlation engine detects extreme market conditions
        (e.g., many symbols moving together, indicating systemic risk).
        
        Args:
            cluster_id: Unique identifier for the correlation cluster
            correlated_symbols: List of symbols in the cluster
            cluster_strength: Strength of correlation (0.0 to 1.0)
            alert_type: Type of alert ("CLUSTER_FORMED", "CLUSTER_BROKE", "BREADTH_EXTREME")
            recommended_action: Recommended action ("REDUCE_SIZE", "CLOSE_ALL", "HOLD")
            
        Returns:
            True if alert was sent successfully
        """
        from shared.commands import CorrelationAlertCommand
        
        cmd = CorrelationAlertCommand(
            symbol=correlated_symbols[0] if correlated_symbols else "MARKET",
            correlated_symbols=correlated_symbols,
            cluster_strength=cluster_strength,
            recommended_action=recommended_action,
            metadata={
                "cluster_id": cluster_id,
                "alert_type": alert_type,
            }
        )
        
        payload = cmd.model_dump()
        endpoint = "/api/alerts/correlation"
        return await self._post(endpoint, payload)

    async def send_emergency_exit(
        self,
        symbol: str,
        reason: str = "",
        immediate: bool = True,
    ) -> bool:
        """Send emergency exit command to Pulse.
        
        This is the fastest way to force-close a position when risk
        parameters are breached.
        
        Args:
            symbol: Symbol to exit
            reason: Reason for emergency exit
            immediate: If True, bypasses retry queue and goes straight to execution
            
        Returns:
            True if command was sent
        """
        logger.critical(f"🚨 EMERGENCY EXIT: {symbol} | reason: {reason}")
        return await self.send_decision(
            symbol,
            "emergency_exit",
            reason=reason,
            immediate=immediate,
        )

    # ====================== PULSE STATUS METHODS ======================

    async def get_account_status(self) -> Optional[Dict[str, Any]]:
        """Get account status from Pulse (buying power, equity, etc.).
        
        Returns:
            Dict with account info or None if unavailable
        """
        data = await self._get("/api/edge/account/status")
        if data:
            logger.debug(f"Account status: equity={data.get('total_equity')}")
        return data

    async def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all open positions from Pulse.
        
        Returns:
            Dict mapping symbol -> position data
        """
        data = await self._get("/api/edge/account/status")
        if isinstance(data, dict):
            positions = data.get("positions", [])
            if isinstance(positions, list):
                return {
                    str(position.get("symbol", "")).upper(): position
                    for position in positions
                    if isinstance(position, dict) and position.get("symbol")
                }
        return {}

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol from Pulse."""
        data = await self._get(f"/api/edge/positions/{symbol}")
        if data is None:
            return None

        return {
            "has_position": bool(data.get("has_position", data.get("active", False))),
            "pnl": float(data.get("pnl", data.get("unrealized_pnl", 0.0))),
            "pnl_pct": float(data.get("pnl_pct", data.get("unrealized_pnl_pct", 0.0))),
            "trailing_enabled": bool(data.get("trailing_enabled", data.get("trailing_stop_enabled", False))),
            "trailing_percent": data.get("trailing_percent"),
            "entry_price": data.get("entry_price"),
            "drawdown_pct": float(data.get("drawdown_pct", 0.0)),
        }

    async def health_check_detailed(self) -> Dict[str, Any]:
        """Perform detailed health check of Pulse connection.
        
        Returns:
            Dict with connection state, latency, and last successful contact
        """
        return {
            "available": self.pulse_available,
            "circuit_state": self.state.name,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "retry_queue_size": self.retry_queue.stats().get("pending", 0),
        }

    async def enable_trailing_stop(self, symbol: str, trailing_percent: float) -> bool:
        return await self.send_decision(symbol, "enable_trailing_stop", trailing_percent=trailing_percent)

    async def stop_buying(self, symbol: str) -> bool:
        return await self.send_decision(symbol, "stop_buying")

    async def emergency_stop(self, symbol: str) -> bool:
        return await self.send_decision(symbol, "emergency_stop")

    async def get_tickers(self) -> list:
        data = await self._get("/api/edge/tickers")
        return data if isinstance(data, list) else []

    def queue_stats(self) -> Dict[str, Any]:
        return self.retry_queue.stats()

    async def queue_snapshot(self, limit: int = 100) -> list[Dict[str, Any]]:
        return await self.retry_queue.snapshot(limit=limit)

    async def aclose(self) -> None:
        await self.retry_queue.flush_to_file()
        await self.retry_queue.stop()
        await self._client.aclose()
