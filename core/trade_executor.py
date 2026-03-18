"""
Trade Executor for order management.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from .mt5_connector import MT5Connector
from .strategy_base import Signal, TradeSignal, Position
from .risk_manager import RiskManager


@dataclass
class TradeRecord:
    """Record of an executed trade."""
    ticket: int
    symbol: str
    signal: Signal
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    strategy: str
    magic_number: int
    open_time: datetime
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    profit: Optional[float] = None
    status: str = "OPEN"


class TradeExecutor:
    """
    Executes and manages trades.

    Handles:
    - Trade execution from signals
    - Position management (trailing stops, partial closes)
    - Trade tracking and history
    """

    def __init__(
        self,
        mt5: MT5Connector,
        risk_manager: RiskManager,
        default_magic: int = 123456
    ):
        """
        Initialize trade executor.

        Args:
            mt5: MT5 connector instance
            risk_manager: Risk manager instance
            default_magic: Default magic number for orders
        """
        self.mt5 = mt5
        self.risk_manager = risk_manager
        self.default_magic = default_magic

        self._trade_history: List[TradeRecord] = []
        self._active_trades: Dict[int, TradeRecord] = {}

    def execute_signal(
        self,
        signal: TradeSignal,
        strategy_name: str = ""
    ) -> Optional[int]:
        """
        Execute a trade signal.

        Args:
            signal: Trade signal to execute
            strategy_name: Name of the strategy generating the signal

        Returns:
            Ticket number if successful, None otherwise
        """
        if signal.signal == Signal.HOLD:
            return None

        # Check if we can open a trade
        can_trade, reason = self.risk_manager.can_open_trade(
            signal.symbol, signal.signal
        )
        if not can_trade:
            logger.warning(f"Cannot open trade: {reason}")
            return None

        # Validate the signal
        is_valid, reason = self.risk_manager.validate_trade_signal(
            signal.symbol,
            signal.signal,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
        )
        if not is_valid:
            logger.warning(f"Invalid trade signal: {reason}")
            return None

        # Calculate lot size if not specified or use risk-based sizing
        lot_size = signal.lot_size
        if lot_size <= 0:
            sl_pips = self._calculate_sl_pips(
                signal.symbol, signal.entry_price, signal.stop_loss
            )
            lot_size = self.risk_manager.calculate_lot_size(signal.symbol, sl_pips)

        # Execute the trade
        magic = signal.magic_number if signal.magic_number > 0 else self.default_magic
        comment = f"{strategy_name}:{signal.comment}" if strategy_name else signal.comment

        success, ticket = self.mt5.place_market_order(
            symbol=signal.symbol,
            order_type=signal.signal,
            volume=lot_size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            magic=magic,
            comment=comment[:31],  # MT5 comment limit
        )

        if success:
            # Record the trade
            record = TradeRecord(
                ticket=ticket,
                symbol=signal.symbol,
                signal=signal.signal,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                lot_size=lot_size,
                strategy=strategy_name,
                magic_number=magic,
                open_time=datetime.now(),
            )
            self._active_trades[ticket] = record

            logger.info(
                f"Trade opened: {signal.signal.name} {lot_size} {signal.symbol} "
                f"@ {signal.entry_price} | SL: {signal.stop_loss} | TP: {signal.take_profit}"
            )
            return ticket

        return None

    def close_trade(self, ticket: int, reason: str = "Manual close") -> bool:
        """
        Close a trade by ticket number.

        Args:
            ticket: Position ticket to close
            reason: Reason for closing

        Returns:
            True if closed successfully
        """
        # Get position info before closing
        positions = self.mt5.get_positions()
        position = next((p for p in positions if p.ticket == ticket), None)

        if not position:
            logger.warning(f"Position {ticket} not found")
            return False

        # Close the position
        success = self.mt5.close_position(ticket)

        if success:
            # Update trade record
            if ticket in self._active_trades:
                record = self._active_trades.pop(ticket)
                record.close_time = datetime.now()
                record.close_price = position.open_price  # Will be updated with actual close
                record.profit = position.profit
                record.status = "CLOSED"
                self._trade_history.append(record)

                # Record for risk manager
                self.risk_manager.record_trade_result(position.profit)

            logger.info(f"Trade closed: {ticket} | Reason: {reason} | P&L: {position.profit}")
            return True

        return False

    def close_all_trades(self, symbol: Optional[str] = None, reason: str = "Close all") -> int:
        """
        Close all open trades.

        Args:
            symbol: Only close trades for this symbol (optional)
            reason: Reason for closing

        Returns:
            Number of trades closed
        """
        positions = self.mt5.get_positions(symbol=symbol)
        closed = 0

        for position in positions:
            if self.close_trade(position.ticket, reason):
                closed += 1

        logger.info(f"Closed {closed} trades")
        return closed

    def update_trailing_stop(
        self,
        ticket: int,
        new_stop_loss: float
    ) -> bool:
        """
        Update trailing stop for a position.

        Args:
            ticket: Position ticket
            new_stop_loss: New stop loss price

        Returns:
            True if updated successfully
        """
        positions = self.mt5.get_positions()
        position = next((p for p in positions if p.ticket == ticket), None)

        if not position:
            return False

        # Validate new stop loss
        if position.type == Signal.BUY:
            # For buy, new SL should be higher than current and below current price
            if new_stop_loss <= position.stop_loss:
                return False  # Not trailing up
        else:
            # For sell, new SL should be lower than current and above current price
            if new_stop_loss >= position.stop_loss:
                return False  # Not trailing down

        success = self.mt5.modify_position(ticket, stop_loss=new_stop_loss)

        if success:
            # Update active trade record
            if ticket in self._active_trades:
                self._active_trades[ticket].stop_loss = new_stop_loss

            logger.debug(f"Trailing stop updated: {ticket} -> SL: {new_stop_loss}")

        return success

    def manage_positions(self, strategies: Dict[str, Any]) -> None:
        """
        Manage all open positions (trailing stops, exit conditions).

        Args:
            strategies: Dictionary of active strategies
        """
        positions = self.mt5.get_positions()

        for position in positions:
            # Find the strategy that opened this trade
            strategy = None
            for strat in strategies.values():
                if hasattr(strat, 'magic_number') and position.magic_number == strat.magic_number:
                    strategy = strat
                    break

            if not strategy:
                continue

            # Get current market data
            data = self.mt5.get_ohlcv(position.symbol, strategy.timeframe, 100)
            if data is None:
                continue

            # Check exit conditions
            if strategy.should_close(position, data):
                self.close_trade(position.ticket, "Strategy exit signal")
                continue

            # Check trailing stop
            new_sl = strategy.get_trailing_stop(position, data)
            if new_sl:
                self.update_trailing_stop(position.ticket, new_sl)

    def _calculate_sl_pips(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """Calculate stop loss distance in pips."""
        symbol_info = self.mt5.get_symbol_info(symbol)
        if not symbol_info:
            return 0.0

        point = symbol_info.point
        pip_factor = 10  # Standard pip = 10 points

        return abs(entry_price - stop_loss) / (point * pip_factor)

    def get_active_trades(self) -> Dict[int, TradeRecord]:
        """Get all active trade records."""
        return self._active_trades.copy()

    def get_trade_history(self) -> List[TradeRecord]:
        """Get trade history."""
        return self._trade_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get trading statistics.

        Returns:
            Dictionary with trade statistics
        """
        history = self._trade_history

        if not history:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "total_profit": 0,
                "average_profit": 0,
                "average_loss": 0,
                "profit_factor": 0,
            }

        winning = [t for t in history if t.profit and t.profit > 0]
        losing = [t for t in history if t.profit and t.profit < 0]

        total_profit = sum(t.profit for t in history if t.profit)
        gross_profit = sum(t.profit for t in winning) if winning else 0
        gross_loss = abs(sum(t.profit for t in losing)) if losing else 0

        return {
            "total_trades": len(history),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(history) * 100 if history else 0,
            "total_profit": total_profit,
            "average_profit": gross_profit / len(winning) if winning else 0,
            "average_loss": gross_loss / len(losing) if losing else 0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else 0,
            "active_trades": len(self._active_trades),
        }
