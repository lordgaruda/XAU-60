"""
Smart Money Concepts (SMC) Indicators and Analysis.
Converted from MQL5 SMC_Utils.mqh
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .common import detect_swing_high, detect_swing_low, calculate_atr


class StructureType(Enum):
    """Market structure type."""
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class SwingPoint:
    """Represents a swing high or low."""
    price: float
    time: pd.Timestamp
    index: int
    is_high: bool  # True for swing high, False for swing low


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (FVG)."""
    upper_price: float
    lower_price: float
    mid_price: float
    is_bullish: bool
    start_index: int
    time: pd.Timestamp
    filled: bool = False


@dataclass
class OrderBlock:
    """Represents an Order Block."""
    upper_price: float
    lower_price: float
    trigger_price: float  # Price at which displacement occurred
    is_bullish: bool
    strength: int  # 1-5 scale
    start_index: int
    time: pd.Timestamp
    tested: bool = False


@dataclass
class LiquidityZone:
    """Represents a liquidity zone."""
    level: float
    touch_count: int
    is_resistance: bool  # True for resistance, False for support
    swept: bool = False


class SMCAnalyzer:
    """
    Smart Money Concepts analyzer.

    Features:
    - Change of Character (CHoCH) detection
    - Break of Structure (BOS) detection
    - Fair Value Gap (FVG) detection
    - Order Block identification
    - Liquidity zone detection
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        fvg_min_pips: float = 5.0,
        ob_displacement_factor: float = 2.0,
        point: float = 0.1  # For gold
    ):
        """
        Initialize SMC analyzer.

        Args:
            swing_lookback: Bars to look back for swing detection
            fvg_min_pips: Minimum FVG size in pips
            ob_displacement_factor: ATR multiplier for order block detection
            point: Point value for pip calculation
        """
        self.swing_lookback = swing_lookback
        self.fvg_min_pips = fvg_min_pips
        self.ob_displacement_factor = ob_displacement_factor
        self.point = point

        self._swing_highs: List[SwingPoint] = []
        self._swing_lows: List[SwingPoint] = []
        self._fvgs: List[FairValueGap] = []
        self._order_blocks: List[OrderBlock] = []

    def analyze(self, data: pd.DataFrame) -> None:
        """
        Run full SMC analysis on data.

        Args:
            data: OHLCV DataFrame
        """
        self._detect_swing_points(data)
        self._detect_fvgs(data)
        self._detect_order_blocks(data)

    def _detect_swing_points(self, data: pd.DataFrame) -> None:
        """Detect all swing highs and lows."""
        self._swing_highs = []
        self._swing_lows = []

        swing_highs = detect_swing_high(data, self.swing_lookback)
        swing_lows = detect_swing_low(data, self.swing_lookback)

        for i, is_high in enumerate(swing_highs):
            if is_high:
                self._swing_highs.append(SwingPoint(
                    price=data.iloc[i]["high"],
                    time=data.iloc[i]["time"],
                    index=i,
                    is_high=True
                ))

        for i, is_low in enumerate(swing_lows):
            if is_low:
                self._swing_lows.append(SwingPoint(
                    price=data.iloc[i]["low"],
                    time=data.iloc[i]["time"],
                    index=i,
                    is_high=False
                ))

    def detect_bullish_choch(
        self,
        data: pd.DataFrame,
        lookback: int = 50
    ) -> Optional[Tuple[int, float]]:
        """
        Detect Bullish Change of Character (CHoCH).
        CHoCH = Price makes higher high after a series of lower lows.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to analyze

        Returns:
            Tuple of (bar_index, price) where CHoCH occurred, or None
        """
        if len(data) < lookback:
            return None

        recent = data.tail(lookback)
        swing_lows = []
        swing_highs = []

        # Find recent swing points
        for i in range(self.swing_lookback, len(recent) - self.swing_lookback):
            idx = len(data) - lookback + i

            # Check for swing low
            is_lowest = True
            for j in range(1, self.swing_lookback + 1):
                if recent.iloc[i]["low"] >= recent.iloc[i - j]["low"] or \
                   recent.iloc[i]["low"] >= recent.iloc[i + j]["low"]:
                    is_lowest = False
                    break
            if is_lowest:
                swing_lows.append((idx, recent.iloc[i]["low"]))

            # Check for swing high
            is_highest = True
            for j in range(1, self.swing_lookback + 1):
                if recent.iloc[i]["high"] <= recent.iloc[i - j]["high"] or \
                   recent.iloc[i]["high"] <= recent.iloc[i + j]["high"]:
                    is_highest = False
                    break
            if is_highest:
                swing_highs.append((idx, recent.iloc[i]["high"]))

        # Need at least 2 swing lows and 1 swing high
        if len(swing_lows) < 2 or len(swing_highs) < 1:
            return None

        # Check for lower lows followed by higher high break
        for i in range(len(swing_lows) - 1):
            if swing_lows[i + 1][1] < swing_lows[i][1]:  # Lower low
                # Find swing high between these lows
                intermediate_highs = [
                    h for h in swing_highs
                    if swing_lows[i][0] < h[0] < swing_lows[i + 1][0]
                ]

                if intermediate_highs:
                    last_high = max(intermediate_highs, key=lambda x: x[0])

                    # Check if current price broke above this high
                    current_high = data.iloc[-1]["high"]
                    if current_high > last_high[1]:
                        return (len(data) - 1, last_high[1])

        return None

    def detect_bearish_choch(
        self,
        data: pd.DataFrame,
        lookback: int = 50
    ) -> Optional[Tuple[int, float]]:
        """
        Detect Bearish Change of Character (CHoCH).
        CHoCH = Price makes lower low after a series of higher highs.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to analyze

        Returns:
            Tuple of (bar_index, price) where CHoCH occurred, or None
        """
        if len(data) < lookback:
            return None

        recent = data.tail(lookback)
        swing_lows = []
        swing_highs = []

        # Find recent swing points
        for i in range(self.swing_lookback, len(recent) - self.swing_lookback):
            idx = len(data) - lookback + i

            # Check for swing low
            is_lowest = True
            for j in range(1, self.swing_lookback + 1):
                if recent.iloc[i]["low"] >= recent.iloc[i - j]["low"] or \
                   recent.iloc[i]["low"] >= recent.iloc[i + j]["low"]:
                    is_lowest = False
                    break
            if is_lowest:
                swing_lows.append((idx, recent.iloc[i]["low"]))

            # Check for swing high
            is_highest = True
            for j in range(1, self.swing_lookback + 1):
                if recent.iloc[i]["high"] <= recent.iloc[i - j]["high"] or \
                   recent.iloc[i]["high"] <= recent.iloc[i + j]["high"]:
                    is_highest = False
                    break
            if is_highest:
                swing_highs.append((idx, recent.iloc[i]["high"]))

        # Need at least 2 swing highs and 1 swing low
        if len(swing_highs) < 2 or len(swing_lows) < 1:
            return None

        # Check for higher highs followed by lower low break
        for i in range(len(swing_highs) - 1):
            if swing_highs[i + 1][1] > swing_highs[i][1]:  # Higher high
                # Find swing low between these highs
                intermediate_lows = [
                    l for l in swing_lows
                    if swing_highs[i][0] < l[0] < swing_highs[i + 1][0]
                ]

                if intermediate_lows:
                    last_low = max(intermediate_lows, key=lambda x: x[0])

                    # Check if current price broke below this low
                    current_low = data.iloc[-1]["low"]
                    if current_low < last_low[1]:
                        return (len(data) - 1, last_low[1])

        return None

    def _detect_fvgs(self, data: pd.DataFrame) -> None:
        """Detect all Fair Value Gaps."""
        self._fvgs = []
        min_gap = self.fvg_min_pips * self.point * 10

        for i in range(2, len(data)):
            bar0 = data.iloc[i]      # Current bar
            bar1 = data.iloc[i - 1]  # Previous bar
            bar2 = data.iloc[i - 2]  # Bar before that

            # Bullish FVG: gap between bar2 high and bar0 low
            if bar0["low"] > bar2["high"]:
                gap_size = bar0["low"] - bar2["high"]
                if gap_size >= min_gap:
                    self._fvgs.append(FairValueGap(
                        upper_price=bar0["low"],
                        lower_price=bar2["high"],
                        mid_price=(bar0["low"] + bar2["high"]) / 2,
                        is_bullish=True,
                        start_index=i,
                        time=bar1["time"]
                    ))

            # Bearish FVG: gap between bar0 high and bar2 low
            if bar0["high"] < bar2["low"]:
                gap_size = bar2["low"] - bar0["high"]
                if gap_size >= min_gap:
                    self._fvgs.append(FairValueGap(
                        upper_price=bar2["low"],
                        lower_price=bar0["high"],
                        mid_price=(bar2["low"] + bar0["high"]) / 2,
                        is_bullish=False,
                        start_index=i,
                        time=bar1["time"]
                    ))

    def detect_bullish_fvg(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> Optional[FairValueGap]:
        """
        Find the most recent unfilled bullish FVG.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to look back

        Returns:
            Most recent unfilled bullish FVG or None
        """
        self._detect_fvgs(data.tail(lookback + 3))

        bullish_fvgs = [f for f in self._fvgs if f.is_bullish and not f.filled]

        if bullish_fvgs:
            # Return the most recent one
            return bullish_fvgs[-1]
        return None

    def detect_bearish_fvg(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> Optional[FairValueGap]:
        """
        Find the most recent unfilled bearish FVG.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to look back

        Returns:
            Most recent unfilled bearish FVG or None
        """
        self._detect_fvgs(data.tail(lookback + 3))

        bearish_fvgs = [f for f in self._fvgs if not f.is_bullish and not f.filled]

        if bearish_fvgs:
            return bearish_fvgs[-1]
        return None

    def _detect_order_blocks(self, data: pd.DataFrame) -> None:
        """Detect Order Blocks with displacement."""
        self._order_blocks = []
        atr = calculate_atr(data, 14)

        for i in range(2, len(data) - 1):
            current = data.iloc[i]
            next_bar = data.iloc[i + 1]

            # Get ATR for displacement check
            current_atr = atr.iloc[i] if i < len(atr) else atr.iloc[-1]
            displacement_threshold = current_atr * self.ob_displacement_factor

            # Bullish Order Block: Strong bearish candle followed by bullish displacement
            if (current["close"] < current["open"] and  # Bearish candle
                next_bar["close"] > next_bar["open"] and  # Followed by bullish
                (next_bar["close"] - current["low"]) > displacement_threshold):

                strength = self._calculate_ob_strength(current, next_bar, displacement_threshold)

                self._order_blocks.append(OrderBlock(
                    upper_price=current["open"],
                    lower_price=current["low"],
                    trigger_price=next_bar["close"],
                    is_bullish=True,
                    strength=strength,
                    start_index=i,
                    time=current["time"]
                ))

            # Bearish Order Block: Strong bullish candle followed by bearish displacement
            if (current["close"] > current["open"] and  # Bullish candle
                next_bar["close"] < next_bar["open"] and  # Followed by bearish
                (current["high"] - next_bar["close"]) > displacement_threshold):

                strength = self._calculate_ob_strength(current, next_bar, displacement_threshold)

                self._order_blocks.append(OrderBlock(
                    upper_price=current["high"],
                    lower_price=current["close"],
                    trigger_price=next_bar["close"],
                    is_bullish=False,
                    strength=strength,
                    start_index=i,
                    time=current["time"]
                ))

    def _calculate_ob_strength(
        self,
        ob_candle: pd.Series,
        displacement_candle: pd.Series,
        atr: float
    ) -> int:
        """Calculate order block strength (1-5)."""
        body_size = abs(ob_candle["close"] - ob_candle["open"])
        displacement = abs(displacement_candle["close"] - displacement_candle["open"])

        # Score based on body size and displacement
        score = 1

        if body_size > atr * 0.5:
            score += 1
        if body_size > atr:
            score += 1
        if displacement > atr:
            score += 1
        if displacement > atr * 1.5:
            score += 1

        return min(score, 5)

    def detect_bullish_order_block(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> Optional[OrderBlock]:
        """
        Find the most recent untested bullish order block.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to look back

        Returns:
            Most recent untested bullish order block or None
        """
        self._detect_order_blocks(data.tail(lookback + 3))

        bullish_obs = [ob for ob in self._order_blocks if ob.is_bullish and not ob.tested]

        if bullish_obs:
            return bullish_obs[-1]
        return None

    def detect_bearish_order_block(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> Optional[OrderBlock]:
        """
        Find the most recent untested bearish order block.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to look back

        Returns:
            Most recent untested bearish order block or None
        """
        self._detect_order_blocks(data.tail(lookback + 3))

        bearish_obs = [ob for ob in self._order_blocks if not ob.is_bullish and not ob.tested]

        if bearish_obs:
            return bearish_obs[-1]
        return None

    def get_market_structure(self, data: pd.DataFrame, lookback: int = 50) -> StructureType:
        """
        Determine overall market structure.

        Args:
            data: OHLCV DataFrame
            lookback: Bars to analyze

        Returns:
            Market structure type
        """
        if len(data) < lookback:
            return StructureType.NEUTRAL

        recent = data.tail(lookback)

        # Detect swing points
        highs = []
        lows = []

        for i in range(self.swing_lookback, len(recent) - self.swing_lookback):
            # Swing high
            is_highest = all(
                recent.iloc[i]["high"] > recent.iloc[i - j]["high"] and
                recent.iloc[i]["high"] > recent.iloc[i + j]["high"]
                for j in range(1, self.swing_lookback + 1)
            )
            if is_highest:
                highs.append(recent.iloc[i]["high"])

            # Swing low
            is_lowest = all(
                recent.iloc[i]["low"] < recent.iloc[i - j]["low"] and
                recent.iloc[i]["low"] < recent.iloc[i + j]["low"]
                for j in range(1, self.swing_lookback + 1)
            )
            if is_lowest:
                lows.append(recent.iloc[i]["low"])

        if len(highs) < 2 or len(lows) < 2:
            return StructureType.NEUTRAL

        # Check for higher highs and higher lows (bullish)
        hh = highs[-1] > highs[-2]
        hl = lows[-1] > lows[-2]

        # Check for lower highs and lower lows (bearish)
        lh = highs[-1] < highs[-2]
        ll = lows[-1] < lows[-2]

        if hh and hl:
            return StructureType.BULLISH
        elif lh and ll:
            return StructureType.BEARISH
        else:
            return StructureType.NEUTRAL

    def get_swing_highs(self) -> List[SwingPoint]:
        """Get detected swing highs."""
        return self._swing_highs.copy()

    def get_swing_lows(self) -> List[SwingPoint]:
        """Get detected swing lows."""
        return self._swing_lows.copy()

    def get_fvgs(self) -> List[FairValueGap]:
        """Get all detected FVGs."""
        return self._fvgs.copy()

    def get_order_blocks(self) -> List[OrderBlock]:
        """Get all detected order blocks."""
        return self._order_blocks.copy()
