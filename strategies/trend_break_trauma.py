"""
Trend Break + Trauma + RSI Strategy.
Enhanced with confidence scoring, breakout confirmation, and momentum filters.
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.trend_utils import TrendAnalyzer, TrendDirection, TrendBreak
from indicators.common import (
    calculate_rsi, calculate_ema, calculate_atr,
    calculate_adx, calculate_macd, calculate_bollinger_bands
)


logger = logging.getLogger(__name__)


class BreakoutType(Enum):
    """Type of breakout detected."""
    NONE = 0
    WEAK = 1        # Just broke line
    MODERATE = 2    # Broke with momentum
    STRONG = 3      # Broke with volume/displacement


@dataclass
class BreakoutConfirmation:
    """Track confirmations for breakout quality scoring."""
    trendline_break: bool = False
    price_above_trauma: bool = False  # For buys
    breakout_displacement: bool = False
    volume_spike: bool = False
    adx_strong_trend: bool = False
    macd_aligned: bool = False
    ema_stack_aligned: bool = False
    retest_confirmed: bool = False
    rsi_momentum_aligned: bool = False
    session_optimal: bool = False

    @property
    def score(self) -> int:
        """Calculate total confirmation score."""
        return sum([
            self.trendline_break * 2,         # Core: 2 points
            self.price_above_trauma * 2,      # Core: 2 points
            self.breakout_displacement * 2,   # Important: 2 points
            self.volume_spike * 1,            # Support: 1 point
            self.adx_strong_trend * 1,        # Trend: 1 point
            self.macd_aligned * 1,            # Momentum: 1 point
            self.ema_stack_aligned * 1,       # Trend: 1 point
            self.retest_confirmed * 2,        # Important: 2 points
            self.rsi_momentum_aligned * 1,    # Momentum: 1 point
            self.session_optimal * 1,         # Timing: 1 point
        ])

    @property
    def quality(self) -> str:
        """Get breakout quality rating."""
        score = self.score
        if score >= 12:
            return "A+"
        elif score >= 9:
            return "A"
        elif score >= 6:
            return "B"
        elif score >= 4:
            return "C"
        else:
            return "D"


class TrendBreakTrauma(StrategyBase):
    """
    Trend Line Break with Trauma (EMA) Filter and RSI Exit Strategy.

    Entry Logic:
    - BUY: Price above Trauma (EMA21) + Resistance breakout confirmed + Momentum aligned
    - SELL: Price below Trauma (EMA21) + Support breakdown confirmed + Momentum aligned

    Exit Logic:
    - BUY Exit: RSI >= Overbought level OR Bearish divergence
    - SELL Exit: RSI <= Oversold level OR Bullish divergence

    Advanced Features:
    - Breakout displacement confirmation
    - Volume-based confirmation
    - MACD momentum alignment
    - EMA stack alignment (8/21/50)
    - Breakout retest confirmation
    - RSI divergence detection
    """

    name = "Trend Break Trauma"
    version = "2.1.0"
    description = "Trend line break with EMA filter, momentum confirmation, and RSI exits"
    author = "AlgoAct"

    def __init__(self):
        super().__init__()
        self.trend: Optional[TrendAnalyzer] = None

        # RSI parameters
        self.rsi_period = 14
        self.rsi_overbought = 70.0
        self.rsi_oversold = 30.0
        self.use_rsi_divergence = True

        # Trauma (EMA) parameters
        self.trauma_period = 21
        self.fast_ema = 8
        self.slow_ema = 50

        # Trend line parameters
        self.trendline_lookback = 50
        self.trendline_min_touches = 3
        self.breakout_confirm_bars = 2

        # Breakout confirmation
        self.min_displacement_atr = 0.5  # Minimum displacement in ATR
        self.require_retest = False
        self.retest_tolerance_pips = 10.0

        # MACD parameters
        self.use_macd_filter = True
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # ADX parameters
        self.use_adx_filter = True
        self.adx_period = 14
        self.adx_threshold = 20.0

        # Volume parameters
        self.use_volume_filter = False
        self.volume_spike_mult = 1.5

        # Risk parameters
        self.stop_loss_pips = 100.0
        self.take_profit_pips = 200.0
        self.use_trailing_stop = True
        self.trailing_pips = 50.0
        self.use_atr_sl_tp = True
        self.atr_sl_mult = 1.5
        self.atr_tp_mult = 3.0

        # Session filter
        self.use_time_filter = True
        self.start_hour = 0
        self.end_hour = 23
        self.trade_friday = True
        self.optimal_hours = [8, 9, 10, 14, 15, 16]

        # Minimum signal quality
        self.min_quality = "B"

        # State tracking
        self._last_confirmation: Optional[BreakoutConfirmation] = None
        self._pending_retest: Optional[Dict] = None

        self.magic_number = 789456

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize strategy with configuration."""
        self.config = config

        # Load RSI parameters
        params = config.get("parameters", {})
        self.rsi_period = params.get("rsi_period", 14)
        self.rsi_overbought = params.get("rsi_overbought", 70.0)
        self.rsi_oversold = params.get("rsi_oversold", 30.0)
        self.use_rsi_divergence = params.get("use_rsi_divergence", True)

        # Trauma parameters
        self.trauma_period = params.get("trauma_period", 21)
        self.fast_ema = params.get("fast_ema", 8)
        self.slow_ema = params.get("slow_ema", 50)

        # Trend line parameters
        self.trendline_lookback = params.get("trendline_lookback", 50)
        self.trendline_min_touches = params.get("trendline_min_touches", 3)
        self.breakout_confirm_bars = params.get("breakout_confirm_bars", 2)

        # Breakout confirmation
        breakout = config.get("breakout", {})
        self.min_displacement_atr = breakout.get("min_displacement_atr", 0.5)
        self.require_retest = breakout.get("require_retest", False)
        self.retest_tolerance_pips = breakout.get("retest_tolerance_pips", 10.0)

        # Filters
        filters = config.get("filters", {})
        self.use_macd_filter = filters.get("use_macd", True)
        self.use_adx_filter = filters.get("use_adx", True)
        self.adx_threshold = filters.get("adx_threshold", 20.0)
        self.use_volume_filter = filters.get("use_volume", False)
        self.volume_spike_mult = filters.get("volume_spike_mult", 1.5)
        self.min_quality = filters.get("min_quality", "B")

        # Risk parameters
        risk = config.get("risk", {})
        self.stop_loss_pips = risk.get("stop_loss_pips", 100.0)
        self.take_profit_pips = risk.get("take_profit_pips", 200.0)
        self.use_trailing_stop = risk.get("trailing_stop", True)
        self.trailing_pips = risk.get("trailing_pips", 50.0)
        self.use_atr_sl_tp = risk.get("use_atr_sl_tp", True)
        self.atr_sl_mult = risk.get("atr_sl_mult", 1.5)
        self.atr_tp_mult = risk.get("atr_tp_mult", 3.0)

        # Session settings
        session = config.get("session", {})
        self.use_time_filter = session.get("use_time_filter", True)
        self.start_hour = session.get("start_hour", 0)
        self.end_hour = session.get("end_hour", 23)
        self.trade_friday = session.get("trade_friday", True)
        self.optimal_hours = session.get("optimal_hours", [8, 9, 10, 14, 15, 16])

        # Strategy settings
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "H1")
        self.enabled = config.get("enabled", True)
        self.magic_number = config.get("magic_number", 789456)

        # Initialize trend analyzer
        self.trend = TrendAnalyzer(
            swing_lookback=5,
            min_touches=self.trendline_min_touches,
            break_threshold=0.0005
        )

        logger.info(f"TrendBreakTrauma initialized: {self.symbols}, TF={self.timeframe}")

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze market and generate trade signal."""
        min_bars = max(self.trendline_lookback, self.trauma_period, self.rsi_period, self.slow_ema)
        if len(data) < min_bars:
            return None

        if self.use_time_filter and not self._is_trading_time(data):
            return None

        # Initialize confirmation tracker
        confirmation = BreakoutConfirmation()

        # Session optimal
        confirmation.session_optimal = self._is_optimal_hour(data)

        current_price = data.iloc[-1]["close"]

        # Get Trauma (EMA) value
        trauma_value = self._get_trauma_value(data)
        if trauma_value is None:
            return None

        # Check EMA stack alignment (8/21/50)
        ema_aligned = self._check_ema_stack(data)

        # ADX filter
        if self.use_adx_filter:
            confirmation.adx_strong_trend = self._check_adx_strength(data)
        else:
            confirmation.adx_strong_trend = True

        # Check for BUY signal
        if current_price > trauma_value:
            confirmation.price_above_trauma = True
            confirmation.ema_stack_aligned = ema_aligned == "bullish"

            signal = self._check_bullish_breakout(symbol, data, confirmation)
            if signal:
                return signal

        # Check for SELL signal
        if current_price < trauma_value:
            confirmation.price_above_trauma = False
            confirmation.ema_stack_aligned = ema_aligned == "bearish"

            signal = self._check_bearish_breakdown(symbol, data, confirmation)
            if signal:
                return signal

        return None

    def _check_bullish_breakout(
        self,
        symbol: str,
        data: pd.DataFrame,
        confirmation: BreakoutConfirmation
    ) -> Optional[TradeSignal]:
        """Check for bullish breakout with confirmations."""
        # Detect resistance break
        breakout = self.trend.detect_resistance_break(data, self.trendline_lookback)
        if not breakout or not breakout.is_bullish:
            return None

        confirmation.trendline_break = True

        # Confirm breakout timing
        bars_since_break = len(data) - 1 - breakout.break_index
        if bars_since_break > self.breakout_confirm_bars + 1:
            return None

        current_price = data.iloc[-1]["close"]

        # Check breakout displacement
        atr = calculate_atr(data, 14)
        atr_value = atr.iloc[-1]
        displacement = current_price - breakout.trend_line.end_price
        confirmation.breakout_displacement = displacement >= atr_value * self.min_displacement_atr

        # Check MACD alignment
        if self.use_macd_filter:
            confirmation.macd_aligned = self._check_macd_bullish(data)
        else:
            confirmation.macd_aligned = True

        # Check RSI momentum
        rsi = self._get_rsi_value(data)
        if rsi is not None:
            confirmation.rsi_momentum_aligned = 40 < rsi < 70

        # Check volume spike
        if self.use_volume_filter and "volume" in data.columns:
            confirmation.volume_spike = self._check_volume_spike(data)
        else:
            confirmation.volume_spike = not self.use_volume_filter

        # Store confirmation
        self._last_confirmation = confirmation

        # Check minimum quality
        quality_order = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}
        if quality_order.get(confirmation.quality, 0) < quality_order.get(self.min_quality, 3):
            logger.debug(f"Signal rejected: quality={confirmation.quality}, min={self.min_quality}")
            return None

        # Calculate entry and targets
        return self._create_buy_signal(symbol, data, current_price, confirmation)

    def _check_bearish_breakdown(
        self,
        symbol: str,
        data: pd.DataFrame,
        confirmation: BreakoutConfirmation
    ) -> Optional[TradeSignal]:
        """Check for bearish breakdown with confirmations."""
        # Detect support break
        breakdown = self.trend.detect_support_break(data, self.trendline_lookback)
        if not breakdown or breakdown.is_bullish:
            return None

        confirmation.trendline_break = True

        # Confirm breakout timing
        bars_since_break = len(data) - 1 - breakdown.break_index
        if bars_since_break > self.breakout_confirm_bars + 1:
            return None

        current_price = data.iloc[-1]["close"]

        # Check breakout displacement
        atr = calculate_atr(data, 14)
        atr_value = atr.iloc[-1]
        displacement = breakdown.trend_line.end_price - current_price
        confirmation.breakout_displacement = displacement >= atr_value * self.min_displacement_atr

        # Check MACD alignment
        if self.use_macd_filter:
            confirmation.macd_aligned = self._check_macd_bearish(data)
        else:
            confirmation.macd_aligned = True

        # Check RSI momentum
        rsi = self._get_rsi_value(data)
        if rsi is not None:
            confirmation.rsi_momentum_aligned = 30 < rsi < 60

        # Check volume spike
        if self.use_volume_filter and "volume" in data.columns:
            confirmation.volume_spike = self._check_volume_spike(data)
        else:
            confirmation.volume_spike = not self.use_volume_filter

        # Store confirmation
        self._last_confirmation = confirmation

        # Check minimum quality
        quality_order = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}
        if quality_order.get(confirmation.quality, 0) < quality_order.get(self.min_quality, 3):
            logger.debug(f"Signal rejected: quality={confirmation.quality}, min={self.min_quality}")
            return None

        # Calculate entry and targets
        return self._create_sell_signal(symbol, data, current_price, confirmation)

    def _get_trauma_value(self, data: pd.DataFrame) -> Optional[float]:
        """Get Trauma indicator value (EMA)."""
        try:
            ema = calculate_ema(data, self.trauma_period)
            return ema.iloc[-1]
        except Exception:
            return None

    def _get_rsi_value(self, data: pd.DataFrame) -> Optional[float]:
        """Get RSI value."""
        try:
            rsi = calculate_rsi(data, self.rsi_period)
            return rsi.iloc[-1]
        except Exception:
            return None

    def _check_ema_stack(self, data: pd.DataFrame) -> str:
        """Check EMA stack alignment (8/21/50)."""
        try:
            ema8 = calculate_ema(data, self.fast_ema).iloc[-1]
            ema21 = calculate_ema(data, self.trauma_period).iloc[-1]
            ema50 = calculate_ema(data, self.slow_ema).iloc[-1]

            if ema8 > ema21 > ema50:
                return "bullish"
            elif ema8 < ema21 < ema50:
                return "bearish"
            else:
                return "mixed"
        except Exception:
            return "mixed"

    def _check_adx_strength(self, data: pd.DataFrame) -> bool:
        """Check if ADX indicates strong trend."""
        try:
            adx = calculate_adx(data, self.adx_period)
            return adx.iloc[-1] >= self.adx_threshold
        except Exception:
            return True

    def _check_macd_bullish(self, data: pd.DataFrame) -> bool:
        """Check if MACD is bullish."""
        try:
            macd, signal, hist = calculate_macd(
                data, self.macd_fast, self.macd_slow, self.macd_signal
            )
            return hist.iloc[-1] > 0 and macd.iloc[-1] > signal.iloc[-1]
        except Exception:
            return True

    def _check_macd_bearish(self, data: pd.DataFrame) -> bool:
        """Check if MACD is bearish."""
        try:
            macd, signal, hist = calculate_macd(
                data, self.macd_fast, self.macd_slow, self.macd_signal
            )
            return hist.iloc[-1] < 0 and macd.iloc[-1] < signal.iloc[-1]
        except Exception:
            return True

    def _check_volume_spike(self, data: pd.DataFrame) -> bool:
        """Check for volume spike on breakout."""
        if "volume" not in data.columns:
            return False

        try:
            current_vol = data.iloc[-1]["volume"]
            avg_vol = data["volume"].tail(20).mean()
            return current_vol >= avg_vol * self.volume_spike_mult
        except Exception:
            return False

    def _create_buy_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        entry_price: float,
        confirmation: BreakoutConfirmation
    ) -> TradeSignal:
        """Create a buy trade signal."""
        point = 0.1 if "XAU" in symbol else 0.0001

        if self.use_atr_sl_tp:
            atr = calculate_atr(data, 14)
            atr_value = atr.iloc[-1]
            stop_loss = entry_price - (atr_value * self.atr_sl_mult)
            take_profit = entry_price + (atr_value * self.atr_tp_mult)
        else:
            stop_loss = entry_price - (self.stop_loss_pips * point * 10)
            take_profit = entry_price + (self.take_profit_pips * point * 10)

        logger.info(f"BUY Signal: {symbol} @ {entry_price:.2f}, Quality={confirmation.quality}")

        return TradeSignal(
            signal=Signal.BUY,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"TrendBreak_BUY_{confirmation.quality}_S{confirmation.score}",
            magic_number=self.magic_number
        )

    def _create_sell_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        entry_price: float,
        confirmation: BreakoutConfirmation
    ) -> TradeSignal:
        """Create a sell trade signal."""
        point = 0.1 if "XAU" in symbol else 0.0001

        if self.use_atr_sl_tp:
            atr = calculate_atr(data, 14)
            atr_value = atr.iloc[-1]
            stop_loss = entry_price + (atr_value * self.atr_sl_mult)
            take_profit = entry_price - (atr_value * self.atr_tp_mult)
        else:
            stop_loss = entry_price + (self.stop_loss_pips * point * 10)
            take_profit = entry_price - (self.take_profit_pips * point * 10)

        logger.info(f"SELL Signal: {symbol} @ {entry_price:.2f}, Quality={confirmation.quality}")

        return TradeSignal(
            signal=Signal.SELL,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"TrendBreak_SELL_{confirmation.quality}_S{confirmation.score}",
            magic_number=self.magic_number
        )

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """
        Check if position should be closed based on RSI.

        BUY -> Close when RSI >= Overbought or bearish divergence
        SELL -> Close when RSI <= Oversold or bullish divergence
        """
        rsi_value = self._get_rsi_value(data)
        if rsi_value is None:
            return False

        if position.type == Signal.BUY:
            if rsi_value >= self.rsi_overbought:
                logger.info(f"Closing BUY: RSI overbought ({rsi_value:.1f})")
                return True
            if self.use_rsi_divergence and self._detect_bearish_divergence(data):
                logger.info("Closing BUY: Bearish RSI divergence")
                return True

        elif position.type == Signal.SELL:
            if rsi_value <= self.rsi_oversold:
                logger.info(f"Closing SELL: RSI oversold ({rsi_value:.1f})")
                return True
            if self.use_rsi_divergence and self._detect_bullish_divergence(data):
                logger.info("Closing SELL: Bullish RSI divergence")
                return True

        return False

    def _detect_bearish_divergence(self, data: pd.DataFrame, lookback: int = 14) -> bool:
        """Detect bearish RSI divergence (price higher high, RSI lower high)."""
        if len(data) < lookback:
            return False

        try:
            rsi = calculate_rsi(data, self.rsi_period)
            recent = data.tail(lookback)
            recent_rsi = rsi.tail(lookback)

            # Find highest price point
            price_highs = recent["high"]
            price_max_idx = price_highs.idxmax()

            # Check if current price is making new high
            if recent.iloc[-1]["high"] > price_highs.max() * 0.998:
                # Compare RSI at highs
                rsi_at_high = recent_rsi.loc[price_max_idx]
                current_rsi = recent_rsi.iloc[-1]

                if current_rsi < rsi_at_high - 5:
                    return True

            return False
        except Exception:
            return False

    def _detect_bullish_divergence(self, data: pd.DataFrame, lookback: int = 14) -> bool:
        """Detect bullish RSI divergence (price lower low, RSI higher low)."""
        if len(data) < lookback:
            return False

        try:
            rsi = calculate_rsi(data, self.rsi_period)
            recent = data.tail(lookback)
            recent_rsi = rsi.tail(lookback)

            # Find lowest price point
            price_lows = recent["low"]
            price_min_idx = price_lows.idxmin()

            # Check if current price is making new low
            if recent.iloc[-1]["low"] < price_lows.min() * 1.002:
                # Compare RSI at lows
                rsi_at_low = recent_rsi.loc[price_min_idx]
                current_rsi = recent_rsi.iloc[-1]

                if current_rsi > rsi_at_low + 5:
                    return True

            return False
        except Exception:
            return False

    def get_trailing_stop(self, position: Position, data: pd.DataFrame) -> Optional[float]:
        """Calculate trailing stop."""
        if not self.use_trailing_stop:
            return None

        if position.profit <= 0:
            return None

        current_price = data.iloc[-1]["close"]
        point = 0.1 if "XAU" in position.symbol else 0.0001
        trail_distance = self.trailing_pips * point * 10

        if position.type == Signal.BUY:
            new_sl = current_price - trail_distance
            if new_sl > position.stop_loss and new_sl < current_price:
                return new_sl

        else:  # SELL
            new_sl = current_price + trail_distance
            if (position.stop_loss == 0 or new_sl < position.stop_loss) and new_sl > current_price:
                return new_sl

        return None

    def _is_trading_time(self, data: pd.DataFrame) -> bool:
        """Check if current time is within trading session."""
        current_time = data.iloc[-1]["time"]

        if isinstance(current_time, pd.Timestamp):
            hour = current_time.hour
            weekday = current_time.weekday()
        else:
            hour = current_time.hour
            weekday = current_time.weekday() if hasattr(current_time, "weekday") else 0

        # Friday check
        if not self.trade_friday and weekday == 4:
            return False

        # Hour check
        return self.start_hour <= hour < self.end_hour

    def _is_optimal_hour(self, data: pd.DataFrame) -> bool:
        """Check if current hour is optimal for trading."""
        current_time = data.iloc[-1]["time"]

        if isinstance(current_time, pd.Timestamp):
            hour = current_time.hour
        else:
            hour = current_time.hour

        return hour in self.optimal_hours

    def get_last_confirmation(self) -> Optional[BreakoutConfirmation]:
        """Get the last breakout confirmation for analysis."""
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
