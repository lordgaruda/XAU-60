"""
Common helper functions.
"""
import platform
from typing import Dict, Any

# MT5 timeframe constants (defined locally to avoid import issues)
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 60
TIMEFRAME_H4 = 240
TIMEFRAME_D1 = 1440
TIMEFRAME_W1 = 10080
TIMEFRAME_MN1 = 43200

# Timeframe mapping
TIMEFRAME_MAP = {
    "M1": TIMEFRAME_M1,
    "M5": TIMEFRAME_M5,
    "M15": TIMEFRAME_M15,
    "M30": TIMEFRAME_M30,
    "H1": TIMEFRAME_H1,
    "H4": TIMEFRAME_H4,
    "D1": TIMEFRAME_D1,
    "W1": TIMEFRAME_W1,
    "MN1": TIMEFRAME_MN1,
}


def timeframe_to_mt5(timeframe: str) -> int:
    """
    Convert timeframe string to MT5 constant.

    Args:
        timeframe: Timeframe string (M1, M5, M15, M30, H1, H4, D1, W1, MN1)

    Returns:
        MT5 timeframe constant
    """
    return TIMEFRAME_MAP.get(timeframe.upper(), TIMEFRAME_M15)


def pips_to_price(symbol: str, pips: float, point: float = 0.00001) -> float:
    """
    Convert pips to price distance.

    Args:
        symbol: Trading symbol
        pips: Number of pips
        point: Point value (default for forex)

    Returns:
        Price distance
    """
    # Gold and JPY pairs have different pip calculations
    if "XAU" in symbol or "GOLD" in symbol:
        return pips * 0.1  # 1 pip = $0.10 for gold
    elif "JPY" in symbol:
        return pips * 0.01  # 1 pip = 0.01 for JPY pairs
    else:
        return pips * 0.0001  # Standard 1 pip = 0.0001


def price_to_pips(symbol: str, price_distance: float) -> float:
    """
    Convert price distance to pips.

    Args:
        symbol: Trading symbol
        price_distance: Price distance

    Returns:
        Number of pips
    """
    if "XAU" in symbol or "GOLD" in symbol:
        return price_distance / 0.1
    elif "JPY" in symbol:
        return price_distance / 0.01
    else:
        return price_distance / 0.0001


def format_price(symbol: str, price: float, digits: int = 5) -> str:
    """
    Format price with appropriate decimal places.

    Args:
        symbol: Trading symbol
        price: Price to format
        digits: Number of decimal places

    Returns:
        Formatted price string
    """
    return f"{price:.{digits}f}"


def calculate_lot_value(symbol: str, lot_size: float, contract_size: float = 100000) -> float:
    """
    Calculate the value of a position.

    Args:
        symbol: Trading symbol
        lot_size: Position size in lots
        contract_size: Contract size (default 100000 for forex)

    Returns:
        Position value
    """
    return lot_size * contract_size


def is_trading_session(hour: int, start_hour: int = 8, end_hour: int = 18) -> bool:
    """
    Check if current hour is within trading session.

    Args:
        hour: Current hour (0-23)
        start_hour: Session start hour
        end_hour: Session end hour

    Returns:
        True if within trading session
    """
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    else:
        # Handle overnight sessions
        return hour >= start_hour or hour <= end_hour


def get_session_name(hour: int) -> str:
    """
    Get the trading session name based on hour (UTC).

    Args:
        hour: Hour in UTC

    Returns:
        Session name (Asian, London, New York, Overlap)
    """
    if 0 <= hour < 8:
        return "Asian"
    elif 8 <= hour < 13:
        return "London"
    elif 13 <= hour < 17:
        return "Overlap"  # London/NY overlap
    elif 17 <= hour < 22:
        return "New York"
    else:
        return "Asian"
