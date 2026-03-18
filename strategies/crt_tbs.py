"""
CRT + TBS Strategy - Candle Range Theory + Time-Based Strategy.

Strategy Rules:
1. Use Asian Session (00:00-06:00 UTC) to define the range
2. Only trade during Killzones (London: 07:00-09:00, NY: 13:00-15:00)
3. Look for manipulation/liquidity sweeps beyond the range
4. Enter when price sweeps and closes back inside range
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
import pytz

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.common import calculate_atr


class Killzone(Enum):
    """Trading killzones."""
    NONE = 0
    LONDON = 1
    NEW_YORK = 2


@dataclass
class AsianRange:
    """Asian session range data."""
    high: float
    low: float
    mid: float
    date: datetime
    valid: bool = True


@dataclass
class ManipulationSignal:
    """Manipulation detection result."""
    detected: bool
    direction: Signal  # BUY if swept low, SELL if swept high
    sweep_price: float
    sweep_time: datetime


class CRTStrategy(StrategyBase):
    """
    CRT + TBS (Candle Range Theory + Time-Based Strategy).

    Entry Logic:
    - Define range using Asian Session H1 candle (00:00-06:00 UTC)
    - Wait for London (07:00-09:00) or NY (13:00-15:00) killzone
    - Bullish: Price sweeps BELOW Asian Low, then closes back inside range
    - Bearish: Price sweeps ABOVE Asian High, then closes back inside range

    Exit Logic:
    - Take Profit: Opposite end of Asian range
    - Stop Loss: 10 pips beyond the sweep wick
    """

    name = "CRT TBS"
    version = "1.0.0"
    description = "Candle Range Theory + Time-Based Strategy with killzone entries"
    author = "AlgoAct"

    def __init__(self):
        super().__init__()

        # Asian session times (UTC)
        self.asian_start = time(0, 0)   # 00:00 UTC
        self.asian_end = time(6, 0)     # 06:00 UTC

        # Killzone times (UTC)
        self.london_start = time(7, 0)   # 07:00 UTC
        self.london_end = time(9, 0)     # 09:00 UTC
        self.ny_start = time(13, 0)      # 13:00 UTC
        self.ny_end = time(15, 0)        # 15:00 UTC

        # Strategy parameters
        self.sl_pips_beyond_sweep = 10.0
        self.use_range_tp = True
        self.fixed_rr = 2.0
        self.max_trades_per_killzone = 1

        # State tracking
        self._current_asian_range: Optional[AsianRange] = None
        self._trades_today: Dict[str, int] = {}  # killzone -> count
        self._last_trade_date: Optional[datetime] = None
        self._sweep_detected: bool = False
        self._sweep_direction: Signal = Signal.HOLD
        self._sweep_price: float = 0.0

        self.magic_number = 789789
        self.utc = pytz.UTC

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize strategy with configuration."""
        self.config = config

        # Load parameters
        params = config.get("parameters", {})
        self.sl_pips_beyond_sweep = params.get("sl_pips_beyond_sweep", 10.0)
        self.use_range_tp = params.get("use_range_tp", True)
        self.fixed_rr = params.get("fixed_rr", 2.0)
        self.max_trades_per_killzone = params.get("max_trades_per_killzone", 1)

        # Session times
        session = config.get("session", {})
        asian = session.get("asian", {})
        if asian:
            self.asian_start = time(asian.get("start_hour", 0), 0)
            self.asian_end = time(asian.get("end_hour", 6), 0)

        london = session.get("london_killzone", {})
        if london:
            self.london_start = time(london.get("start_hour", 7), 0)
            self.london_end = time(london.get("end_hour", 9), 0)

        ny = session.get("ny_killzone", {})
        if ny:
            self.ny_start = time(ny.get("start_hour", 13), 0)
            self.ny_end = time(ny.get("end_hour", 15), 0)

        # Strategy settings
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M5")  # Entry timeframe
        self.range_timeframe = config.get("range_timeframe", "H1")
        self.enabled = config.get("enabled", True)
        self.magic_number = config.get("magic_number", 789789)

        # Risk settings
        risk = config.get("risk", {})
        self.lot_size = risk.get("lot_size", 0.1)

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trade signal.

        Args:
            symbol: Trading symbol
            data: M5 OHLCV DataFrame for entry detection

        Returns:
            TradeSignal if entry condition met, None otherwise
        """
        if len(data) < 10:
            return None

        current_bar = data.iloc[-1]
        current_time = self._get_utc_time(current_bar["time"])

        # Reset daily tracking if new day
        self._reset_daily_tracking(current_time)

        # Check if we're in a killzone
        killzone = self._get_current_killzone(current_time)
        if killzone == Killzone.NONE:
            return None

        # Check if we've already traded this killzone today
        kz_key = f"{current_time.date()}_{killzone.name}"
        if self._trades_today.get(kz_key, 0) >= self.max_trades_per_killzone:
            return None

        # Get or update Asian range
        if not self._update_asian_range(symbol, data, current_time):
            return None

        asian_range = self._current_asian_range
        if not asian_range or not asian_range.valid:
            return None

        # Detect manipulation (liquidity sweep)
        manipulation = self._detect_manipulation(data, asian_range)

        if manipulation.detected:
            # Generate trade signal
            signal = self._create_trade_signal(
                symbol=symbol,
                data=data,
                asian_range=asian_range,
                manipulation=manipulation,
                killzone=killzone
            )

            if signal:
                # Mark trade for this killzone
                self._trades_today[kz_key] = self._trades_today.get(kz_key, 0) + 1
                return signal

        return None

    def _get_utc_time(self, timestamp) -> datetime:
        """Convert timestamp to UTC datetime."""
        if isinstance(timestamp, pd.Timestamp):
            dt = timestamp.to_pydatetime()
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            dt = datetime.now()

        if dt.tzinfo is None:
            dt = self.utc.localize(dt)
        return dt

    def _reset_daily_tracking(self, current_time: datetime) -> None:
        """Reset daily trade tracking if new day."""
        current_date = current_time.date()

        if self._last_trade_date != current_date:
            self._trades_today = {}
            self._last_trade_date = current_date
            self._current_asian_range = None
            self._sweep_detected = False

    def _get_current_killzone(self, current_time: datetime) -> Killzone:
        """
        Check if current time is in a killzone.

        Args:
            current_time: Current UTC time

        Returns:
            Killzone enum value
        """
        current_t = current_time.time()

        # London Killzone: 07:00-09:00 UTC
        if self.london_start <= current_t < self.london_end:
            return Killzone.LONDON

        # NY Killzone: 13:00-15:00 UTC
        if self.ny_start <= current_t < self.ny_end:
            return Killzone.NEW_YORK

        return Killzone.NONE

    def _update_asian_range(
        self,
        symbol: str,
        data: pd.DataFrame,
        current_time: datetime
    ) -> bool:
        """
        Update Asian session range if needed.

        The Asian range is valid for the entire trading day after 06:00 UTC.
        """
        current_date = current_time.date()

        # Check if we already have today's range
        if (self._current_asian_range and
            self._current_asian_range.date.date() == current_date):
            return True

        # We need to calculate the Asian range
        # Asian session: 00:00-06:00 UTC
        asian_range = self._calculate_asian_range(data, current_time)

        if asian_range and asian_range.valid:
            self._current_asian_range = asian_range
            return True

        return False

    def _calculate_asian_range(
        self,
        data: pd.DataFrame,
        current_time: datetime
    ) -> Optional[AsianRange]:
        """
        Calculate Asian session High/Low/Mid from data.

        Looks for candles between 00:00-06:00 UTC of the current day.
        """
        try:
            # Filter data for Asian session (00:00-06:00 UTC today)
            asian_date = current_time.date()
            asian_start = datetime.combine(asian_date, self.asian_start)
            asian_end = datetime.combine(asian_date, self.asian_end)

            if current_time.tzinfo:
                asian_start = self.utc.localize(asian_start)
                asian_end = self.utc.localize(asian_end)

            # Convert data times for comparison
            data = data.copy()
            data["time_dt"] = pd.to_datetime(data["time"])

            # Filter for Asian session
            asian_data = data[
                (data["time_dt"] >= asian_start) &
                (data["time_dt"] < asian_end)
            ]

            if len(asian_data) < 1:
                # Try to find range from recent highs/lows
                # Fall back to last 6 bars if no Asian data
                recent_data = data.tail(12)
                if len(recent_data) < 6:
                    return None

                high = recent_data["high"].max()
                low = recent_data["low"].min()
            else:
                high = asian_data["high"].max()
                low = asian_data["low"].min()

            mid = (high + low) / 2

            return AsianRange(
                high=high,
                low=low,
                mid=mid,
                date=current_time,
                valid=True
            )

        except Exception as e:
            return None

    def _detect_manipulation(
        self,
        data: pd.DataFrame,
        asian_range: AsianRange
    ) -> ManipulationSignal:
        """
        Detect manipulation/liquidity sweep.

        Bullish: Price sweeps BELOW Asian Low, then closes back inside
        Bearish: Price sweeps ABOVE Asian High, then closes back inside
        """
        if len(data) < 3:
            return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2]

        current_close = current_bar["close"]
        current_low = current_bar["low"]
        current_high = current_bar["high"]
        prev_low = prev_bar["low"]
        prev_high = prev_bar["high"]

        # Bullish Setup: Sweep below Asian Low, close back inside
        # Check if we swept below and closed back inside
        swept_low = current_low < asian_range.low or prev_low < asian_range.low
        closed_inside_for_buy = current_close > asian_range.low and current_close < asian_range.high

        if swept_low and closed_inside_for_buy:
            sweep_price = min(current_low, prev_low)
            return ManipulationSignal(
                detected=True,
                direction=Signal.BUY,
                sweep_price=sweep_price,
                sweep_time=self._get_utc_time(current_bar["time"])
            )

        # Bearish Setup: Sweep above Asian High, close back inside
        swept_high = current_high > asian_range.high or prev_high > asian_range.high
        closed_inside_for_sell = current_close < asian_range.high and current_close > asian_range.low

        if swept_high and closed_inside_for_sell:
            sweep_price = max(current_high, prev_high)
            return ManipulationSignal(
                detected=True,
                direction=Signal.SELL,
                sweep_price=sweep_price,
                sweep_time=self._get_utc_time(current_bar["time"])
            )

        return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

    def _create_trade_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        asian_range: AsianRange,
        manipulation: ManipulationSignal,
        killzone: Killzone
    ) -> Optional[TradeSignal]:
        """Create trade signal based on manipulation detection."""
        current_bar = data.iloc[-1]
        entry_price = current_bar["close"]

        # Point value for SL calculation
        point = 0.1 if "XAU" in symbol else 0.0001
        sl_distance = self.sl_pips_beyond_sweep * point * 10

        if manipulation.direction == Signal.BUY:
            # Stop Loss: Below the sweep low
            stop_loss = manipulation.sweep_price - sl_distance

            # Take Profit: Asian High (opposite end of range)
            if self.use_range_tp:
                take_profit = asian_range.high
            else:
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * self.fixed_rr)

            # Validate trade makes sense
            if take_profit <= entry_price or stop_loss >= entry_price:
                return None

            return TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=self.lot_size,
                comment=f"CRT_TBS_{killzone.name}",
                magic_number=self.magic_number
            )

        elif manipulation.direction == Signal.SELL:
            # Stop Loss: Above the sweep high
            stop_loss = manipulation.sweep_price + sl_distance

            # Take Profit: Asian Low (opposite end of range)
            if self.use_range_tp:
                take_profit = asian_range.low
            else:
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * self.fixed_rr)

            # Validate trade makes sense
            if take_profit >= entry_price or stop_loss <= entry_price:
                return None

            return TradeSignal(
                signal=Signal.SELL,
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=self.lot_size,
                comment=f"CRT_TBS_{killzone.name}",
                magic_number=self.magic_number
            )

        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """
        Check if position should be closed.

        CRT strategy primarily uses SL/TP from the original trade setup.
        Additional exit: Close if price returns to mid-range without progress.
        """
        # This strategy mainly relies on SL/TP
        # Optional: Add mid-range exit or time-based exit
        return False

    def get_trailing_stop(self, position: Position, data: pd.DataFrame) -> Optional[float]:
        """
        CRT strategy doesn't use trailing stops by default.
        The target is the opposite end of the range.
        """
        return None

    def get_asian_range(self) -> Optional[AsianRange]:
        """Get current Asian range for external access."""
        return self._current_asian_range

    def get_trades_today(self) -> Dict[str, int]:
        """Get today's trade count per killzone."""
        return self._trades_today.copy()
