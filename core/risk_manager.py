"""
Advanced Risk Manager for position sizing and comprehensive risk control.

Features:
- Position sizing based on account balance, risk %, and SL distance
- Daily loss limit with trading halt
- Max concurrent positions with symbol exposure limits
- Max drawdown circuit breaker
- Per-symbol exposure limits
- Correlation-based exposure tracking
- Equity-based position sizing
- Real-time risk status dashboard
"""
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
import threading
from loguru import logger

from .mt5_connector import MT5Connector, AccountInfo, SymbolInfo
from .strategy_base import Signal, Position


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"           # 0-25% of limits used
    MEDIUM = "medium"     # 25-50% of limits used
    HIGH = "high"         # 50-75% of limits used
    CRITICAL = "critical" # 75-100% of limits used
    HALTED = "halted"     # Trading paused


class TradingState(Enum):
    """Trading state."""
    ACTIVE = "active"
    PAUSED = "paused"
    HALTED = "halted"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class RiskLimits:
    """
    Comprehensive risk management limits.

    All percentage values are relative to account balance.
    """
    # Per-trade limits
    max_risk_per_trade: float = 2.0     # Max risk per trade (%)
    min_risk_per_trade: float = 0.5     # Minimum risk per trade (%)
    default_risk_per_trade: float = 1.0 # Default risk (%)

    # Daily limits
    max_daily_loss: float = 5.0         # Max daily loss before halt (%)
    max_daily_trades: int = 20          # Max trades per day
    daily_profit_target: float = 5.0    # Daily profit target (%)

    # Drawdown limits
    max_drawdown: float = 20.0          # Max drawdown from peak (%)
    drawdown_warning: float = 10.0      # Drawdown warning level (%)
    drawdown_reduce_size: float = 15.0  # Drawdown to reduce position size (%)

    # Position limits
    max_positions: int = 5              # Max total open positions
    max_positions_per_symbol: int = 2   # Max positions per symbol
    max_lots_per_symbol: float = 1.0    # Max lots exposure per symbol
    max_total_lots: float = 5.0         # Max total lots across all positions

    # Margin limits
    min_margin_level: float = 150.0     # Minimum margin level (%)
    margin_call_level: float = 100.0    # Margin call level (%)

    # Correlation/Exposure limits
    max_correlation_exposure: float = 50.0  # Max exposure to correlated pairs (%)

    # Time limits
    max_trade_duration_hours: int = 24  # Max time to hold a position
    weekend_close: bool = True          # Close positions before weekend

    # Circuit breaker
    consecutive_losses_pause: int = 3   # Pause after N consecutive losses
    pause_duration_minutes: int = 30    # Pause duration


@dataclass
class DailyStats:
    """Daily trading statistics with comprehensive tracking."""
    date: date
    starting_balance: float
    starting_equity: float
    current_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_losses: int = 0
    peak_equity: float = 0.0
    max_drawdown_today: float = 0.0

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.trades_count == 0:
            return 0.0
        return (self.winning_trades / self.trades_count) * 100

    @property
    def profit_factor(self) -> float:
        """Calculate profit factor."""
        if self.gross_loss == 0:
            return 0.0
        return abs(self.gross_profit / self.gross_loss)


@dataclass
class SymbolExposure:
    """Exposure tracking per symbol."""
    symbol: str
    total_lots: float = 0.0
    position_count: int = 0
    unrealized_pnl: float = 0.0
    direction: Optional[Signal] = None  # Net direction


@dataclass
class RiskEvent:
    """Risk event for logging and alerts."""
    timestamp: datetime
    event_type: str
    severity: RiskLevel
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


