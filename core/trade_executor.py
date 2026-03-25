"""
Advanced Trade Executor for order management.

Features:
- Full order type support (Market, Limit, Stop, Stop Limit)
- TP/SL handling: price, pips, R:R ratio, ATR multiplier
- Partial position close
- Trailing stop with activation level
- Break-even functionality
- Order retry logic with slippage handling
- Comprehensive execution logging
"""
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
from loguru import logger

from .mt5_connector import (
    MT5Connector, Signal, OrderType, OrderResult,
    SLTPType
)
from .strategy_base import TradeSignal, Position
from .risk_manager import RiskManager


class TradeStatus(Enum):
    """Trade status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    PARTIAL_CLOSED = "partial_closed"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CloseReason(Enum):
    """Reason for closing a trade."""
    MANUAL = "manual"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    BREAK_EVEN = "break_even"
    STRATEGY_EXIT = "strategy_exit"
    DAILY_LIMIT = "daily_limit"
    RISK_LIMIT = "risk_limit"
    TIME_EXIT = "time_exit"


@dataclass
class TradeRecord:
    """
    Comprehensive record of an executed trade.

    Tracks full lifecycle from signal to close with all modifications.
    """
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
    pips: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN
    close_reason: Optional[CloseReason] = None

    # Order details
    order_type: OrderType = OrderType.MARKET_BUY
    requested_price: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    swap: float = 0.0

    # Trailing stop tracking
    trailing_activated: bool = False
    max_favorable_excursion: float = 0.0  # Max profit reached
    max_adverse_excursion: float = 0.0  # Max drawdown reached

    # Modifications history
    sl_modifications: List[Tuple[datetime, float]] = field(default_factory=list)
    tp_modifications: List[Tuple[datetime, float]] = field(default_factory=list)
    partial_closes: List[Tuple[datetime, float, float]] = field(default_factory=list)  # (time, volume, profit)

    # Original SL/TP for risk calculations
    original_stop_loss: float = 0.0
    original_take_profit: float = 0.0

    def __post_init__(self):
        if self.original_stop_loss == 0:
            self.original_stop_loss = self.stop_loss
        if self.original_take_profit == 0:
            self.original_take_profit = self.take_profit


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop behavior."""
    enabled: bool = False
    activation_pips: float = 10.0  # Profit pips to activate trailing
    trail_pips: float = 5.0  # Distance to trail
    step_pips: float = 1.0  # Minimum step to update SL


@dataclass
class BreakEvenConfig:
    """Configuration for break-even functionality."""
    enabled: bool = False
    trigger_pips: float = 10.0  # Pips in profit to trigger
    offset_pips: float = 1.0  # Pips above/below entry for BE


