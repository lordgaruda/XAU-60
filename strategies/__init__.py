"""
Trading strategies module.

Available Strategies:
- SMCScalper: Smart Money Concepts scalping with CHoCH, FVG, and Order Blocks
- TrendBreakTrauma: Trend line break with EMA filter and RSI exits
- CRTStrategy: Candle Range Theory + Time-Based Strategy with killzone entries
"""

from .smc_scalper import SMCScalper
from .trend_break_trauma import TrendBreakTrauma
from .crt_tbs import CRTStrategy

__all__ = [
    "SMCScalper",
    "TrendBreakTrauma",
    "CRTStrategy",
]

# Strategy registry for auto-discovery
STRATEGY_REGISTRY = {
    "SMC Scalper": SMCScalper,
    "Trend Break Trauma": TrendBreakTrauma,
    "CRT TBS": CRTStrategy,
}


def get_strategy(name: str):
    """Get strategy class by name."""
    return STRATEGY_REGISTRY.get(name)


def list_strategies():
    """List all available strategies."""
    return list(STRATEGY_REGISTRY.keys())


def create_strategy(name: str, config: dict = None):
    """Create and initialize a strategy instance."""
    strategy_class = get_strategy(name)
    if strategy_class is None:
        raise ValueError(f"Unknown strategy: {name}")

    strategy = strategy_class()
    if config:
        strategy.initialize(config)
    return strategy
