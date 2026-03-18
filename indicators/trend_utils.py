"""
Trend Line and Trend Analysis Indicators.
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .common import detect_swing_high, detect_swing_low, calculate_ema


class TrendDirection(Enum):
    """Trend direction."""
    UP = 1
    DOWN = -1
    SIDEWAYS = 0


@dataclass
class TrendLine:
    """Represents a trend line."""
    start_price: float
    end_price: float
    start_index: int
    end_index: int
    slope: float
    is_resistance: bool  # True for resistance, False for support
    touches: int
    valid: bool = True


@dataclass
class TrendBreak:
    """Represents a trend line breakout."""
    trend_line: TrendLine
    break_price: float
    break_index: int
    is_bullish: bool  # True if breaking above resistance


class TrendAnalyzer:
    """
    Trend line detection and analysis.

    Features:
    - Automatic trend line detection
    - Trend line break detection
    - Trauma indicator (EMA-based trend filter)
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        min_touches: int = 3,
        break_threshold: float = 0.001  # 0.1% for confirmation
    ):
        """
        Initialize trend analyzer.

        Args:
            swing_lookback: Bars for swing detection
            min_touches: Minimum touches for valid trend line
            break_threshold: Price threshold for break confirmation
        """
        self.swing_lookback = swing_lookback
        self.min_touches = min_touches
        self.break_threshold = break_threshold

        self._resistance_lines: List[TrendLine] = []
        self._support_lines: List[TrendLine] = []

    def analyze(self, data: pd.DataFrame) -> None:
        """
        Run full trend analysis.

        Args:
            data: OHLCV DataFrame
        """
        self._detect_trend_lines(data)

    def _detect_trend_lines(self, data: pd.DataFrame, lookback: int = 50) -> None:
        """Detect resistance and support trend lines."""
        self._resistance_lines = []
        self._support_lines = []

        if len(data) < lookback:
            return

        recent = data.tail(lookback).reset_index(drop=True)

        # Find swing points
        swing_highs = []
        swing_lows = []

        for i in range(self.swing_lookback, len(recent) - self.swing_lookback):
            # Swing high
            is_highest = all(
                recent.iloc[i]["high"] > recent.iloc[i - j]["high"] and
                recent.iloc[i]["high"] > recent.iloc[i + j]["high"]
                for j in range(1, self.swing_lookback + 1)
            )
            if is_highest:
                swing_highs.append((i, recent.iloc[i]["high"]))

            # Swing low
            is_lowest = all(
                recent.iloc[i]["low"] < recent.iloc[i - j]["low"] and
                recent.iloc[i]["low"] < recent.iloc[i + j]["low"]
                for j in range(1, self.swing_lookback + 1)
            )
            if is_lowest:
                swing_lows.append((i, recent.iloc[i]["low"]))

        # Build resistance lines from swing highs
        if len(swing_highs) >= 2:
            for i in range(len(swing_highs) - 1):
                for j in range(i + 1, len(swing_highs)):
                    line = self._create_trend_line(
                        swing_highs[i], swing_highs[j], recent, is_resistance=True
                    )
                    if line and line.touches >= self.min_touches:
                        self._resistance_lines.append(line)

        # Build support lines from swing lows
        if len(swing_lows) >= 2:
            for i in range(len(swing_lows) - 1):
                for j in range(i + 1, len(swing_lows)):
                    line = self._create_trend_line(
                        swing_lows[i], swing_lows[j], recent, is_resistance=False
                    )
                    if line and line.touches >= self.min_touches:
                        self._support_lines.append(line)

    def _create_trend_line(
        self,
        point1: Tuple[int, float],
        point2: Tuple[int, float],
        data: pd.DataFrame,
        is_resistance: bool
    ) -> Optional[TrendLine]:
        """Create a trend line between two points and count touches."""
        idx1, price1 = point1
        idx2, price2 = point2

        if idx2 <= idx1:
            return None

        # Calculate slope
        slope = (price2 - price1) / (idx2 - idx1)

        # Count touches
        touches = 2  # The two anchor points
        touch_threshold = abs(price2 - price1) * 0.02  # 2% tolerance

        for i in range(idx1 + 1, min(idx2, len(data))):
            line_price = price1 + slope * (i - idx1)

            if is_resistance:
                if abs(data.iloc[i]["high"] - line_price) < touch_threshold:
                    touches += 1
            else:
                if abs(data.iloc[i]["low"] - line_price) < touch_threshold:
                    touches += 1

        return TrendLine(
            start_price=price1,
            end_price=price2,
            start_index=idx1,
            end_index=idx2,
            slope=slope,
            is_resistance=is_resistance,
            touches=touches
        )

    def detect_resistance_break(
        self,
        data: pd.DataFrame,
        lookback: int = 50
    ) -> Optional[TrendBreak]:
        """
        Detect a resistance trend line breakout.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to analyze

        Returns:
            TrendBreak if breakout detected, None otherwise
        """
        self._detect_trend_lines(data, lookback)

        if not self._resistance_lines:
            return None

        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2]

        for line in self._resistance_lines:
            # Calculate current trend line level
            bars_since_start = len(data) - 1 - (len(data) - lookback + line.start_index)
            current_line_price = line.start_price + line.slope * bars_since_start

            # Check for breakout
            if (prev_bar["close"] <= current_line_price * (1 + self.break_threshold) and
                current_bar["close"] > current_line_price * (1 + self.break_threshold)):
                return TrendBreak(
                    trend_line=line,
                    break_price=current_bar["close"],
                    break_index=len(data) - 1,
                    is_bullish=True
                )

        return None

    def detect_support_break(
        self,
        data: pd.DataFrame,
        lookback: int = 50
    ) -> Optional[TrendBreak]:
        """
        Detect a support trend line breakdown.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to analyze

        Returns:
            TrendBreak if breakdown detected, None otherwise
        """
        self._detect_trend_lines(data, lookback)

        if not self._support_lines:
            return None

        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2]

        for line in self._support_lines:
            # Calculate current trend line level
            bars_since_start = len(data) - 1 - (len(data) - lookback + line.start_index)
            current_line_price = line.start_price + line.slope * bars_since_start

            # Check for breakdown
            if (prev_bar["close"] >= current_line_price * (1 - self.break_threshold) and
                current_bar["close"] < current_line_price * (1 - self.break_threshold)):
                return TrendBreak(
                    trend_line=line,
                    break_price=current_bar["close"],
                    break_index=len(data) - 1,
                    is_bullish=False
                )

        return None

    def calculate_trauma(
        self,
        data: pd.DataFrame,
        period: int = 21,
        column: str = "close"
    ) -> pd.Series:
        """
        Calculate Trauma indicator (EMA-based trend filter).

        Price above Trauma = Bullish bias
        Price below Trauma = Bearish bias

        Args:
            data: OHLCV DataFrame
            period: EMA period
            column: Column to use

        Returns:
            Trauma (EMA) series
        """
        return calculate_ema(data, period, column)

    def is_above_trauma(
        self,
        data: pd.DataFrame,
        period: int = 21
    ) -> bool:
        """
        Check if price is above Trauma indicator.

        Args:
            data: OHLCV DataFrame
            period: EMA period

        Returns:
            True if price is above Trauma
        """
        trauma = self.calculate_trauma(data, period)
        return data.iloc[-1]["close"] > trauma.iloc[-1]

    def is_below_trauma(
        self,
        data: pd.DataFrame,
        period: int = 21
    ) -> bool:
        """
        Check if price is below Trauma indicator.

        Args:
            data: OHLCV DataFrame
            period: EMA period

        Returns:
            True if price is below Trauma
        """
        trauma = self.calculate_trauma(data, period)
        return data.iloc[-1]["close"] < trauma.iloc[-1]

    def get_trend_direction(
        self,
        data: pd.DataFrame,
        short_period: int = 10,
        long_period: int = 30
    ) -> TrendDirection:
        """
        Determine trend direction using EMAs.

        Args:
            data: OHLCV DataFrame
            short_period: Fast EMA period
            long_period: Slow EMA period

        Returns:
            Trend direction
        """
        short_ema = calculate_ema(data, short_period)
        long_ema = calculate_ema(data, long_period)

        short_val = short_ema.iloc[-1]
        long_val = long_ema.iloc[-1]

        # Check slope of short EMA
        short_slope = short_ema.iloc[-1] - short_ema.iloc[-5] if len(short_ema) >= 5 else 0

        if short_val > long_val and short_slope > 0:
            return TrendDirection.UP
        elif short_val < long_val and short_slope < 0:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS

    def get_resistance_lines(self) -> List[TrendLine]:
        """Get detected resistance lines."""
        return self._resistance_lines.copy()

    def get_support_lines(self) -> List[TrendLine]:
        """Get detected support lines."""
        return self._support_lines.copy()