class RiskManager:
    """
    Advanced Risk Management System.

    Provides comprehensive risk control including:
    - Dynamic position sizing based on account and SL
    - Daily loss limits with automatic trading halt
    - Maximum drawdown circuit breaker
    - Per-symbol exposure limits
    - Real-time risk monitoring and alerts

    Example:
        >>> risk_mgr = RiskManager(mt5, limits=RiskLimits(max_risk_per_trade=1.0))
        >>> risk_mgr.initialize()
        >>> lot_size = risk_mgr.calculate_lot_size("XAUUSD", sl_pips=20)
        >>> can_trade, reason = risk_mgr.can_open_trade("XAUUSD", Signal.BUY)
    """

    # Correlated symbol groups
    CORRELATED_PAIRS = {
        "USD_POSITIVE": {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"},
        "USD_NEGATIVE": {"USDJPY", "USDCAD", "USDCHF"},
        "GOLD": {"XAUUSD", "XAGUSD"},
        "INDICES": {"US30", "US500", "US100", "DE40", "UK100"},
    }

    def __init__(
        self,
        mt5: MT5Connector,
        limits: Optional[RiskLimits] = None,
        enable_notifications: bool = True
    ):
        """
        Initialize risk manager.

        Args:
            mt5: MT5 connector instance
            limits: Risk limits configuration
            enable_notifications: Enable risk event notifications
        """
        self.mt5 = mt5
        self.limits = limits or RiskLimits()
        self._enable_notifications = enable_notifications

        # State tracking
        self._daily_stats: Optional[DailyStats] = None
        self._peak_balance: float = 0.0
        self._starting_balance: float = 0.0
        self._trading_state: TradingState = TradingState.ACTIVE
        self._pause_until: Optional[datetime] = None

        # Exposure tracking
        self._symbol_exposure: Dict[str, SymbolExposure] = {}

        # Event log
        self._risk_events: List[RiskEvent] = []
        self._max_events = 1000

        # Thread safety
        self._lock = threading.RLock()

        # Callbacks for risk alerts
        self._alert_callbacks: List[callable] = []

    def initialize(self) -> bool:
        """
        Initialize risk manager with account data.

        Returns:
            True if initialized successfully
        """
        with self._lock:
            account = self.mt5.get_account_info()
            if not account:
                logger.error("Failed to get account info for risk manager")
                return False

            self._starting_balance = account.balance
            self._peak_balance = account.equity

            self._daily_stats = DailyStats(
                date=date.today(),
                starting_balance=account.balance,
                starting_equity=account.equity,
                peak_equity=account.equity
            )

            self._update_exposure()

            logger.info(
                f"Risk manager initialized | "
                f"Balance: {account.balance:.2f} {account.currency} | "
                f"Max risk/trade: {self.limits.max_risk_per_trade}% | "
                f"Max daily loss: {self.limits.max_daily_loss}% | "
                f"Max drawdown: {self.limits.max_drawdown}%"
            )
            return True

    def calculate_lot_size(
        self,
        symbol: str,
        stop_loss_pips: float,
        risk_percent: Optional[float] = None,
        account_percent: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on risk parameters.

        Formula: lot = (balance * risk%) / (sl_pips * pip_value)

        Args:
            symbol: Trading symbol
            stop_loss_pips: Stop loss distance in pips
            risk_percent: Risk per trade percentage (uses default if not provided)
            account_percent: Override to use percentage of account balance

        Returns:
            Calculated lot size
        """
        symbol_info = self.mt5.get_symbol_info(symbol)
        account = self.mt5.get_account_info()

        if not account or not symbol_info:
            logger.error("Failed to get account/symbol info for lot calculation")
            return symbol_info.min_lot if symbol_info else 0.01

        # Determine risk percentage
        if risk_percent is None:
            risk_percent = self.limits.default_risk_per_trade

        # Apply drawdown reduction
        current_drawdown = self.get_current_drawdown()
        if current_drawdown >= self.limits.drawdown_reduce_size:
            reduction_factor = 0.5  # Reduce position size by 50%
            risk_percent *= reduction_factor
            logger.info(f"Position size reduced due to drawdown: {current_drawdown:.2f}%")

        # Clamp risk to limits
        risk_percent = max(
            self.limits.min_risk_per_trade,
            min(risk_percent, self.limits.max_risk_per_trade)
        )

        # Calculate risk amount
        balance_to_use = account.balance
        if account_percent:
            balance_to_use = account.balance * (account_percent / 100)

        risk_amount = balance_to_use * (risk_percent / 100)

        # Calculate pip value
        point = symbol_info.point
        tick_value = symbol_info.tick_value
        tick_size = symbol_info.tick_size
        contract_size = symbol_info.contract_size

        # Pip value calculation varies by symbol type
        if tick_size > 0:
            pip_value = (tick_value / tick_size) * point * 10
        else:
            pip_value = tick_value * 10

        # For gold/metals, pip value is typically $1 per 0.01 lot
        if "XAU" in symbol or "XAG" in symbol:
            pip_value = 1.0  # Simplified for gold

        # Calculate lot size
        if stop_loss_pips > 0 and pip_value > 0:
            lot_size = risk_amount / (stop_loss_pips * pip_value)
        else:
            lot_size = symbol_info.min_lot

        # Round to lot step and clamp to min/max
        lot_step = symbol_info.lot_step
        lot_size = round(lot_size / lot_step) * lot_step
        lot_size = max(symbol_info.min_lot, min(lot_size, symbol_info.max_lot))

        # Check against symbol exposure limit
        current_exposure = self._symbol_exposure.get(symbol)
        if current_exposure:
            remaining_lots = self.limits.max_lots_per_symbol - current_exposure.total_lots
            if lot_size > remaining_lots:
                lot_size = max(0, remaining_lots)

        # Check against total exposure limit
        total_lots = sum(e.total_lots for e in self._symbol_exposure.values())
        remaining_total = self.limits.max_total_lots - total_lots
        if lot_size > remaining_total:
            lot_size = max(0, remaining_total)

        logger.debug(
            f"Lot calculation: {symbol} | Risk: {risk_percent}% | "
            f"SL: {stop_loss_pips} pips | Lot: {lot_size}"
        )

        return lot_size

    def can_open_trade(
        self,
        symbol: str,
        signal: Signal,
        lot_size: float = 0.01
    ) -> Tuple[bool, str]:
        """
        Check if a new trade can be opened.

        Args:
            symbol: Symbol to trade
            signal: Trade direction
            lot_size: Intended lot size

        Returns:
            Tuple of (can_trade, reason)
        """
        with self._lock:
            # Check trading state
            if self._trading_state == TradingState.HALTED:
                return False, "Trading halted - risk limits exceeded"

            if self._trading_state == TradingState.CIRCUIT_BREAKER:
                return False, "Circuit breaker active - consecutive losses"

            if self._trading_state == TradingState.PAUSED:
                if self._pause_until and datetime.now() < self._pause_until:
                    remaining = (self._pause_until - datetime.now()).seconds // 60
                    return False, f"Trading paused - {remaining} minutes remaining"
                else:
                    self._trading_state = TradingState.ACTIVE
                    self._pause_until = None

            # Check daily stats reset
            self._check_daily_reset()

            # Check daily loss limit
            if self._is_daily_limit_reached():
                self._trading_state = TradingState.HALTED
                self._log_risk_event(
                    "DAILY_LIMIT",
                    RiskLevel.CRITICAL,
                    "Daily loss limit reached - trading halted"
                )
                return False, "Daily loss limit reached"

            # Check max drawdown
            if self._is_max_drawdown_reached():
                self._trading_state = TradingState.HALTED
                self._log_risk_event(
                    "MAX_DRAWDOWN",
                    RiskLevel.CRITICAL,
                    "Maximum drawdown reached - trading halted"
                )
                return False, "Maximum drawdown reached"

            # Check daily trades limit
            if self._daily_stats and self._daily_stats.trades_count >= self.limits.max_daily_trades:
                return False, f"Daily trade limit ({self.limits.max_daily_trades}) reached"

            # Check position limits
            positions = self.mt5.get_positions()

            if len(positions) >= self.limits.max_positions:
                return False, f"Maximum positions ({self.limits.max_positions}) reached"

            # Check positions per symbol
            symbol_positions = [p for p in positions if p.symbol == symbol]
            if len(symbol_positions) >= self.limits.max_positions_per_symbol:
                return False, f"Maximum positions for {symbol} ({self.limits.max_positions_per_symbol}) reached"

            # Check symbol exposure
            exposure = self._symbol_exposure.get(symbol, SymbolExposure(symbol=symbol))
            if exposure.total_lots + lot_size > self.limits.max_lots_per_symbol:
                return False, f"Maximum lot exposure for {symbol} would be exceeded"

            # Check total exposure
            total_lots = sum(e.total_lots for e in self._symbol_exposure.values())
            if total_lots + lot_size > self.limits.max_total_lots:
                return False, "Maximum total lot exposure would be exceeded"

            # Check margin
            account = self.mt5.get_account_info()
            if account:
                if account.margin_level > 0 and account.margin_level < self.limits.min_margin_level:
                    return False, f"Insufficient margin (level: {account.margin_level:.0f}% < {self.limits.min_margin_level:.0f}%)"

                if account.free_margin < 100:  # Minimum free margin
                    return False, "Insufficient free margin"

            # Check correlation exposure (optional)
            if self.limits.max_correlation_exposure < 100:
                corr_exposure = self._calculate_correlation_exposure(symbol)
                if corr_exposure > self.limits.max_correlation_exposure:
                    return False, f"Correlation exposure limit exceeded ({corr_exposure:.1f}%)"

            return True, "OK"

    def validate_trade_signal(
        self,
        symbol: str,
        signal: Signal,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Tuple[bool, str]:
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

        # Calculate minimum stop distance
        min_distance = symbol_info.stops_level * symbol_info.point
        if min_distance == 0:
            min_distance = symbol_info.point * 10  # Default 10 points

        # Validate stop loss distance
        sl_distance = abs(entry_price - stop_loss)
        if stop_loss > 0 and sl_distance < min_distance:
            return False, f"Stop loss too close: {sl_distance:.5f} < {min_distance:.5f}"

        # Validate take profit distance
        tp_distance = abs(entry_price - take_profit)
        if take_profit > 0 and tp_distance < min_distance:
            return False, f"Take profit too close: {tp_distance:.5f} < {min_distance:.5f}"

        # Validate direction consistency
        if signal == Signal.BUY:
            if stop_loss > 0 and stop_loss >= entry_price:
                return False, "BUY stop loss must be below entry"
            if take_profit > 0 and take_profit <= entry_price:
                return False, "BUY take profit must be above entry"
        elif signal == Signal.SELL:
            if stop_loss > 0 and stop_loss <= entry_price:
                return False, "SELL stop loss must be above entry"
            if take_profit > 0 and take_profit >= entry_price:
                return False, "SELL take profit must be below entry"

        # Calculate risk:reward ratio
        if stop_loss > 0 and take_profit > 0:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0

            if rr_ratio < 1.0:
                logger.warning(f"Low R:R ratio: {rr_ratio:.2f}")
                # Not rejecting, just warning

        return True, "Valid"

    def record_trade_result(self, profit: float, symbol: str = "") -> None:
        """
        Record a trade result for statistics.

        Args:
            profit: Trade profit (positive or negative)
            symbol: Symbol traded
        """
        with self._lock:
            if not self._daily_stats:
                return

            self._daily_stats.trades_count += 1
            self._daily_stats.realized_pnl += profit

            if profit > 0:
                self._daily_stats.winning_trades += 1
                self._daily_stats.gross_profit += profit
                self._daily_stats.consecutive_losses = 0

                if profit > self._daily_stats.largest_win:
                    self._daily_stats.largest_win = profit
            else:
                self._daily_stats.losing_trades += 1
                self._daily_stats.gross_loss += abs(profit)
                self._daily_stats.consecutive_losses += 1

                if profit < self._daily_stats.largest_loss:
                    self._daily_stats.largest_loss = profit

            # Check consecutive losses for circuit breaker
            if self._daily_stats.consecutive_losses >= self.limits.consecutive_losses_pause:
                self._activate_circuit_breaker()

            # Update exposure
            self._update_exposure()

            logger.debug(
                f"Trade recorded: ${profit:+.2f} | "
                f"Daily P&L: ${self._daily_stats.realized_pnl:+.2f} | "
                f"Win rate: {self._daily_stats.win_rate:.1f}%"
            )

    def _check_daily_reset(self) -> None:
        """Check and reset daily stats if new day."""
        if not self._daily_stats or self._daily_stats.date != date.today():
            account = self.mt5.get_account_info()

            self._daily_stats = DailyStats(
                date=date.today(),
                starting_balance=account.balance if account else 0,
                starting_equity=account.equity if account else 0,
                peak_equity=account.equity if account else 0
            )

            # Reset trading state on new day
            if self._trading_state in [TradingState.HALTED, TradingState.CIRCUIT_BREAKER]:
                self._trading_state = TradingState.ACTIVE
                logger.info("Daily reset - trading state restored to active")

    def _is_daily_limit_reached(self) -> bool:
        """Check if daily loss limit is reached."""
        if not self._daily_stats:
            return False

        account = self.mt5.get_account_info()
        if not account:
            return False

        daily_pnl = account.equity - self._daily_stats.starting_equity
        daily_pnl_percent = (daily_pnl / self._daily_stats.starting_balance) * 100

        # Update daily stats
        self._daily_stats.current_pnl = daily_pnl
        self._daily_stats.unrealized_pnl = daily_pnl - self._daily_stats.realized_pnl

        if daily_pnl_percent <= -self.limits.max_daily_loss:
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

        # Update daily peak
        if self._daily_stats and account.equity > self._daily_stats.peak_equity:
            self._daily_stats.peak_equity = account.equity

        drawdown = self.get_current_drawdown()

        # Update max drawdown today
        if self._daily_stats and drawdown > self._daily_stats.max_drawdown_today:
            self._daily_stats.max_drawdown_today = drawdown

        if drawdown >= self.limits.max_drawdown:
            return True

        # Log warning levels
        if drawdown >= self.limits.drawdown_warning:
            self._log_risk_event(
                "DRAWDOWN_WARNING",
                RiskLevel.HIGH,
                f"Drawdown at warning level: {drawdown:.2f}%"
            )

        return False

    def _calculate_correlation_exposure(self, symbol: str) -> float:
        """Calculate correlation-based exposure percentage."""
        # Find symbol group
        symbol_group = None
        for group_name, symbols in self.CORRELATED_PAIRS.items():
            if symbol in symbols:
                symbol_group = group_name
                break

        if not symbol_group:
            return 0.0

        # Calculate exposure to correlated symbols
        correlated_exposure = 0.0
        account = self.mt5.get_account_info()
        if not account:
            return 0.0

        positions = self.mt5.get_positions()
        for pos in positions:
            if pos.symbol in self.CORRELATED_PAIRS.get(symbol_group, set()):
                # Simple exposure calculation
                symbol_info = self.mt5.get_symbol_info(pos.symbol)
                if symbol_info:
                    exposure = pos.volume * symbol_info.contract_size
                    correlated_exposure += exposure

        # Calculate as percentage of balance
        if account.balance > 0:
            return (correlated_exposure / account.balance) * 100

        return 0.0

    def _update_exposure(self) -> None:
        """Update symbol exposure tracking."""
        positions = self.mt5.get_positions()
        self._symbol_exposure.clear()

        for pos in positions:
            if pos.symbol not in self._symbol_exposure:
                self._symbol_exposure[pos.symbol] = SymbolExposure(symbol=pos.symbol)

            exposure = self._symbol_exposure[pos.symbol]
            exposure.total_lots += pos.volume
            exposure.position_count += 1
            exposure.unrealized_pnl += pos.profit

            # Track net direction
            if exposure.direction is None:
                exposure.direction = pos.type
            elif exposure.direction != pos.type:
                exposure.direction = None  # Mixed direction

    def _activate_circuit_breaker(self) -> None:
        """Activate circuit breaker after consecutive losses."""
        self._trading_state = TradingState.CIRCUIT_BREAKER
        self._pause_until = datetime.now() + timedelta(minutes=self.limits.pause_duration_minutes)

        self._log_risk_event(
            "CIRCUIT_BREAKER",
            RiskLevel.CRITICAL,
            f"Circuit breaker activated - {self.limits.consecutive_losses_pause} consecutive losses. "
            f"Pause for {self.limits.pause_duration_minutes} minutes."
        )

        logger.warning(
            f"Circuit breaker activated! "
            f"Trading paused until {self._pause_until.strftime('%H:%M:%S')}"
        )

    def _log_risk_event(self, event_type: str, severity: RiskLevel, message: str, data: Dict = None) -> None:
        """Log a risk event."""
        event = RiskEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            message=message,
            data=data or {}
        )

        self._risk_events.append(event)

        # Trim events list
        if len(self._risk_events) > self._max_events:
            self._risk_events = self._risk_events[-self._max_events:]

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Risk alert callback error: {e}")

    def register_alert_callback(self, callback: callable) -> None:
        """Register callback for risk alerts."""
        self._alert_callbacks.append(callback)

    def get_current_drawdown(self) -> float:
        """Get current drawdown percentage from peak."""
        account = self.mt5.get_account_info()
        if not account or self._peak_balance == 0:
            return 0.0

        return ((self._peak_balance - account.equity) / self._peak_balance) * 100

    def get_daily_stats(self) -> Optional[DailyStats]:
        """Get current daily statistics."""
        return self._daily_stats

    def get_trading_state(self) -> TradingState:
        """Get current trading state."""
        return self._trading_state

    def resume_trading(self) -> bool:
        """Manually resume trading after halt (use with caution)."""
        with self._lock:
            if self._trading_state in [TradingState.HALTED, TradingState.CIRCUIT_BREAKER, TradingState.PAUSED]:
                self._trading_state = TradingState.ACTIVE
                self._pause_until = None

                self._log_risk_event(
                    "TRADING_RESUMED",
                    RiskLevel.MEDIUM,
                    "Trading manually resumed"
                )

                logger.info("Trading manually resumed")
                return True
            return False

    def pause_trading(self, duration_minutes: int = 30) -> None:
        """Manually pause trading."""
        with self._lock:
            self._trading_state = TradingState.PAUSED
            self._pause_until = datetime.now() + timedelta(minutes=duration_minutes)

            self._log_risk_event(
                "TRADING_PAUSED",
                RiskLevel.MEDIUM,
                f"Trading manually paused for {duration_minutes} minutes"
            )

    def get_risk_level(self) -> RiskLevel:
        """Get current overall risk level."""
        drawdown = self.get_current_drawdown()

        # Calculate risk score (0-100)
        risk_score = 0

        # Drawdown contribution (40% weight)
        drawdown_ratio = drawdown / self.limits.max_drawdown
        risk_score += drawdown_ratio * 40

        # Position usage contribution (30% weight)
        positions = self.mt5.get_positions()
        position_ratio = len(positions) / self.limits.max_positions
        risk_score += position_ratio * 30

        # Daily loss contribution (30% weight)
        if self._daily_stats and self._daily_stats.starting_balance > 0:
            daily_loss_ratio = abs(min(0, self._daily_stats.current_pnl)) / \
                               (self._daily_stats.starting_balance * self.limits.max_daily_loss / 100)
            risk_score += min(daily_loss_ratio, 1.0) * 30

        if self._trading_state in [TradingState.HALTED, TradingState.CIRCUIT_BREAKER]:
            return RiskLevel.HALTED
        elif risk_score >= 75:
            return RiskLevel.CRITICAL
        elif risk_score >= 50:
            return RiskLevel.HIGH
        elif risk_score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def get_risk_status(self) -> Dict[str, Any]:
        """
        Get comprehensive risk status summary.

        Returns:
            Dictionary with complete risk metrics
        """
        account = self.mt5.get_account_info()
        positions = self.mt5.get_positions()

        # Calculate total lots
        total_lots = sum(p.volume for p in positions)
        total_unrealized = sum(p.profit for p in positions)

        # Symbol breakdown
        symbol_breakdown = {}
        for sym, exp in self._symbol_exposure.items():
            symbol_breakdown[sym] = {
                "lots": exp.total_lots,
                "positions": exp.position_count,
                "unrealized_pnl": exp.unrealized_pnl
            }

        return {
            # Account metrics
            "balance": account.balance if account else 0,
            "equity": account.equity if account else 0,
            "margin": account.margin if account else 0,
            "free_margin": account.free_margin if account else 0,
            "margin_level": account.margin_level if account else 0,

            # Drawdown metrics
            "peak_balance": self._peak_balance,
            "drawdown_percent": self.get_current_drawdown(),
            "drawdown_warning_level": self.limits.drawdown_warning,
            "max_drawdown_level": self.limits.max_drawdown,

            # Position metrics
            "open_positions": len(positions),
            "max_positions": self.limits.max_positions,
            "total_lots": total_lots,
            "max_total_lots": self.limits.max_total_lots,
            "unrealized_pnl": total_unrealized,

            # Daily metrics
            "daily_pnl": self._daily_stats.current_pnl if self._daily_stats else 0,
            "daily_realized_pnl": self._daily_stats.realized_pnl if self._daily_stats else 0,
            "daily_trades": self._daily_stats.trades_count if self._daily_stats else 0,
            "daily_max_trades": self.limits.max_daily_trades,
            "daily_win_rate": self._daily_stats.win_rate if self._daily_stats else 0,
            "consecutive_losses": self._daily_stats.consecutive_losses if self._daily_stats else 0,

            # State
            "trading_state": self._trading_state.value,
            "risk_level": self.get_risk_level().value,
            "daily_limit_reached": self._is_daily_limit_reached(),
            "max_drawdown_reached": self._is_max_drawdown_reached(),
            "pause_until": self._pause_until.isoformat() if self._pause_until else None,

            # Exposure breakdown
            "symbol_exposure": symbol_breakdown,

            # Limits
            "limits": {
                "max_risk_per_trade": self.limits.max_risk_per_trade,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_drawdown": self.limits.max_drawdown,
                "max_positions": self.limits.max_positions,
                "max_positions_per_symbol": self.limits.max_positions_per_symbol,
            }
        }

    def get_recent_events(self, limit: int = 20) -> List[RiskEvent]:
        """Get recent risk events."""
        return self._risk_events[-limit:]
