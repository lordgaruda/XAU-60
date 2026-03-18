"""
Common technical indicators using pandas/numpy and ta library.
"""
import pandas as pd
import numpy as np
from typing import Optional
import ta


def calculate_rsi(data: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        data: DataFrame with price data
        period: RSI period
        column: Column to use for calculation

    Returns:
        RSI series
    """
    return ta.momentum.RSIIndicator(data[column], window=period).rsi()


def calculate_ema(data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).

    Args:
        data: DataFrame with price data
        period: EMA period
        column: Column to use

    Returns:
        EMA series
    """
    return ta.trend.EMAIndicator(data[column], window=period).ema_indicator()


def calculate_sma(data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).

    Args:
        data: DataFrame with price data
        period: SMA period
        column: Column to use

    Returns:
        SMA series
    """
    return ta.trend.SMAIndicator(data[column], window=period).sma_indicator()


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).

    Args:
        data: DataFrame with OHLC data
        period: ATR period

    Returns:
        ATR series
    """
    return ta.volatility.AverageTrueRange(
        data["high"], data["low"], data["close"], window=period
    ).average_true_range()


def calculate_bollinger_bands(
    data: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close"
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.

    Args:
        data: DataFrame with price data
        period: MA period
        std_dev: Standard deviation multiplier
        column: Column to use

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    bb = ta.volatility.BollingerBands(data[column], window=period, window_dev=std_dev)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def calculate_macd(
    data: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close"
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        data: DataFrame with price data
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period
        column: Column to use

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    macd = ta.trend.MACD(data[column], window_fast=fast, window_slow=slow, window_sign=signal)
    return macd.macd(), macd.macd_signal(), macd.macd_diff()


def calculate_stochastic(
    data: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3
) -> tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator.

    Args:
        data: DataFrame with OHLC data
        k_period: %K period
        d_period: %D period

    Returns:
        Tuple of (%K, %D)
    """
    stoch = ta.momentum.StochasticOscillator(
        data["high"], data["low"], data["close"],
        window=k_period, smooth_window=d_period
    )
    return stoch.stoch(), stoch.stoch_signal()


def calculate_adx(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX).

    Args:
        data: DataFrame with OHLC data
        period: ADX period

    Returns:
        ADX series
    """
    return ta.trend.ADXIndicator(
        data["high"], data["low"], data["close"], window=period
    ).adx()


def calculate_williams_r(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Williams %R.

    Args:
        data: DataFrame with OHLC data
        period: Period

    Returns:
        Williams %R series
    """
    return ta.momentum.WilliamsRIndicator(
        data["high"], data["low"], data["close"], lbp=period
    ).williams_r()


def calculate_cci(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Commodity Channel Index (CCI).

    Args:
        data: DataFrame with OHLC data
        period: CCI period

    Returns:
        CCI series
    """
    return ta.trend.CCIIndicator(
        data["high"], data["low"], data["close"], window=period
    ).cci()


def detect_swing_high(
    data: pd.DataFrame,
    lookback: int = 5,
    column: str = "high"
) -> pd.Series:
    """
    Detect swing highs.

    Args:
        data: DataFrame with price data
        lookback: Bars to look back
        column: Column to use

    Returns:
        Boolean series where True indicates swing high
    """
    highs = data[column]
    swing_highs = pd.Series(False, index=data.index)

    for i in range(lookback, len(highs) - lookback):
        is_highest = True
        for j in range(1, lookback + 1):
            if highs.iloc[i] <= highs.iloc[i - j] or highs.iloc[i] <= highs.iloc[i + j]:
                is_highest = False
                break
        swing_highs.iloc[i] = is_highest

    return swing_highs


def detect_swing_low(
    data: pd.DataFrame,
    lookback: int = 5,
    column: str = "low"
) -> pd.Series:
    """
    Detect swing lows.

    Args:
        data: DataFrame with price data
        lookback: Bars to look back
        column: Column to use

    Returns:
        Boolean series where True indicates swing low
    """
    lows = data[column]
    swing_lows = pd.Series(False, index=data.index)

    for i in range(lookback, len(lows) - lookback):
        is_lowest = True
        for j in range(1, lookback + 1):
            if lows.iloc[i] >= lows.iloc[i - j] or lows.iloc[i] >= lows.iloc[i + j]:
                is_lowest = False
                break
        swing_lows.iloc[i] = is_lowest

    return swing_lows


def calculate_pivot_points(
    high: float,
    low: float,
    close: float
) -> dict[str, float]:
    """
    Calculate classic pivot points.

    Args:
        high: Previous period high
        low: Previous period low
        close: Previous period close

    Returns:
        Dictionary with P, R1, R2, R3, S1, S2, S3
    """
    pivot = (high + low + close) / 3

    return {
        "P": pivot,
        "R1": 2 * pivot - low,
        "R2": pivot + (high - low),
        "R3": high + 2 * (pivot - low),
        "S1": 2 * pivot - high,
        "S2": pivot - (high - low),
        "S3": low - 2 * (high - pivot),
    }


def is_bullish_candle(open_price: float, close_price: float) -> bool:
    """Check if candle is bullish."""
    return close_price > open_price


def is_bearish_candle(open_price: float, close_price: float) -> bool:
    """Check if candle is bearish."""
    return close_price < open_price


def calculate_candle_body(open_price: float, close_price: float) -> float:
    """Calculate candle body size."""
    return abs(close_price - open_price)


def calculate_upper_wick(high: float, open_price: float, close_price: float) -> float:
    """Calculate upper wick size."""
    return high - max(open_price, close_price)


def calculate_lower_wick(low: float, open_price: float, close_price: float) -> float:
    """Calculate lower wick size."""
    return min(open_price, close_price) - low
