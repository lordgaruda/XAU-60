"""
Trend Break + Trauma + RSI Strategy.
Converted from XAUUSD_TrendBreak_Trauma.mq5
"""
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.trend_utils import TrendAnalyzer, TrendDirection
from indicators.common import calculate_rsi, calculate_ema


class TrendBreakTrauma(StrategyBase):
    """
    Trend Line Break with Trauma (EMA) Filter and RSI Exit Strategy.

    Entry Logic:
    - BUY: Price above Trauma (EMA) + Resistance breakout confirmed
    - SELL: Price below Trauma (EMA) + Support breakdown confirmed

    Exit Logic:
    - BUY Exit: RSI >= Overbought level (default 70)
    - SELL Exit: RSI <= Oversold level (default 30)
    """

    name = "Trend Break Trauma"
    version = "2.0.0"
    description = "Trend line break with EMA filter and RSI-based exits"
    author = "AlgoAct"

    def __init__(self):
        super().__init__()
        self.trend: Optional[TrendAnalyzer] = None

        # RSI parameters
        self.rsi_period = 14
        self.rsi_overbought = 70.0
        self.rsi_oversold = 30.0

        # Trauma (EMA) parameters
        self.trauma_period = 21

        # Trend line parameters
        self.trendline_lookback = 50
        self.trendline_min_touches = 3
        self.breakout_confirm_bars = 2

        # Risk parameters
        self.stop_loss_pips = 100.0
        self.take_profit_pips = 200.0
        self.use_trailing_stop = False
        self.trailing_pips = 50.0

        # Session filter
        self.use_time_filter = True
        self.start_hour = 0
        self.end_hour = 23
        self.trade_friday = True

        self.magic_number = 789456

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize strategy with configuration."""
        self.config = config

        # Load RSI parameters
        params = config.get("parameters", {})
        self.rsi_period = params.get("rsi_period", 14)
        self.rsi_overbought = params.get("rsi_overbought", 70.0)
        self.rsi_oversold = params.get("rsi_oversold", 30.0)

        # Trauma parameters
        self.trauma_period = params.get("trauma_period", 21)

        # Trend line parameters
        self.trendline_lookback = params.get("trendline_lookback", 50)
        self.trendline_min_touches = params.get("trendline_min_touches", 3)
        self.breakout_confirm_bars = params.get("breakout_confirm_bars", 2)

        # Risk parameters
        risk = config.get("risk", {})
        self.stop_loss_pips = risk.get("stop_loss_pips", 100.0)
        self.take_profit_pips = risk.get("take_profit_pips", 200.0)
        self.use_trailing_stop = risk.get("trailing_stop", False)
        self.trailing_pips = risk.get("trailing_pips", 50.0)

        # Session settings
        session = config.get("session", {})
        self.use_time_filter = session.get("use_time_filter", True)
        self.start_hour = session.get("start_hour", 0)
        self.end_hour = session.get("end_hour", 23)
        self.trade_friday = session.get("trade_friday", True)

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

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze market and generate trade signal."""
        if len(data) < max(self.trendline_lookback, self.trauma_period, self.rsi_period):
            return None

        if self.use_time_filter and not self._is_trading_time(data):
            return None

        current_price = data.iloc[-1]["close"]

        # Get Trauma (EMA) value
        trauma_value = self._get_trauma_value(data)
        if trauma_value is None:
            return None

        # Get RSI value
        rsi_value = self._get_rsi_value(data)
        if rsi_value is None:
            return None

        # Check for BUY signal
        # Condition: Price above Trauma + Bullish trend line breakout
        if current_price > trauma_value:
            breakout = self.trend.detect_resistance_break(data, self.trendline_lookback)

            if breakout and breakout.is_bullish:
                # Confirm breakout timing
                bars_since_break = len(data) - 1 - breakout.break_index
                if bars_since_break <= self.breakout_confirm_bars + 1:
                    return self._create_buy_signal(symbol, data, current_price)

        # Check for SELL signal
        # Condition: Price below Trauma + Bearish trend line breakdown
        if current_price < trauma_value:
            breakdown = self.trend.detect_support_break(data, self.trendline_lookback)

            if breakdown and not breakdown.is_bullish:
                bars_since_break = len(data) - 1 - breakdown.break_index
                if bars_since_break <= self.breakout_confirm_bars + 1:
                    return self._create_sell_signal(symbol, data, current_price)

        return None

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

    def _create_buy_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        entry_price: float
    ) -> TradeSignal:
        """Create a buy trade signal."""
        point = 0.1 if "XAU" in symbol else 0.0001

        stop_loss = entry_price - (self.stop_loss_pips * point * 10)
        take_profit = entry_price + (self.take_profit_pips * point * 10)

        return TradeSignal(
            signal=Signal.BUY,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment="TrendBreak_BUY",
            magic_number=self.magic_number
        )

    def _create_sell_signal(
        self,
        symbol: str,
        data: pd.DataFrame,
        entry_price: float
    ) -> TradeSignal:
        """Create a sell trade signal."""
        point = 0.1 if "XAU" in symbol else 0.0001

        stop_loss = entry_price + (self.stop_loss_pips * point * 10)
        take_profit = entry_price - (self.take_profit_pips * point * 10)

        return TradeSignal(
            signal=Signal.SELL,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment="TrendBreak_SELL",
            magic_number=self.magic_number
        )

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """
        Check if position should be closed based on RSI.

        BUY -> Close when RSI >= Overbought
        SELL -> Close when RSI <= Oversold
        """
        rsi_value = self._get_rsi_value(data)
        if rsi_value is None:
            return False

        if position.type == Signal.BUY:
            if rsi_value >= self.rsi_overbought:
                return True

        elif position.type == Signal.SELL:
            if rsi_value <= self.rsi_oversold:
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
