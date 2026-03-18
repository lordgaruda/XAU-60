"""
SMC Scalper Strategy - Smart Money Concepts based scalping.
Converted from XAUUSD_SMC_Scalper.mq5
"""
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime

from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
from indicators.smc_utils import SMCAnalyzer
from indicators.common import calculate_atr


class SMCScalper(StrategyBase):
    """
    Smart Money Concepts Scalping Strategy.

    Entry Logic:
    - BUY: Bullish CHoCH + Bullish FVG + Bearish Order Block (target)
    - SELL: Bearish CHoCH + Bearish FVG + Bullish Order Block (target)

    Entry at FVG midline, exit at Order Block or R:R target.
    """

    name = "SMC Scalper"
    version = "2.0.0"
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

        # Session filter
        self.start_hour = 8
        self.end_hour = 18
        self.trade_friday = False

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

        # Session settings
        session = config.get("session", {})
        self.start_hour = session.get("start_hour", 8)
        self.end_hour = session.get("end_hour", 18)
        self.trade_friday = session.get("trade_friday", False)

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

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze market and generate trade signal."""
        if len(data) < self.choch_lookback:
            return None

        if not self._is_trading_time(data):
            return None

        # Check for bullish setup
        signal = self._check_bullish_setup(symbol, data)
        if signal:
            return signal

        # Check for bearish setup
        signal = self._check_bearish_setup(symbol, data)
        if signal:
            return signal

        return None

    def _check_bullish_setup(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Check for bullish SMC setup."""
        # Detect Bullish CHoCH
        choch = self.smc.detect_bullish_choch(data, self.choch_lookback)
        if not choch:
            return None

        # Detect Bullish FVG
        fvg = self.smc.detect_bullish_fvg(data, 20)
        if not fvg:
            return None

        # Detect Bearish Order Block (for take profit target)
        ob = self.smc.detect_bearish_order_block(data, self.ob_lookback)
        if not ob:
            return None

        current_price = data.iloc[-1]["close"]

        # Check if price is in FVG zone
        if not (fvg.lower_price <= current_price <= fvg.upper_price):
            # Check if price is close to FVG (within 20 pips)
            point = 0.1 if "XAU" in symbol else 0.0001
            max_distance = 20 * point * 10
            if abs(current_price - fvg.mid_price) > max_distance:
                return None

        # Entry at FVG midline
        entry_price = fvg.mid_price

        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(data, entry_price, is_buy=True)

        # Calculate take profit
        take_profit = self._calculate_take_profit(
            entry_price, stop_loss, ob.lower_price, is_buy=True
        )

        return TradeSignal(
            signal=Signal.BUY,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"SMC_BUY_CHoCH_FVG",
            magic_number=self.magic_number
        )

    def _check_bearish_setup(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Check for bearish SMC setup."""
        # Detect Bearish CHoCH
        choch = self.smc.detect_bearish_choch(data, self.choch_lookback)
        if not choch:
            return None

        # Detect Bearish FVG
        fvg = self.smc.detect_bearish_fvg(data, 20)
        if not fvg:
            return None

        # Detect Bullish Order Block (for take profit target)
        ob = self.smc.detect_bullish_order_block(data, self.ob_lookback)
        if not ob:
            return None

        current_price = data.iloc[-1]["close"]

        # Check if price is in FVG zone
        if not (fvg.lower_price <= current_price <= fvg.upper_price):
            point = 0.1 if "XAU" in symbol else 0.0001
            max_distance = 20 * point * 10
            if abs(current_price - fvg.mid_price) > max_distance:
                return None

        # Entry at FVG midline
        entry_price = fvg.mid_price

        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(data, entry_price, is_buy=False)

        # Calculate take profit
        take_profit = self._calculate_take_profit(
            entry_price, stop_loss, ob.upper_price, is_buy=False
        )

        return TradeSignal(
            signal=Signal.SELL,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"SMC_SELL_CHoCH_FVG",
            magic_number=self.magic_number
        )

    def _calculate_stop_loss(
        self,
        data: pd.DataFrame,
        entry_price: float,
        is_buy: bool
    ) -> float:
        """Calculate stop loss based on ATR or fixed pips."""
        point = 0.1 if "XAU" in data.iloc[-1].get("symbol", "XAUUSD") else 0.0001

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

        # Try to use order block level
        if order_block_level > 0:
            if is_buy and order_block_level > entry_price:
                distance_to_ob = order_block_level - entry_price
                # Check if OB provides at least 1.5:1 RR
                if distance_to_ob >= stop_distance * 1.5:
                    # Target 10 pips before order block
                    point = 0.1  # Gold
                    return order_block_level - (10 * point * 10)

            elif not is_buy and order_block_level < entry_price:
                distance_to_ob = entry_price - order_block_level
                if distance_to_ob >= stop_distance * 1.5:
                    point = 0.1
                    return order_block_level + (10 * point * 10)

        # Fall back to fixed R:R ratio
        if is_buy:
            return entry_price + (stop_distance * self.risk_reward)
        else:
            return entry_price - (stop_distance * self.risk_reward)

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """Check if position should be closed."""
        # This strategy primarily uses SL/TP for exits
        # Additional exit logic can be added here
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
