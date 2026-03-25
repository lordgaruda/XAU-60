"""
SMC Scalper Strategy - Smart Money Concepts based scalping.
Enhanced with confidence scoring, multi-timeframe analysis, and advanced filters.
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.smc_utils import SMCAnalyzer, StructureType, FairValueGap, OrderBlock
from indicators.common import calculate_atr, calculate_ema, calculate_adx, calculate_rsi


logger = logging.getLogger(__name__)


class SignalQuality(Enum):
    """Signal quality rating."""
    A_PLUS = 5  # Highest quality - all confirmations
    A = 4       # Strong signal - most confirmations
    B = 3       # Good signal - core confirmations
    C = 2       # Acceptable - minimum confirmations
    D = 1       # Weak signal - consider skipping


@dataclass
class SignalConfirmation:
    """Track confirmations for signal quality scoring."""
    choch_detected: bool = False
    fvg_detected: bool = False
    order_block_valid: bool = False
    trend_aligned: bool = False
    price_in_fvg_zone: bool = False
    session_optimal: bool = False
    atr_filter_passed: bool = False
    adx_filter_passed: bool = False
    rsi_filter_passed: bool = False
    spread_acceptable: bool = False

    @property
    def score(self) -> int:
        """Calculate total confirmation score."""
        return sum([
            self.choch_detected * 2,        # Core: 2 points
            self.fvg_detected * 2,          # Core: 2 points
            self.order_block_valid * 1,     # Support: 1 point
            self.trend_aligned * 2,         # Important: 2 points
            self.price_in_fvg_zone * 1,     # Precision: 1 point
            self.session_optimal * 1,       # Timing: 1 point
            self.atr_filter_passed * 1,     # Risk: 1 point
            self.adx_filter_passed * 1,     # Trend strength: 1 point
            self.rsi_filter_passed * 1,     # Momentum: 1 point
            self.spread_acceptable * 1,     # Cost: 1 point
        ])

    @property
    def quality(self) -> SignalQuality:
        """Get signal quality rating."""
        score = self.score
        if score >= 12:
            return SignalQuality.A_PLUS
        elif score >= 9:
            return SignalQuality.A
        elif score >= 6:
            return SignalQuality.B
        elif score >= 4:
            return SignalQuality.C
        else:
            return SignalQuality.D


class SMCScalper(StrategyBase):
    """
    Smart Money Concepts Scalping Strategy.

    Entry Logic:
    - BUY: Bullish CHoCH + Bullish FVG + Bearish Order Block (target)
    - SELL: Bearish CHoCH + Bearish FVG + Bullish Order Block (target)

    Entry at FVG midline, exit at Order Block or R:R target.

    Advanced Features:
    - Signal confidence scoring (A+, A, B, C, D)
    - Multi-timeframe trend alignment
    - ADX trend strength filter
    - RSI momentum filter
    - ATR-based volatility filter
    - Session optimization (London/NY)
    - Spread filter
    """

    name = "SMC Scalper"
    version = "2.1.0"
    description = "Smart Money Concepts scalping with CHoCH, FVG, and Order Blocks"
    author = "AlgoAct"

    def __init__(self):
        super().__init__()
        self.smc: Optional[SMCAnalyzer] = None

        # Default parameters
        self.choch_lookback = 50
        self.fvg_min_pips = 5.0
        self.ob_lookback = 20
        self.risk_reward = 2.0
        self.use_trailing_stop = True
        self.trailing_pips = 50.0
        self.atr_period = 14
        self.atr_multiplier = 2.0
        self.use_atr_sl = True
        self.stop_loss_pips = 100.0

        # Advanced filters
        self.min_signal_quality = SignalQuality.B  # Minimum quality to trade
        self.use_mtf_filter = True
        self.htf_trend_period = 50  # Higher TF trend lookback

        self.use_adx_filter = True
        self.adx_period = 14
        self.adx_threshold = 20.0  # Minimum ADX for trend confirmation

        self.use_rsi_filter = True
        self.rsi_period = 14
        self.rsi_ob = 70.0  # Overbought
        self.rsi_os = 30.0  # Oversold

        self.use_atr_volatility_filter = True
        self.atr_min_pips = 5.0
        self.atr_max_pips = 50.0

        self.max_spread_pips = 5.0
        self.use_spread_filter = True

        # Session filter
        self.use_session_filter = True
        self.start_hour = 8
        self.end_hour = 18
        self.trade_friday = False
        self.optimal_hours = [8, 9, 10, 14, 15, 16]  # London open, NY open

        # State tracking
        self._last_signal_time: Optional[datetime] = None
        self._signal_cooldown_bars = 3
        self._last_confirmation: Optional[SignalConfirmation] = None

        self.magic_number = 789123

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize strategy with configuration."""
        self.config = config

        # Load parameters
        params = config.get("parameters", {})
        self.choch_lookback = params.get("choch_lookback", 50)
        self.fvg_min_pips = params.get("fvg_min_pips", 5.0)
        self.ob_lookback = params.get("ob_lookback", 20)
        self.risk_reward = params.get("risk_reward", 2.0)
        self.use_trailing_stop = params.get("trailing_stop", True)
        self.trailing_pips = params.get("trailing_pips", 50.0)
        self.atr_period = params.get("atr_period", 14)
        self.atr_multiplier = params.get("atr_multiplier", 2.0)
        self.use_atr_sl = params.get("use_atr_sl", True)
        self.stop_loss_pips = params.get("stop_loss_pips", 100.0)

        # Advanced filter settings
        filters = config.get("filters", {})
        min_quality = filters.get("min_signal_quality", "B")
        self.min_signal_quality = getattr(SignalQuality, min_quality, SignalQuality.B)
        self.use_mtf_filter = filters.get("use_mtf_filter", True)
        self.htf_trend_period = filters.get("htf_trend_period", 50)

        self.use_adx_filter = filters.get("use_adx_filter", True)
        self.adx_period = filters.get("adx_period", 14)
        self.adx_threshold = filters.get("adx_threshold", 20.0)

        self.use_rsi_filter = filters.get("use_rsi_filter", True)
        self.rsi_period = filters.get("rsi_period", 14)
        self.rsi_ob = filters.get("rsi_overbought", 70.0)
        self.rsi_os = filters.get("rsi_oversold", 30.0)

        self.use_atr_volatility_filter = filters.get("use_atr_filter", True)
        self.atr_min_pips = filters.get("atr_min_pips", 5.0)
        self.atr_max_pips = filters.get("atr_max_pips", 50.0)

        self.max_spread_pips = filters.get("max_spread_pips", 5.0)
        self.use_spread_filter = filters.get("use_spread_filter", True)

        # Session settings
        session = config.get("session", {})
        self.use_session_filter = session.get("use_filter", True)
        self.start_hour = session.get("start_hour", 8)
        self.end_hour = session.get("end_hour", 18)
        self.trade_friday = session.get("trade_friday", False)
        self.optimal_hours = session.get("optimal_hours", [8, 9, 10, 14, 15, 16])

        # Strategy settings
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M15")
        self.enabled = config.get("enabled", True)
        self.magic_number = config.get("magic_number", 789123)

        # Initialize SMC analyzer
        point = 0.1 if "XAU" in self.symbols[0] else 0.0001
        self.smc = SMCAnalyzer(
            swing_lookback=5,
            fvg_min_pips=self.fvg_min_pips,
            ob_displacement_factor=self.atr_multiplier,
            point=point
        )

        logger.info(f"SMC Scalper initialized: {self.symbols}, TF={self.timeframe}, "
                   f"min_quality={self.min_signal_quality.name}")

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze market and generate trade signal."""
        if len(data) < self.choch_lookback:
            return None

        # Initialize confirmation tracker
        confirmation = SignalConfirmation()

        # Session filter
        if self.use_session_filter:
            if not self._is_trading_time(data):
                return None
            confirmation.session_optimal = self._is_optimal_hour(data)
        else:
            confirmation.session_optimal = True

        # ATR volatility filter
        if self.use_atr_volatility_filter:
            if not self._check_atr_filter(data, symbol):
                return None
            confirmation.atr_filter_passed = True
        else:
            confirmation.atr_filter_passed = True

        # ADX trend strength filter
        if self.use_adx_filter:
            confirmation.adx_filter_passed = self._check_adx_filter(data)
        else:
            confirmation.adx_filter_passed = True

        # Check for bullish setup
        signal = self._check_bullish_setup(symbol, data, confirmation)
        if signal:
            return signal

        # Check for bearish setup
        signal = self._check_bearish_setup(symbol, data, confirmation)
        if signal:
            return signal

        return None

    def _check_bullish_setup(
        self,
        symbol: str,
        data: pd.DataFrame,
        confirmation: SignalConfirmation
    ) -> Optional[TradeSignal]:
        """Check for bullish SMC setup with full confirmation scoring."""
        # Detect Bullish CHoCH
        choch = self.smc.detect_bullish_choch(data, self.choch_lookback)
        if not choch:
            return None
        confirmation.choch_detected = True

        # Detect Bullish FVG
        fvg = self.smc.detect_bullish_fvg(data, 20)
        if not fvg:
            return None
        confirmation.fvg_detected = True

        # Detect Bearish Order Block (for take profit target)
        ob = self.smc.detect_bearish_order_block(data, self.ob_lookback)
        confirmation.order_block_valid = ob is not None

        current_price = data.iloc[-1]["close"]
        point = 0.1 if "XAU" in symbol else 0.0001

        # Check if price is in FVG zone
        if fvg.lower_price <= current_price <= fvg.upper_price:
            confirmation.price_in_fvg_zone = True
        else:
            max_distance = 20 * point * 10
            if abs(current_price - fvg.mid_price) > max_distance:
                return None

        # Multi-timeframe trend alignment
        if self.use_mtf_filter:
            structure = self.smc.get_market_structure(data, self.htf_trend_period)
            confirmation.trend_aligned = structure == StructureType.BULLISH
        else:
            confirmation.trend_aligned = True

        # RSI filter - for buys, prefer not overbought
        if self.use_rsi_filter:
            rsi = self._get_rsi(data)
            if rsi is not None:
                confirmation.rsi_filter_passed = rsi < self.rsi_ob - 10
        else:
            confirmation.rsi_filter_passed = True

        # Spread filter
        confirmation.spread_acceptable = self._check_spread(data, symbol)

        # Store confirmation for analysis
        self._last_confirmation = confirmation

        # Check minimum quality
        if confirmation.quality.value < self.min_signal_quality.value:
            logger.debug(f"Signal rejected: quality={confirmation.quality.name}, "
                        f"score={confirmation.score}, min={self.min_signal_quality.name}")
            return None

        # Entry at FVG midline
        entry_price = fvg.mid_price

        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(data, entry_price, is_buy=True)

        # Calculate take profit
        ob_target = ob.lower_price if ob else entry_price + (entry_price - stop_loss) * self.risk_reward
        take_profit = self._calculate_take_profit(entry_price, stop_loss, ob_target, is_buy=True)

        logger.info(f"BUY Signal: {symbol} @ {entry_price:.2f}, SL={stop_loss:.2f}, "
                   f"TP={take_profit:.2f}, Quality={confirmation.quality.name}")

        return TradeSignal(
            signal=Signal.BUY,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"SMC_BUY_{confirmation.quality.name}_S{confirmation.score}",
            magic_number=self.magic_number
        )

    def _check_bearish_setup(
        self,
        symbol: str,
        data: pd.DataFrame,
        confirmation: SignalConfirmation
    ) -> Optional[TradeSignal]:
        """Check for bearish SMC setup with full confirmation scoring."""
        # Detect Bearish CHoCH
        choch = self.smc.detect_bearish_choch(data, self.choch_lookback)
        if not choch:
            return None
        confirmation.choch_detected = True

        # Detect Bearish FVG
        fvg = self.smc.detect_bearish_fvg(data, 20)
        if not fvg:
            return None
        confirmation.fvg_detected = True

        # Detect Bullish Order Block (for take profit target)
        ob = self.smc.detect_bullish_order_block(data, self.ob_lookback)
        confirmation.order_block_valid = ob is not None

        current_price = data.iloc[-1]["close"]
        point = 0.1 if "XAU" in symbol else 0.0001

        # Check if price is in FVG zone
        if fvg.lower_price <= current_price <= fvg.upper_price:
            confirmation.price_in_fvg_zone = True
        else:
            max_distance = 20 * point * 10
            if abs(current_price - fvg.mid_price) > max_distance:
                return None

        # Multi-timeframe trend alignment
        if self.use_mtf_filter:
            structure = self.smc.get_market_structure(data, self.htf_trend_period)
            confirmation.trend_aligned = structure == StructureType.BEARISH
        else:
            confirmation.trend_aligned = True

        # RSI filter - for sells, prefer not oversold
        if self.use_rsi_filter:
            rsi = self._get_rsi(data)
            if rsi is not None:
                confirmation.rsi_filter_passed = rsi > self.rsi_os + 10
        else:
            confirmation.rsi_filter_passed = True

        # Spread filter
        confirmation.spread_acceptable = self._check_spread(data, symbol)

        # Store confirmation for analysis
        self._last_confirmation = confirmation

        # Check minimum quality
        if confirmation.quality.value < self.min_signal_quality.value:
            logger.debug(f"Signal rejected: quality={confirmation.quality.name}, "
                        f"score={confirmation.score}, min={self.min_signal_quality.name}")
            return None

        # Entry at FVG midline
        entry_price = fvg.mid_price

        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(data, entry_price, is_buy=False)

        # Calculate take profit
        ob_target = ob.upper_price if ob else entry_price - (stop_loss - entry_price) * self.risk_reward
        take_profit = self._calculate_take_profit(entry_price, stop_loss, ob_target, is_buy=False)

        logger.info(f"SELL Signal: {symbol} @ {entry_price:.2f}, SL={stop_loss:.2f}, "
                   f"TP={take_profit:.2f}, Quality={confirmation.quality.name}")

        return TradeSignal(
            signal=Signal.SELL,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"SMC_SELL_{confirmation.quality.name}_S{confirmation.score}",
            magic_number=self.magic_number
        )

    def _calculate_stop_loss(
        self,
        data: pd.DataFrame,
        entry_price: float,
        is_buy: bool
    ) -> float:
        """Calculate stop loss based on ATR or fixed pips."""
        point = 0.1 if "XAU" in str(data.iloc[-1].get("symbol", "XAUUSD")) else 0.0001

        if self.use_atr_sl and len(data) >= self.atr_period:
            atr = calculate_atr(data, self.atr_period)
            atr_value = atr.iloc[-1] * self.atr_multiplier

            if is_buy:
                return entry_price - atr_value
            else:
                return entry_price + atr_value
        else:
            sl_distance = self.stop_loss_pips * point * 10

            if is_buy:
                return entry_price - sl_distance
            else:
                return entry_price + sl_distance

    def _calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        order_block_level: float,
        is_buy: bool
    ) -> float:
        """Calculate take profit based on order block or R:R ratio."""
        stop_distance = abs(entry_price - stop_loss)
        point = 0.1  # Gold

        # Try to use order block level
        if order_block_level > 0:
            if is_buy and order_block_level > entry_price:
                distance_to_ob = order_block_level - entry_price
                # Check if OB provides at least 1.5:1 RR
                if distance_to_ob >= stop_distance * 1.5:
                    # Target 10 pips before order block
                    return order_block_level - (10 * point * 10)

            elif not is_buy and order_block_level < entry_price:
                distance_to_ob = entry_price - order_block_level
                if distance_to_ob >= stop_distance * 1.5:
                    return order_block_level + (10 * point * 10)

        # Fall back to fixed R:R ratio
        if is_buy:
            return entry_price + (stop_distance * self.risk_reward)
        else:
            return entry_price - (stop_distance * self.risk_reward)

    def _check_atr_filter(self, data: pd.DataFrame, symbol: str) -> bool:
        """Check if ATR is within acceptable range."""
        if len(data) < self.atr_period:
            return True

        atr = calculate_atr(data, self.atr_period)
        atr_value = atr.iloc[-1]

        point = 0.1 if "XAU" in symbol else 0.0001
        atr_pips = atr_value / (point * 10)

        return self.atr_min_pips <= atr_pips <= self.atr_max_pips

    def _check_adx_filter(self, data: pd.DataFrame) -> bool:
        """Check if ADX indicates sufficient trend strength."""
        if len(data) < self.adx_period:
            return True

        try:
            adx = calculate_adx(data, self.adx_period)
            return adx.iloc[-1] >= self.adx_threshold
        except Exception:
            return True

    def _get_rsi(self, data: pd.DataFrame) -> Optional[float]:
        """Get current RSI value."""
        if len(data) < self.rsi_period:
            return None

        try:
            rsi = calculate_rsi(data, self.rsi_period)
            return rsi.iloc[-1]
        except Exception:
            return None

    def _check_spread(self, data: pd.DataFrame, symbol: str) -> bool:
        """Check if spread is acceptable."""
        if not self.use_spread_filter:
            return True

        # Try to get spread from data
        if "spread" in data.columns:
            spread = data.iloc[-1]["spread"]
            point = 0.1 if "XAU" in symbol else 0.0001
            spread_pips = spread / (point * 10)
            return spread_pips <= self.max_spread_pips

        # Default to acceptable if no spread data
        return True

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """Check if position should be closed."""
        # This strategy primarily uses SL/TP for exits
        # Additional exit: Close on opposing CHoCH
        if position.type == Signal.BUY:
            choch = self.smc.detect_bearish_choch(data, 20)
            if choch:
                logger.info(f"Closing BUY on bearish CHoCH")
                return True

        elif position.type == Signal.SELL:
            choch = self.smc.detect_bullish_choch(data, 20)
            if choch:
                logger.info(f"Closing SELL on bullish CHoCH")
                return True

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
        """Check if current hour is in optimal trading hours."""
        current_time = data.iloc[-1]["time"]

        if isinstance(current_time, pd.Timestamp):
            hour = current_time.hour
        else:
            hour = current_time.hour

        return hour in self.optimal_hours

    def get_last_confirmation(self) -> Optional[SignalConfirmation]:
        """Get the last signal confirmation for analysis."""
        return self._last_confirmation

    def on_trade_opened(self, position: Position) -> None:
        """Log trade opening with confirmation details."""
        if self._last_confirmation:
            logger.info(
                f"Trade Opened: {position.symbol} {position.type.name} @ {position.open_price}, "
                f"Quality={self._last_confirmation.quality.name}, Score={self._last_confirmation.score}"
            )

    def on_trade_closed(self, position: Position, profit: float) -> None:
        """Log trade closing."""
        result = "WIN" if profit > 0 else "LOSS"
        logger.info(
            f"Trade Closed: {position.symbol} {position.type.name} "
            f"P/L={profit:.2f} ({result})"
        )
