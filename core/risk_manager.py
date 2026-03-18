"""
Risk Manager for position sizing and risk control.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, date
from loguru import logger

from .mt5_connector import MT5Connector, AccountInfo, SymbolInfo
from .strategy_base import Signal, Position


@dataclass
class RiskLimits:
    """Risk management limits."""
    max_risk_per_trade: float = 2.0  # Percentage
    max_daily_loss: float = 5.0  # Percentage
    max_drawdown: float = 20.0  # Percentage
    max_positions: int = 5
    max_positions_per_symbol: int = 2
    max_correlation_exposure: float = 50.0  # Percentage


@dataclass
class DailyStats:
    """Daily trading statistics."""
    date: date
    starting_balance: float
    current_pnl: float
    trades_count: int
    winning_trades: int
    losing_trades: int


class RiskManager:
    """
    Risk management for the trading bot.

    Handles:
    - Position sizing based on risk %
    - Daily loss limits
    - Max drawdown protection
    - Position limits per symbol
    - Margin validation
    """

    def __init__(self, mt5: MT5Connector, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.

        Args:
            mt5: MT5 connector instance
            limits: Risk limits (uses defaults if not provided)
        """
        self.mt5 = mt5
        self.limits = limits or RiskLimits()

        self._daily_stats: Optional[DailyStats] = None
        self._peak_balance: float = 0.0
        self._starting_balance: float = 0.0

    def initialize(self) -> bool:
        """
        Initialize risk manager with account data.

        Returns:
            True if initialized successfully
        """
        account = self.mt5.get_account_info()
        if not account:
            logger.error("Failed to get account info for risk manager")
            return False

        self._starting_balance = account.balance
        self._peak_balance = account.balance

        self._daily_stats = DailyStats(
            date=date.today(),
            starting_balance=account.balance,
            current_pnl=0.0,
            trades_count=0,
            winning_trades=0,
            losing_trades=0,
        )

        logger.info(f"Risk manager initialized. Balance: {account.balance} {account.currency}")
        return True

    def calculate_lot_size(
        self,
        symbol: str,
        stop_loss_pips: float,
        risk_percent: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on risk percentage.

        Args:
            symbol: Trading symbol
            stop_loss_pips: Stop loss distance in pips
            risk_percent: Risk per trade (uses limit if not provided)

        Returns:
            Calculated lot size
        """
        if risk_percent is None:
            risk_percent = self.limits.max_risk_per_trade

        account = self.mt5.get_account_info()
        symbol_info = self.mt5.get_symbol_info(symbol)

        if not account or not symbol_info:
            logger.error("Failed to get account/symbol info for lot calculation")
            return symbol_info.min_lot if symbol_info else 0.01

        # Calculate risk amount in account currency
        risk_amount = account.balance * (risk_percent / 100)

        # Calculate pip value
        # For forex: pip_value = lot_size * contract_size * point
        # For gold (XAUUSD): 1 pip = $1 per 0.01 lot typically
        point = symbol_info.point
        tick_value = symbol_info.tick_value
        tick_size = symbol_info.tick_size

        if tick_size > 0:
            pip_value = (tick_value / tick_size) * point * 10  # Adjust for pip definition
        else:
            pip_value = tick_value * 10

        # Calculate lot size
        if stop_loss_pips > 0 and pip_value > 0:
            lot_size = risk_amount / (stop_loss_pips * pip_value)
        else:
            lot_size = symbol_info.min_lot

        # Round to lot step and clamp to min/max
        lot_step = symbol_info.lot_step
        lot_size = round(lot_size / lot_step) * lot_step
        lot_size = max(symbol_info.min_lot, min(lot_size, symbol_info.max_lot))

        logger.debug(f"Calculated lot size: {lot_size} for {risk_percent}% risk, {stop_loss_pips} pip SL")
        return lot_size

    def can_open_trade(self, symbol: str, signal: Signal) -> tuple[bool, str]:
        """
        Check if a new trade can be opened.

        Args:
            symbol: Symbol to trade
            signal: Trade direction

        Returns:
            Tuple of (can_trade, reason)
        """
        # Check daily loss limit
        if self._is_daily_limit_reached():
            return False, "Daily loss limit reached"

        # Check max drawdown
        if self._is_max_drawdown_reached():
            return False, "Maximum drawdown reached"

        # Check position limits
        positions = self.mt5.get_positions()

        if len(positions) >= self.limits.max_positions:
            return False, f"Maximum positions ({self.limits.max_positions}) reached"

        # Check positions per symbol
        symbol_positions = [p for p in positions if p.symbol == symbol]
        if len(symbol_positions) >= self.limits.max_positions_per_symbol:
            return False, f"Maximum positions for {symbol} reached"

        # Check margin
        account = self.mt5.get_account_info()
        if account and account.margin_level > 0 and account.margin_level < 150:
            return False, "Insufficient margin (margin level < 150%)"

        return True, "OK"

    def _is_daily_limit_reached(self) -> bool:
        """Check if daily loss limit is reached."""
        if not self._daily_stats:
            return False

        # Reset stats if new day
        if self._daily_stats.date != date.today():
            account = self.mt5.get_account_info()
            self._daily_stats = DailyStats(
                date=date.today(),
                starting_balance=account.balance if account else 0,
                current_pnl=0.0,
                trades_count=0,
                winning_trades=0,
                losing_trades=0,
            )

        # Calculate current daily P&L
        account = self.mt5.get_account_info()
        if account:
            daily_pnl = account.equity - self._daily_stats.starting_balance
            daily_pnl_percent = (daily_pnl / self._daily_stats.starting_balance) * 100

            if daily_pnl_percent <= -self.limits.max_daily_loss:
                logger.warning(f"Daily loss limit reached: {daily_pnl_percent:.2f}%")
                return True

        return False

    def _is_max_drawdown_reached(self) -> bool:
        """Check if maximum drawdown is reached."""
        account = self.mt5.get_account_info()
        if not account:
            return False

        # Update peak balance
        if account.equity > self._peak_balance:
            self._peak_balance = account.equity

        # Calculate drawdown
        if self._peak_balance > 0:
            drawdown = ((self._peak_balance - account.equity) / self._peak_balance) * 100

            if drawdown >= self.limits.max_drawdown:
                logger.warning(f"Max drawdown reached: {drawdown:.2f}%")
                return True

        return False

    def validate_trade_signal(
        self,
        symbol: str,
        signal: Signal,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> tuple[bool, str]:
        """
        Validate a trade signal before execution.

        Args:
            symbol: Trading symbol
            signal: Trade direction
            entry_price: Planned entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Tuple of (is_valid, reason)
        """
        symbol_info = self.mt5.get_symbol_info(symbol)
        if not symbol_info:
            return False, f"Invalid symbol: {symbol}"

        # Validate stop loss distance
        sl_distance = abs(entry_price - stop_loss)
        min_sl = symbol_info.point * 10  # Minimum 10 points

        if sl_distance < min_sl:
            return False, f"Stop loss too close: {sl_distance} < {min_sl}"

        # Validate take profit distance
        tp_distance = abs(entry_price - take_profit)
        if tp_distance < min_sl:
            return False, f"Take profit too close: {tp_distance} < {min_sl}"

        # Validate direction consistency
        if signal == Signal.BUY:
            if stop_loss >= entry_price:
                return False, "BUY stop loss must be below entry"
            if take_profit <= entry_price:
                return False, "BUY take profit must be above entry"
        elif signal == Signal.SELL:
            if stop_loss <= entry_price:
                return False, "SELL stop loss must be above entry"
            if take_profit >= entry_price:
                return False, "SELL take profit must be below entry"

        return True, "Valid"

    def record_trade_result(self, profit: float) -> None:
        """
        Record a trade result for daily statistics.

        Args:
            profit: Trade profit (positive or negative)
        """
        if self._daily_stats:
            self._daily_stats.trades_count += 1
            self._daily_stats.current_pnl += profit

            if profit > 0:
                self._daily_stats.winning_trades += 1
            else:
                self._daily_stats.losing_trades += 1

    def get_daily_stats(self) -> Optional[DailyStats]:
        """Get current daily statistics."""
        return self._daily_stats

    def get_current_drawdown(self) -> float:
        """Get current drawdown percentage."""
        account = self.mt5.get_account_info()
        if not account or self._peak_balance == 0:
            return 0.0

        return ((self._peak_balance - account.equity) / self._peak_balance) * 100

    def get_risk_status(self) -> Dict[str, Any]:
        """
        Get current risk status summary.

        Returns:
            Dictionary with risk metrics
        """
        account = self.mt5.get_account_info()
        positions = self.mt5.get_positions()

        return {
            "balance": account.balance if account else 0,
            "equity": account.equity if account else 0,
            "margin_level": account.margin_level if account else 0,
            "drawdown_percent": self.get_current_drawdown(),
            "peak_balance": self._peak_balance,
            "open_positions": len(positions),
            "max_positions": self.limits.max_positions,
            "daily_pnl": self._daily_stats.current_pnl if self._daily_stats else 0,
            "daily_trades": self._daily_stats.trades_count if self._daily_stats else 0,
            "daily_limit_reached": self._is_daily_limit_reached(),
            "max_drawdown_reached": self._is_max_drawdown_reached(),
        }
