"""
CRT + TBS Strategy - Candle Range Theory + Time-Based Strategy.
Enhanced with manipulation quality scoring, HTF bias, and advanced range analysis.

Strategy Rules:
1. Use Asian Session (00:00-06:00 UTC) to define the range
2. Only trade during Killzones (London: 07:00-09:00, NY: 13:00-15:00)
3. Look for manipulation/liquidity sweeps beyond the range
4. Enter when price sweeps and closes back inside range with confirmation
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
import pytz
import logging

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.common import calculate_atr, calculate_ema, calculate_rsi


logger = logging.getLogger(__name__)


class Killzone(Enum):
    """Trading killzones."""
    NONE = 0
    LONDON = 1
    NEW_YORK = 2
    LONDON_CLOSE = 3


class SweepQuality(Enum):
    """Quality of liquidity sweep."""
    NONE = 0
    WEAK = 1        # Small sweep, quick return
    MODERATE = 2    # Decent sweep with momentum
    STRONG = 3      # Strong sweep with displacement
    PERFECT = 4     # Textbook manipulation


@dataclass
class AsianRange:
    """Asian session range data."""
    high: float
    low: float
    mid: float
    range_size: float
    date: datetime
    valid: bool = True
    is_expansion_day: bool = False  # Above average range


@dataclass
class ManipulationSignal:
    """Manipulation detection result with quality scoring."""
    detected: bool
    direction: Signal  # BUY if swept low, SELL if swept high
    sweep_price: float
    sweep_time: datetime
    quality: SweepQuality = SweepQuality.NONE
    sweep_depth_pips: float = 0.0
    candle_rejection: bool = False
    volume_spike: bool = False
    quick_reversal: bool = False


@dataclass
class CRTConfirmation:
    """Track confirmations for CRT signal quality."""
    range_valid: bool = False
    in_killzone: bool = False
    sweep_detected: bool = False
    sweep_quality: SweepQuality = SweepQuality.NONE
    price_closed_inside: bool = False
    htf_bias_aligned: bool = False
    candle_rejection: bool = False
    volume_confirmed: bool = False
    atr_filter_passed: bool = False
    not_overextended: bool = False

    @property
    def score(self) -> int:
        """Calculate total confirmation score."""
        return sum([
            self.range_valid * 1,
            self.in_killzone * 1,
            self.sweep_detected * 2,
            self.sweep_quality.value,
            self.price_closed_inside * 2,
            self.htf_bias_aligned * 2,
            self.candle_rejection * 1,
            self.volume_confirmed * 1,
            self.atr_filter_passed * 1,
            self.not_overextended * 1,
        ])

    @property
    def quality(self) -> str:
        """Get signal quality rating."""
        score = self.score
        if score >= 14:
            return "A+"
        elif score >= 11:
            return "A"
        elif score >= 8:
            return "B"
        elif score >= 5:
            return "C"
        else:
            return "D"


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

    Advanced Features:
    - Manipulation quality scoring (weak/moderate/strong/perfect)
    - Higher timeframe bias confirmation
    - Range expansion filter
    - Candle rejection detection
    - Multiple killzone support
    - Time-based exit option
    """

    name = "CRT TBS"
    version = "2.1.0"
    description = "Candle Range Theory + Time-Based Strategy with killzone entries"
    author = "AlgoAct"

    def __init__(self):
        super().__init__()

        # Asian session times (UTC)
        self.asian_start = time(0, 0)   # 00:00 UTC
        self.asian_end = time(6, 0)     # 06:00 UTC

        # Killzone times (UTC)
        self.london_start = time(7, 0)
        self.london_end = time(9, 0)
        self.ny_start = time(13, 0)
        self.ny_end = time(15, 0)
        self.london_close_start = time(15, 0)
        self.london_close_end = time(17, 0)

        # Killzone preferences
        self.trade_london = True
        self.trade_ny = True
        self.trade_london_close = False

        # Strategy parameters
        self.sl_pips_beyond_sweep = 10.0
        self.use_range_tp = True
        self.fixed_rr = 2.0
        self.max_trades_per_killzone = 1
        self.max_trades_per_day = 2

        # Sweep detection
        self.min_sweep_pips = 3.0
        self.max_sweep_pips = 50.0
        self.require_candle_rejection = True
        self.rejection_body_ratio = 0.3  # Body < 30% of range = rejection

        # Range filters
        self.min_range_pips = 20.0
        self.max_range_pips = 100.0
        self.use_range_expansion_filter = True
        self.avg_range_lookback = 5  # Days

        # HTF bias
        self.use_htf_bias = True
        self.htf_ema_period = 50

        # Exit options
        self.use_mid_range_exit = False
        self.use_time_exit = True
        self.time_exit_hour = 20  # Close all by 20:00 UTC

        # Risk parameters
        self.use_atr_filter = True
        self.atr_min_mult = 0.8
        self.atr_max_mult = 2.5

        # Signal quality
        self.min_quality = "B"

        # State tracking
        self._current_asian_range: Optional[AsianRange] = None
        self._trades_today: Dict[str, int] = {}
        self._last_trade_date: Optional[datetime] = None
        self._daily_trade_count: int = 0
        self._range_history: List[float] = []
        self._last_confirmation: Optional[CRTConfirmation] = None

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
        self.max_trades_per_day = params.get("max_trades_per_day", 2)

        # Sweep detection
        sweep = config.get("sweep", {})
        self.min_sweep_pips = sweep.get("min_pips", 3.0)
        self.max_sweep_pips = sweep.get("max_pips", 50.0)
        self.require_candle_rejection = sweep.get("require_rejection", True)
        self.rejection_body_ratio = sweep.get("rejection_ratio", 0.3)

        # Range filters
        range_cfg = config.get("range", {})
        self.min_range_pips = range_cfg.get("min_pips", 20.0)
        self.max_range_pips = range_cfg.get("max_pips", 100.0)
        self.use_range_expansion_filter = range_cfg.get("use_expansion_filter", True)

        # HTF bias
        htf = config.get("htf", {})
        self.use_htf_bias = htf.get("use_bias", True)
        self.htf_ema_period = htf.get("ema_period", 50)

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
            self.trade_london = london.get("enabled", True)

        ny = session.get("ny_killzone", {})
        if ny:
            self.ny_start = time(ny.get("start_hour", 13), 0)
            self.ny_end = time(ny.get("end_hour", 15), 0)
            self.trade_ny = ny.get("enabled", True)

        london_close = session.get("london_close_killzone", {})
        if london_close:
            self.london_close_start = time(london_close.get("start_hour", 15), 0)
            self.london_close_end = time(london_close.get("end_hour", 17), 0)
            self.trade_london_close = london_close.get("enabled", False)

        # Exit options
        exit_cfg = config.get("exit", {})
        self.use_mid_range_exit = exit_cfg.get("mid_range", False)
        self.use_time_exit = exit_cfg.get("time_exit", True)
        self.time_exit_hour = exit_cfg.get("exit_hour", 20)

        # Quality filter
        filters = config.get("filters", {})
        self.min_quality = filters.get("min_quality", "B")
        self.use_atr_filter = filters.get("use_atr", True)

        # Strategy settings
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M5")
        self.range_timeframe = config.get("range_timeframe", "H1")
        self.enabled = config.get("enabled", True)
        self.magic_number = config.get("magic_number", 789789)

        # Risk settings
        risk = config.get("risk", {})
        self.lot_size = risk.get("lot_size", 0.1)

        logger.info(f"CRT TBS initialized: {self.symbols}, TF={self.timeframe}")

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trade signal.

        Args:
            symbol: Trading symbol
            data: M5 OHLCV DataFrame for entry detection

        Returns:
            TradeSignal if entry condition met, None otherwise
        """
        if len(data) < 20:
            return None

        current_bar = data.iloc[-1]
        current_time = self._get_utc_time(current_bar["time"])

        # Reset daily tracking if new day
        self._reset_daily_tracking(current_time)

        # Check daily trade limit
        if self._daily_trade_count >= self.max_trades_per_day:
            return None

        # Check if we're in a killzone
        killzone = self._get_current_killzone(current_time)
        if killzone == Killzone.NONE:
            return None

        # Check killzone trade limit
        kz_key = f"{current_time.date()}_{killzone.name}"
        if self._trades_today.get(kz_key, 0) >= self.max_trades_per_killzone:
            return None

        # Initialize confirmation tracker
        confirmation = CRTConfirmation()
        confirmation.in_killzone = True

        # Get or update Asian range
        if not self._update_asian_range(symbol, data, current_time):
            return None

        asian_range = self._current_asian_range
        if not asian_range or not asian_range.valid:
            return None

        confirmation.range_valid = True

        # Check range size filter
        point = 0.1 if "XAU" in symbol else 0.0001
        range_pips = asian_range.range_size / (point * 10)
        if range_pips < self.min_range_pips or range_pips > self.max_range_pips:
            return None

        # ATR filter
        if self.use_atr_filter:
            confirmation.atr_filter_passed = self._check_atr_filter(data, asian_range.range_size)
        else:
            confirmation.atr_filter_passed = True

        # HTF bias check
        if self.use_htf_bias:
            htf_bias = self._get_htf_bias(data)
        else:
            htf_bias = Signal.HOLD

        # Detect manipulation (liquidity sweep)
        manipulation = self._detect_manipulation(data, asian_range, symbol)

        if manipulation.detected:
            confirmation.sweep_detected = True
            confirmation.sweep_quality = manipulation.quality
            confirmation.price_closed_inside = True
            confirmation.candle_rejection = manipulation.candle_rejection
            confirmation.volume_confirmed = manipulation.volume_spike

            # Check HTF alignment
            if self.use_htf_bias:
                confirmation.htf_bias_aligned = (
                    (manipulation.direction == Signal.BUY and htf_bias != Signal.SELL) or
                    (manipulation.direction == Signal.SELL and htf_bias != Signal.BUY)
                )
            else:
                confirmation.htf_bias_aligned = True

            # Check if price is not overextended from EMA
            confirmation.not_overextended = self._check_not_overextended(data, symbol)

            # Store confirmation
            self._last_confirmation = confirmation

            # Check minimum quality
            quality_order = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}
            if quality_order.get(confirmation.quality, 0) < quality_order.get(self.min_quality, 3):
                logger.debug(f"Signal rejected: quality={confirmation.quality}, min={self.min_quality}")
                return None

            # Generate trade signal
            signal = self._create_trade_signal(
                symbol=symbol,
                data=data,
                asian_range=asian_range,
                manipulation=manipulation,
                killzone=killzone,
                confirmation=confirmation
            )

            if signal:
                # Mark trade for this killzone
                self._trades_today[kz_key] = self._trades_today.get(kz_key, 0) + 1
                self._daily_trade_count += 1
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
            self._daily_trade_count = 0

    def _get_current_killzone(self, current_time: datetime) -> Killzone:
        """Check if current time is in a killzone."""
        current_t = current_time.time()

        # London Killzone
        if self.trade_london and self.london_start <= current_t < self.london_end:
            return Killzone.LONDON

        # NY Killzone
        if self.trade_ny and self.ny_start <= current_t < self.ny_end:
            return Killzone.NEW_YORK

        # London Close Killzone
        if self.trade_london_close and self.london_close_start <= current_t < self.london_close_end:
            return Killzone.LONDON_CLOSE

        return Killzone.NONE

    def _update_asian_range(
        self,
        symbol: str,
        data: pd.DataFrame,
        current_time: datetime
    ) -> bool:
        """Update Asian session range if needed."""
        current_date = current_time.date()

        # Check if we already have today's range
        if (self._current_asian_range and
            self._current_asian_range.date.date() == current_date):
            return True

        # Calculate the Asian range
        asian_range = self._calculate_asian_range(data, current_time, symbol)

        if asian_range and asian_range.valid:
            self._current_asian_range = asian_range
            # Update range history
            self._range_history.append(asian_range.range_size)
            if len(self._range_history) > self.avg_range_lookback * 2:
                self._range_history = self._range_history[-self.avg_range_lookback:]
            return True

        return False

    def _calculate_asian_range(
        self,
        data: pd.DataFrame,
        current_time: datetime,
        symbol: str
    ) -> Optional[AsianRange]:
        """Calculate Asian session High/Low/Mid from data."""
        try:
            asian_date = current_time.date()
            asian_start = datetime.combine(asian_date, self.asian_start)
            asian_end = datetime.combine(asian_date, self.asian_end)

            if current_time.tzinfo:
                asian_start = self.utc.localize(asian_start)
                asian_end = self.utc.localize(asian_end)

            data = data.copy()
            data["time_dt"] = pd.to_datetime(data["time"])

            asian_data = data[
                (data["time_dt"] >= asian_start) &
                (data["time_dt"] < asian_end)
            ]

            if len(asian_data) < 1:
                # Fall back to recent data
                recent_data = data.tail(12)
                if len(recent_data) < 6:
                    return None

                high = recent_data["high"].max()
                low = recent_data["low"].min()
            else:
                high = asian_data["high"].max()
                low = asian_data["low"].min()

            range_size = high - low
            mid = (high + low) / 2

            # Check if expansion day
            is_expansion = False
            if self.use_range_expansion_filter and len(self._range_history) >= 3:
                avg_range = np.mean(self._range_history[-self.avg_range_lookback:])
                is_expansion = range_size > avg_range * 1.3

            return AsianRange(
                high=high,
                low=low,
                mid=mid,
                range_size=range_size,
                date=current_time,
                valid=True,
                is_expansion_day=is_expansion
            )

        except Exception as e:
            logger.error(f"Error calculating Asian range: {e}")
            return None

    def _detect_manipulation(
        self,
        data: pd.DataFrame,
        asian_range: AsianRange,
        symbol: str
    ) -> ManipulationSignal:
        """
        Detect manipulation/liquidity sweep with quality scoring.

        Bullish: Price sweeps BELOW Asian Low, then closes back inside
        Bearish: Price sweeps ABOVE Asian High, then closes back inside
        """
        if len(data) < 3:
            return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2]
        prev_prev_bar = data.iloc[-3]

        current_close = current_bar["close"]
        current_low = current_bar["low"]
        current_high = current_bar["high"]
        current_open = current_bar["open"]
        prev_low = prev_bar["low"]
        prev_high = prev_bar["high"]

        point = 0.1 if "XAU" in symbol else 0.0001

        # Bullish Setup: Sweep below Asian Low, close back inside
        swept_low = current_low < asian_range.low or prev_low < asian_range.low
        closed_inside_for_buy = current_close > asian_range.low and current_close < asian_range.high

        if swept_low and closed_inside_for_buy:
            sweep_price = min(current_low, prev_low)
            sweep_depth = asian_range.low - sweep_price
            sweep_depth_pips = sweep_depth / (point * 10)

            # Check sweep depth
            if sweep_depth_pips < self.min_sweep_pips or sweep_depth_pips > self.max_sweep_pips:
                return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

            # Calculate quality
            quality = self._calculate_sweep_quality(
                data, sweep_depth_pips, is_bullish=True
            )

            # Check candle rejection (lower wick > body)
            body = abs(current_close - current_open)
            lower_wick = min(current_open, current_close) - current_low
            candle_rejection = (body / (current_high - current_low + 0.0001)) < self.rejection_body_ratio

            # Check volume spike (if available)
            volume_spike = False
            if "volume" in data.columns:
                avg_vol = data["volume"].tail(20).mean()
                volume_spike = current_bar["volume"] > avg_vol * 1.5

            # Quick reversal check
            quick_reversal = current_close > (asian_range.low + asian_range.range_size * 0.3)

            return ManipulationSignal(
                detected=True,
                direction=Signal.BUY,
                sweep_price=sweep_price,
                sweep_time=self._get_utc_time(current_bar["time"]),
                quality=quality,
                sweep_depth_pips=sweep_depth_pips,
                candle_rejection=candle_rejection,
                volume_spike=volume_spike,
                quick_reversal=quick_reversal
            )

        # Bearish Setup: Sweep above Asian High, close back inside
        swept_high = current_high > asian_range.high or prev_high > asian_range.high
        closed_inside_for_sell = current_close < asian_range.high and current_close > asian_range.low

        if swept_high and closed_inside_for_sell:
            sweep_price = max(current_high, prev_high)
            sweep_depth = sweep_price - asian_range.high
            sweep_depth_pips = sweep_depth / (point * 10)

            # Check sweep depth
            if sweep_depth_pips < self.min_sweep_pips or sweep_depth_pips > self.max_sweep_pips:
                return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

            # Calculate quality
            quality = self._calculate_sweep_quality(
                data, sweep_depth_pips, is_bullish=False
            )

            # Check candle rejection (upper wick > body)
            body = abs(current_close - current_open)
            upper_wick = current_high - max(current_open, current_close)
            candle_rejection = (body / (current_high - current_low + 0.0001)) < self.rejection_body_ratio

            # Check volume spike
            volume_spike = False
            if "volume" in data.columns:
                avg_vol = data["volume"].tail(20).mean()
                volume_spike = current_bar["volume"] > avg_vol * 1.5

            # Quick reversal check
            quick_reversal = current_close < (asian_range.high - asian_range.range_size * 0.3)

            return ManipulationSignal(
                detected=True,
                direction=Signal.SELL,
                sweep_price=sweep_price,
                sweep_time=self._get_utc_time(current_bar["time"]),
                quality=quality,
                sweep_depth_pips=sweep_depth_pips,
                candle_rejection=candle_rejection,
                volume_spike=volume_spike,
                quick_reversal=quick_reversal
            )

        return ManipulationSignal(False, Signal.HOLD, 0, datetime.now())

    def _calculate_sweep_quality(
        self,
        data: pd.DataFrame,
        sweep_depth_pips: float,
        is_bullish: bool
    ) -> SweepQuality:
        """Calculate the quality of the liquidity sweep."""
        score = 0

        # Sweep depth contributes to quality
        if sweep_depth_pips >= 15:
            score += 2
        elif sweep_depth_pips >= 8:
            score += 1

        # Check for quick reversal
        current = data.iloc[-1]
        body = abs(current["close"] - current["open"])
        total_range = current["high"] - current["low"]

        if body > 0 and total_range > 0:
            if is_bullish:
                wick_ratio = (min(current["open"], current["close"]) - current["low"]) / total_range
            else:
                wick_ratio = (current["high"] - max(current["open"], current["close"])) / total_range

            if wick_ratio > 0.6:
                score += 2
            elif wick_ratio > 0.4:
                score += 1

        # Determine quality level
        if score >= 4:
            return SweepQuality.PERFECT
        elif score >= 3:
            return SweepQuality.STRONG
        elif score >= 2:
            return SweepQuality.MODERATE
        elif score >= 1:
            return SweepQuality.WEAK
        else:
            return SweepQuality.NONE

    def _get_htf_bias(self, data: pd.DataFrame) -> Signal:
        """Get higher timeframe bias using EMA."""
        if len(data) < self.htf_ema_period:
            return Signal.HOLD

        try:
            ema = calculate_ema(data, self.htf_ema_period)
            current_price = data.iloc[-1]["close"]
            ema_value = ema.iloc[-1]

            # Also check slope
            ema_slope = ema.iloc[-1] - ema.iloc[-5] if len(ema) >= 5 else 0

            if current_price > ema_value and ema_slope > 0:
                return Signal.BUY
            elif current_price < ema_value and ema_slope < 0:
                return Signal.SELL
            else:
                return Signal.HOLD
        except Exception:
            return Signal.HOLD

    def _check_atr_filter(self, data: pd.DataFrame, range_size: float) -> bool:
        """Check if current ATR supports the range size."""
        try:
            atr = calculate_atr(data, 14)
            atr_value = atr.iloc[-1]

            return (atr_value * self.atr_min_mult <= range_size <=
                    atr_value * self.atr_max_mult)
        except Exception:
            return True

    def _check_not_overextended(self, data: pd.DataFrame, symbol: str) -> bool:
        """Check if price is not overextended from moving average."""
        try:
            ema = calculate_ema(data, 21)
            current_price = data.iloc[-1]["close"]
            ema_value = ema.iloc[-1]

            point = 0.1 if "XAU" in symbol else 0.0001
            deviation_pips = abs(current_price - ema_value) / (point * 10)

            return deviation_pips < 50  # Not more than 50 pips from EMA
        except Exception:
            return True

    def _create_trade_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        asian_range: AsianRange,
        manipulation: ManipulationSignal,
        killzone: Killzone,
        confirmation: CRTConfirmation
    ) -> Optional[TradeSignal]:
        """Create trade signal based on manipulation detection."""
        current_bar = data.iloc[-1]
        entry_price = current_bar["close"]

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

            logger.info(
                f"BUY Signal: {symbol} @ {entry_price:.2f}, "
                f"SL={stop_loss:.2f}, TP={take_profit:.2f}, "
                f"Quality={confirmation.quality}, Killzone={killzone.name}"
            )

            return TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=self.lot_size,
                comment=f"CRT_{killzone.name}_{confirmation.quality}_S{confirmation.score}",
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

            logger.info(
                f"SELL Signal: {symbol} @ {entry_price:.2f}, "
                f"SL={stop_loss:.2f}, TP={take_profit:.2f}, "
                f"Quality={confirmation.quality}, Killzone={killzone.name}"
            )

            return TradeSignal(
                signal=Signal.SELL,
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=self.lot_size,
                comment=f"CRT_{killzone.name}_{confirmation.quality}_S{confirmation.score}",
                magic_number=self.magic_number
            )

        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """
        Check if position should be closed.

        Exit conditions:
        - Mid-range exit (optional)
        - Time-based exit
        """
        current_bar = data.iloc[-1]
        current_time = self._get_utc_time(current_bar["time"])

        # Time-based exit
        if self.use_time_exit:
            if current_time.hour >= self.time_exit_hour:
                logger.info(f"Closing position: Time exit ({current_time.hour}:00)")
                return True

        # Mid-range exit
        if self.use_mid_range_exit and self._current_asian_range:
            mid = self._current_asian_range.mid
            current_price = current_bar["close"]

            if position.type == Signal.BUY:
                if current_price >= mid and position.profit > 0:
                    logger.info("Closing BUY: Mid-range target reached")
                    return True

            elif position.type == Signal.SELL:
                if current_price <= mid and position.profit > 0:
                    logger.info("Closing SELL: Mid-range target reached")
                    return True

        return False

    def get_trailing_stop(self, position: Position, data: pd.DataFrame) -> Optional[float]:
        """CRT strategy doesn't use trailing stops by default."""
        return None

    def get_asian_range(self) -> Optional[AsianRange]:
        """Get current Asian range for external access."""
        return self._current_asian_range

    def get_trades_today(self) -> Dict[str, int]:
        """Get today's trade count per killzone."""
        return self._trades_today.copy()

    def get_last_confirmation(self) -> Optional[CRTConfirmation]:
        """Get the last signal confirmation for analysis."""
        return self._last_confirmation

    def on_trade_opened(self, position: Position) -> None:
        """Log trade opening."""
        if self._last_confirmation:
            logger.info(
                f"Trade Opened: {position.symbol} {position.type.name} @ {position.open_price}, "
                f"Quality={self._last_confirmation.quality}, Score={self._last_confirmation.score}"
            )

    def on_trade_closed(self, position: Position, profit: float) -> None:
        """Log trade closing."""
        result = "WIN" if profit > 0 else "LOSS"
        logger.info(
            f"Trade Closed: {position.symbol} {position.type.name} "
            f"P/L={profit:.2f} ({result})"
        )