class TradeExecutor:
    """
    Advanced Trade Executor with comprehensive order management.

    Handles:
    - All order types (Market, Limit, Stop, Stop Limit)
    - Multiple SL/TP specification methods
    - Partial position closes
    - Trailing stops with configurable activation
    - Break-even functionality
    - Order retry logic for requotes
    - Full trade lifecycle tracking

    Example:
        >>> executor = TradeExecutor(mt5, risk_manager)
        >>> ticket = executor.execute_signal(signal, "SMC Scalper")
        >>> executor.set_break_even(ticket, trigger_pips=15, offset_pips=2)
        >>> executor.enable_trailing_stop(ticket, activation_pips=20, trail_pips=10)
    """

    def __init__(
        self,
        mt5: MT5Connector,
        risk_manager: RiskManager,
        default_magic: int = 123456,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        """
        Initialize trade executor.

        Args:
            mt5: MT5 connector instance
            risk_manager: Risk manager instance
            default_magic: Default magic number for orders
            max_retries: Maximum order retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.mt5 = mt5
        self.risk_manager = risk_manager
        self.default_magic = default_magic
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Trade tracking
        self._trade_history: List[TradeRecord] = []
        self._active_trades: Dict[int, TradeRecord] = {}

        # Position management configs
        self._trailing_configs: Dict[int, TrailingStopConfig] = {}
        self._breakeven_configs: Dict[int, BreakEvenConfig] = {}

        # Execution callbacks
        self._on_trade_open: List[Callable[[TradeRecord], None]] = []
        self._on_trade_close: List[Callable[[TradeRecord], None]] = []

        # Thread safety
        self._lock = threading.RLock()

        # Position management thread
        self._management_thread: Optional[threading.Thread] = None
        self._stop_management = threading.Event()

        logger.info("TradeExecutor initialized")

    def execute_signal(
        self,
        signal: TradeSignal,
        strategy_name: str = "",
        sl_type: SLTPType = SLTPType.PRICE,
        tp_type: SLTPType = SLTPType.PRICE,
        atr_value: Optional[float] = None
    ) -> Optional[int]:
        """
        Execute a trade signal with advanced SL/TP handling.

        Args:
            signal: Trade signal to execute
            strategy_name: Name of the strategy generating the signal
            sl_type: How SL is specified (price, pips, ATR multiplier)
            tp_type: How TP is specified (price, pips, R:R ratio, ATR multiplier)
            atr_value: ATR value for ATR-based calculations

        Returns:
            Ticket number if successful, None otherwise
        """
        if signal.signal == Signal.HOLD:
            return None

        with self._lock:
            # Validate against risk manager
            can_trade, reason = self.risk_manager.can_open_trade(
                signal.symbol, signal.signal
            )
            if not can_trade:
                logger.warning(f"Risk check failed: {reason}")
                return None

            # Get current price
            tick = self.mt5.get_tick(signal.symbol)
            if not tick:
                logger.error(f"Cannot get tick for {signal.symbol}")
                return None

            entry_price = tick["ask"] if signal.signal == Signal.BUY else tick["bid"]
            if signal.entry_price > 0:
                entry_price = signal.entry_price

            # Calculate SL/TP prices
            sl_price, tp_price = self.mt5.calculate_sl_tp_price(
                symbol=signal.symbol,
                order_type=signal.signal,
                entry_price=entry_price,
                sl_value=signal.stop_loss if signal.stop_loss > 0 else None,
                tp_value=signal.take_profit if signal.take_profit > 0 else None,
                sl_type=sl_type,
                tp_type=tp_type,
                atr_value=atr_value
            )

            # Validate SL/TP
            if sl_price > 0 or tp_price > 0:
                valid, error = self.mt5.validate_sl_tp(
                    signal.symbol, signal.signal, entry_price, sl_price, tp_price
                )
                if not valid:
                    logger.warning(f"SL/TP validation failed: {error}")
                    return None

            # Calculate lot size
            lot_size = signal.lot_size
            if lot_size <= 0:
                sl_pips = self._calculate_sl_pips(
                    signal.symbol, entry_price, sl_price
                )
                lot_size = self.risk_manager.calculate_lot_size(signal.symbol, sl_pips)

            # Validate lot size
            symbol_info = self.mt5.get_symbol_info(signal.symbol)
            if symbol_info:
                lot_size = max(lot_size, symbol_info.min_lot)
                lot_size = min(lot_size, symbol_info.max_lot)
                lot_size = round(lot_size / symbol_info.lot_step) * symbol_info.lot_step

            # Execute the order
            magic = signal.magic_number if signal.magic_number > 0 else self.default_magic
            comment = f"{strategy_name}:{signal.comment}"[:31] if strategy_name else signal.comment[:31]

            result = self.mt5.place_market_order(
                symbol=signal.symbol,
                order_type=signal.signal,
                volume=lot_size,
                stop_loss=sl_price,
                take_profit=tp_price,
                magic=magic,
                comment=comment
            )

            if result.success:
                # Create trade record
                record = TradeRecord(
                    ticket=result.ticket,
                    symbol=signal.symbol,
                    signal=signal.signal,
                    entry_price=result.price,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    lot_size=lot_size,
                    strategy=strategy_name,
                    magic_number=magic,
                    open_time=datetime.now(),
                    order_type=OrderType.MARKET_BUY if signal.signal == Signal.BUY else OrderType.MARKET_SELL,
                    requested_price=entry_price,
                    slippage=result.slippage,
                    original_stop_loss=sl_price,
                    original_take_profit=tp_price
                )

                self._active_trades[result.ticket] = record
                self._notify_trade_open(record)

                logger.info(
                    f"Trade opened: {signal.signal.name} {lot_size} {signal.symbol} "
                    f"@ {result.price} (slippage: {result.slippage:.5f}) | "
                    f"SL: {sl_price} | TP: {tp_price} | Ticket: {result.ticket}"
                )

                return result.ticket

            else:
                logger.error(f"Order failed: {result.error_message}")
                return None

    def place_pending_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        price: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        expiration: Optional[datetime] = None,
        magic: int = 0,
        comment: str = "",
        strategy_name: str = ""
    ) -> Optional[int]:
        """
        Place a pending order (Limit, Stop, or Stop Limit).

        Args:
            symbol: Symbol to trade
            order_type: Order type (BUY_LIMIT, SELL_LIMIT, etc.)
            volume: Lot size
            price: Order trigger price
            stop_loss: Stop loss price
            take_profit: Take profit price
            expiration: Order expiration time
            magic: Magic number
            comment: Order comment
            strategy_name: Strategy name for tracking

        Returns:
            Order ticket if successful, None otherwise
        """
        with self._lock:
            # Validate against risk manager
            signal = Signal.BUY if "BUY" in order_type.value else Signal.SELL
            can_trade, reason = self.risk_manager.can_open_trade(symbol, signal)
            if not can_trade:
                logger.warning(f"Risk check failed: {reason}")
                return None

            result = self.mt5.place_pending_order(
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                expiration=expiration,
                magic=magic if magic > 0 else self.default_magic,
                comment=f"{strategy_name}:{comment}"[:31] if strategy_name else comment[:31]
            )

            if result.success:
                logger.info(
                    f"Pending order placed: {order_type.value} {volume} {symbol} "
                    f"@ {price} | Order: {result.ticket}"
                )
                return result.ticket

            logger.error(f"Pending order failed: {result.error_message}")
            return None

    def close_trade(
        self,
        ticket: int,
        reason: CloseReason = CloseReason.MANUAL,
        comment: str = ""
    ) -> bool:
        """
        Close a trade by ticket number.

        Args:
            ticket: Position ticket to close
            reason: Reason for closing
            comment: Additional comment

        Returns:
            True if closed successfully
        """
        with self._lock:
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
                    record.close_price = position.open_price  # Approximate
                    record.profit = position.profit
                    record.pips = self._calculate_profit_pips(position)
                    record.status = TradeStatus.CLOSED
                    record.close_reason = reason

                    self._trade_history.append(record)
                    self.risk_manager.record_trade_result(position.profit)
                    self._notify_trade_close(record)

                # Clean up configs
                self._trailing_configs.pop(ticket, None)
                self._breakeven_configs.pop(ticket, None)

                logger.info(
                    f"Trade closed: {ticket} | Reason: {reason.value} | "
                    f"P&L: ${position.profit:.2f} | {comment}"
                )
                return True

            return False

    def partial_close(
        self,
        ticket: int,
        volume: Optional[float] = None,
        percent: Optional[float] = None,
        reason: str = "Partial close"
    ) -> bool:
        """
        Partially close a position.

        Args:
            ticket: Position ticket
            volume: Volume to close (mutually exclusive with percent)
            percent: Percentage to close (0-100)
            reason: Reason for partial close

        Returns:
            True if partial close successful
        """
        with self._lock:
            # Get current position
            positions = self.mt5.get_positions()
            position = next((p for p in positions if p.ticket == ticket), None)

            if not position:
                logger.warning(f"Position {ticket} not found")
                return False

            success = self.mt5.partial_close(
                ticket=ticket,
                volume=volume,
                percent=percent
            )

            if success:
                # Update trade record
                if ticket in self._active_trades:
                    close_volume = volume if volume else position.volume * (percent / 100)
                    close_profit = position.profit * (close_volume / position.volume)

                    record = self._active_trades[ticket]
                    record.partial_closes.append((datetime.now(), close_volume, close_profit))
                    record.lot_size -= close_volume
                    record.status = TradeStatus.PARTIAL_CLOSED

                    # Record partial profit
                    self.risk_manager.record_trade_result(close_profit)

                logger.info(f"Partial close: {ticket} | {close_volume} lots | ${close_profit:.2f}")
                return True

            return False

    def close_all_trades(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None,
        reason: CloseReason = CloseReason.MANUAL
    ) -> Tuple[int, int]:
        """
        Close all open trades.

        Args:
            symbol: Only close trades for this symbol
            magic: Only close trades with this magic number
            reason: Reason for closing

        Returns:
            Tuple of (closed_count, failed_count)
        """
        positions = self.mt5.get_positions(symbol=symbol, magic=magic)
        closed = 0
        failed = 0

        for position in positions:
            if self.close_trade(position.ticket, reason):
                closed += 1
            else:
                failed += 1

        logger.info(f"Closed {closed} trades, {failed} failed | Reason: {reason.value}")
        return closed, failed

    def modify_sl_tp(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify stop loss and/or take profit for a position.

        Args:
            ticket: Position ticket
            stop_loss: New stop loss (None to keep current)
            take_profit: New take profit (None to keep current)

        Returns:
            True if modified successfully
        """
        with self._lock:
            success = self.mt5.modify_position(
                ticket=ticket,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if success and ticket in self._active_trades:
                record = self._active_trades[ticket]

                if stop_loss is not None:
                    record.sl_modifications.append((datetime.now(), stop_loss))
                    record.stop_loss = stop_loss

                if take_profit is not None:
                    record.tp_modifications.append((datetime.now(), take_profit))
                    record.take_profit = take_profit

                logger.debug(f"Position modified: {ticket} | SL: {stop_loss} | TP: {take_profit}")

            return success

    def set_break_even(
        self,
        ticket: int,
        trigger_pips: float = 10.0,
        offset_pips: float = 1.0
    ) -> bool:
        """
        Configure break-even for a position.

        Args:
            ticket: Position ticket
            trigger_pips: Pips in profit to trigger break-even
            offset_pips: Pips above/below entry for SL placement

        Returns:
            True if configured successfully
        """
        with self._lock:
            if ticket not in self._active_trades:
                return False

            self._breakeven_configs[ticket] = BreakEvenConfig(
                enabled=True,
                trigger_pips=trigger_pips,
                offset_pips=offset_pips
            )

            logger.info(f"Break-even configured: {ticket} | Trigger: {trigger_pips} pips, Offset: {offset_pips} pips")
            return True

    def enable_trailing_stop(
        self,
        ticket: int,
        activation_pips: float = 10.0,
        trail_pips: float = 5.0,
        step_pips: float = 1.0
    ) -> bool:
        """
        Enable trailing stop for a position.

        Args:
            ticket: Position ticket
            activation_pips: Profit pips to activate trailing
            trail_pips: Distance to trail
            step_pips: Minimum step to update SL

        Returns:
            True if configured successfully
        """
        with self._lock:
            if ticket not in self._active_trades:
                return False

            self._trailing_configs[ticket] = TrailingStopConfig(
                enabled=True,
                activation_pips=activation_pips,
                trail_pips=trail_pips,
                step_pips=step_pips
            )

            logger.info(
                f"Trailing stop enabled: {ticket} | Activation: {activation_pips} pips, "
                f"Trail: {trail_pips} pips, Step: {step_pips} pips"
            )
            return True

    def disable_trailing_stop(self, ticket: int) -> bool:
        """Disable trailing stop for a position."""
        with self._lock:
            if ticket in self._trailing_configs:
                del self._trailing_configs[ticket]
                return True
            return False

    def start_position_management(self, interval: float = 1.0) -> None:
        """
        Start background position management thread.

        Args:
            interval: Check interval in seconds
        """
        if self._management_thread and self._management_thread.is_alive():
            return

        self._stop_management.clear()
        self._management_thread = threading.Thread(
            target=self._position_management_loop,
            args=(interval,),
            daemon=True,
            name="PositionManager"
        )
        self._management_thread.start()
        logger.info("Position management started")

    def stop_position_management(self) -> None:
        """Stop position management thread."""
        self._stop_management.set()
        if self._management_thread:
            self._management_thread.join(timeout=5)
        logger.info("Position management stopped")

    def _position_management_loop(self, interval: float) -> None:
        """Background loop for position management."""
        while not self._stop_management.is_set():
            try:
                self._check_breakeven()
                self._check_trailing_stops()
                self._update_excursions()
            except Exception as e:
                logger.error(f"Position management error: {e}")

            time.sleep(interval)

    def _check_breakeven(self) -> None:
        """Check and apply break-even for configured positions."""
        for ticket, config in list(self._breakeven_configs.items()):
            if not config.enabled:
                continue

            try:
                if self.mt5.set_breakeven(
                    ticket=ticket,
                    trigger_pips=config.trigger_pips,
                    offset_pips=config.offset_pips
                ):
                    # Disable after successful break-even
                    config.enabled = False
                    logger.info(f"Break-even set for: {ticket}")
            except Exception as e:
                logger.error(f"Break-even error for {ticket}: {e}")

    def _check_trailing_stops(self) -> None:
        """Check and update trailing stops for configured positions."""
        for ticket, config in list(self._trailing_configs.items()):
            if not config.enabled:
                continue

            try:
                if self.mt5.update_trailing_stop(
                    ticket=ticket,
                    trail_pips=config.trail_pips,
                    activation_pips=config.activation_pips
                ):
                    if ticket in self._active_trades:
                        self._active_trades[ticket].trailing_activated = True
            except Exception as e:
                logger.error(f"Trailing stop error for {ticket}: {e}")

    def _update_excursions(self) -> None:
        """Update max favorable/adverse excursions for tracking."""
        for ticket, record in self._active_trades.items():
            try:
                positions = self.mt5.get_positions()
                position = next((p for p in positions if p.ticket == ticket), None)

                if position:
                    profit = position.profit

                    if profit > record.max_favorable_excursion:
                        record.max_favorable_excursion = profit

                    if profit < 0 and abs(profit) > record.max_adverse_excursion:
                        record.max_adverse_excursion = abs(profit)

            except Exception:
                pass

    def manage_positions_with_strategies(self, strategies: Dict[str, Any]) -> None:
        """
        Manage positions based on strategy exit signals.

        Args:
            strategies: Dictionary of active strategy instances
        """
        positions = self.mt5.get_positions()

        for position in positions:
            # Find the strategy that opened this trade
            strategy = None
            for strat in strategies.values():
                if hasattr(strat, 'magic_number') and position.magic_number == getattr(strat, 'magic_number', 0):
                    strategy = strat
                    break

            if not strategy:
                continue

            # Get current market data
            timeframe = getattr(strategy, 'timeframe', 'M15')
            data = self.mt5.get_ohlcv(position.symbol, timeframe, 100)
            if data is None:
                continue

            # Check exit conditions
            if strategy.should_close(position, data):
                self.close_trade(position.ticket, CloseReason.STRATEGY_EXIT)
                continue

            # Check for custom trailing stop from strategy
            new_sl = strategy.get_trailing_stop(position, data)
            if new_sl:
                self.modify_sl_tp(position.ticket, stop_loss=new_sl)

    def _calculate_sl_pips(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """Calculate stop loss distance in pips."""
        if stop_loss <= 0:
            return 0.0

        symbol_info = self.mt5.get_symbol_info(symbol)
        if not symbol_info:
            return 0.0

        point = symbol_info.point
        pip_factor = 10  # Standard pip = 10 points

        return abs(entry_price - stop_loss) / (point * pip_factor)

    def _calculate_profit_pips(self, position: Position) -> float:
        """Calculate profit in pips for a position."""
        symbol_info = self.mt5.get_symbol_info(position.symbol)
        if not symbol_info:
            return 0.0

        tick = self.mt5.get_tick(position.symbol)
        if not tick:
            return 0.0

        current_price = tick["bid"] if position.type == Signal.BUY else tick["ask"]
        price_diff = current_price - position.open_price

        if position.type == Signal.SELL:
            price_diff = -price_diff

        return price_diff / (symbol_info.point * 10)

    def register_trade_open_callback(self, callback: Callable[[TradeRecord], None]) -> None:
        """Register callback for trade open events."""
        self._on_trade_open.append(callback)

    def register_trade_close_callback(self, callback: Callable[[TradeRecord], None]) -> None:
        """Register callback for trade close events."""
        self._on_trade_close.append(callback)

    def _notify_trade_open(self, record: TradeRecord) -> None:
        """Notify all registered callbacks of trade open."""
        for callback in self._on_trade_open:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"Trade open callback error: {e}")

    def _notify_trade_close(self, record: TradeRecord) -> None:
        """Notify all registered callbacks of trade close."""
        for callback in self._on_trade_close:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"Trade close callback error: {e}")

    def get_active_trades(self) -> Dict[int, TradeRecord]:
        """Get all active trade records."""
        return self._active_trades.copy()

    def get_trade_history(self) -> List[TradeRecord]:
        """Get trade history."""
        return self._trade_history.copy()

    def get_trade_record(self, ticket: int) -> Optional[TradeRecord]:
        """Get trade record by ticket."""
        if ticket in self._active_trades:
            return self._active_trades[ticket]

        for record in self._trade_history:
            if record.ticket == ticket:
                return record

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive trading statistics.

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
                "total_pips": 0,
                "average_profit": 0,
                "average_loss": 0,
                "profit_factor": 0,
                "average_winner_pips": 0,
                "average_loser_pips": 0,
                "largest_winner": 0,
                "largest_loser": 0,
                "avg_mfe": 0,
                "avg_mae": 0,
                "active_trades": len(self._active_trades),
            }

        winning = [t for t in history if t.profit and t.profit > 0]
        losing = [t for t in history if t.profit and t.profit < 0]

        total_profit = sum(t.profit for t in history if t.profit)
        total_pips = sum(t.pips for t in history if t.pips)
        gross_profit = sum(t.profit for t in winning) if winning else 0
        gross_loss = abs(sum(t.profit for t in losing)) if losing else 0

        # MFE/MAE averages
        avg_mfe = sum(t.max_favorable_excursion for t in history) / len(history) if history else 0
        avg_mae = sum(t.max_adverse_excursion for t in history) / len(history) if history else 0

        return {
            "total_trades": len(history),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(history) * 100 if history else 0,
            "total_profit": total_profit,
            "total_pips": total_pips,
            "average_profit": gross_profit / len(winning) if winning else 0,
            "average_loss": gross_loss / len(losing) if losing else 0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else 0,
            "average_winner_pips": sum(t.pips for t in winning if t.pips) / len(winning) if winning else 0,
            "average_loser_pips": abs(sum(t.pips for t in losing if t.pips)) / len(losing) if losing else 0,
            "largest_winner": max((t.profit for t in winning), default=0),
            "largest_loser": min((t.profit for t in losing), default=0),
            "avg_mfe": avg_mfe,
            "avg_mae": avg_mae,
            "active_trades": len(self._active_trades),
            "trailing_active": sum(1 for c in self._trailing_configs.values() if c.enabled),
            "breakeven_pending": sum(1 for c in self._breakeven_configs.values() if c.enabled),
        }

    def get_today_statistics(self) -> Dict[str, Any]:
        """Get today's trading statistics."""
        today = datetime.now().date()
        today_trades = [
            t for t in self._trade_history
            if t.close_time and t.close_time.date() == today
        ]

        if not today_trades:
            return {
                "trades_today": 0,
                "profit_today": 0,
                "win_rate_today": 0
            }

        winning = [t for t in today_trades if t.profit and t.profit > 0]

        return {
            "trades_today": len(today_trades),
            "profit_today": sum(t.profit for t in today_trades if t.profit),
            "win_rate_today": len(winning) / len(today_trades) * 100 if today_trades else 0
        }
