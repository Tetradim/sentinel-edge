"""Simulation Lab feature gate and experiment discovery contract."""
import os
from dataclasses import dataclass
from typing import Any, Dict


SIMULATION_LAB_ENV_FLAG = "EDGE_SIMULATION_LAB_ENABLED"
SIMULATION_LAB_STATUS_VERSION = "edge.simulation_lab.status.v1"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SimulationLabExperiment:
    """Roadmap experiment metadata surfaced before runnable lab endpoints exist."""

    id: str
    label: str
    capability: str
    status: str = "planned"
    runnable: bool = False

    def to_status(self, lab_enabled: bool) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "capability": self.capability,
            "status": self.status,
            "state": "visible" if lab_enabled else "hidden",
            "runnable": self.runnable,
        }


_EXPERIMENTS = (
    SimulationLabExperiment(
        id="orb_backtest",
        label="ORB backtesting",
        capability="Replay ORB session decisions independently from live automation.",
    ),
    SimulationLabExperiment(
        id="buying_power_allocation",
        label="Buying-power allocation experiments",
        capability="Compare capital-allocation assumptions before promotion to automation settings.",
    ),
    SimulationLabExperiment(
        id="stop_trailing_dca",
        label="Stop vs trailing-stop vs DCA comparisons",
        capability="Compare exit and averaging tactics against the same historical trade stream.",
    ),
)


def _simulation_lab_enabled() -> bool:
    value = os.getenv(SIMULATION_LAB_ENV_FLAG, "")
    return value.strip().lower() in _TRUTHY_VALUES


def simulation_lab_status() -> Dict[str, Any]:
    """Return the default-off Simulation Lab discovery payload."""
    enabled = _simulation_lab_enabled()
    return {
        "schema_version": SIMULATION_LAB_STATUS_VERSION,
        "enabled": enabled,
        "default_hidden": not enabled,
        "env_flag": SIMULATION_LAB_ENV_FLAG,
        "experiments": [experiment.to_status(enabled) for experiment in _EXPERIMENTS],
    }
