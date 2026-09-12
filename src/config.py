"""Configuration loading, path resolution and logging setup.

Every module imports ``load_config`` / ``get_logger`` from here so that the
whole pipeline shares one source of truth and one log format.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

# Project root = parent of the ``src`` directory.
ROOT = Path(__file__).resolve().parents[1]

PATHS = {
    "root": ROOT,
    "config": ROOT / "config.yaml",
    "data_raw": ROOT / "data" / "raw",
    "data_processed": ROOT / "data" / "processed",
    "outputs": ROOT / "outputs",
    "tables": ROOT / "outputs" / "tables",
    "figures": ROOT / "outputs" / "figures",
    "models": ROOT / "models",
    "sql": ROOT / "sql",
}


@lru_cache(maxsize=1)
def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    """Load ``config.yaml`` once and cache it."""
    cfg_path = Path(path) if path else PATHS["config"]
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    _validate(cfg)
    return cfg


def _validate(cfg: Dict[str, Any]) -> None:
    """Fail fast on internally inconsistent configuration."""
    w = cfg["scorecard"]["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9, "scorecard weights must sum to 1.0"
    rw = cfg["risk"]["weights"]
    assert abs(sum(rw.values()) - 1.0) < 1e-9, "risk weights must sum to 1.0"
    nw = cfg["negotiation"]["weights"]
    assert abs(sum(nw.values()) - 1.0) < 1e-9, "negotiation weights must sum to 1.0"
    caps = cfg["savings"]["capture_rates"]
    assert caps["conservative"] <= caps["base"] <= caps["aggressive"], \
        "capture rates must be ordered conservative <= base <= aggressive"


def ensure_dirs() -> None:
    for key in ("data_raw", "data_processed", "outputs", "tables", "figures", "models"):
        PATHS[key].mkdir(parents=True, exist_ok=True)


_LOG_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _LOG_CONFIGURED
    if not _LOG_CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
            datefmt="%H:%M:%S",
        )
        _LOG_CONFIGURED = True
    return logging.getLogger(name)


def fmt_money(x: float, cfg: Dict[str, Any] | None = None) -> str:
    """Human-readable money formatting ($1.2M / $850.0K)."""
    sym = (cfg or load_config())["project"]["currency_symbol"]
    ax = abs(x)
    if ax >= 1e9:
        return f"{sym}{x/1e9:.2f}B"
    if ax >= 1e6:
        return f"{sym}{x/1e6:.2f}M"
    if ax >= 1e3:
        return f"{sym}{x/1e3:.1f}K"
    return f"{sym}{x:,.0f}"
