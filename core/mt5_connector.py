"""
MetaTrader 5 Connection and API Wrapper.
Handles all communication with the MT5 terminal.

Enhanced with:
- Multi-account support via AccountManager
- Pending order types (Limit, Stop, Stop Limit)
- Partial position close
- Order retry logic
- Comprehensive error handling
"""
import platform
import pandas as pd
import threading
import time
from enum import Enum

# Use mock MT5 on non-Windows platforms
if platform.system() == "Windows":
    import MetaTrader5 as mt5
else:
    # Mock MT5 for development on macOS/Linux
    import sys
    import os
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mt5_mock",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "mt5_mock.py")
    )
    mt5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt5)

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from loguru import logger

from .strategy_base import Signal, Position


class OrderType(Enum):
    """Order type enumeration."""
    MARKET_BUY = "market_buy"
    MARKET_SELL = "market_sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"
    BUY_STOP_LIMIT = "buy_stop_limit"
    SELL_STOP_LIMIT = "sell_stop_limit"


class SLTPType(Enum):
    """Stop Loss / Take Profit specification type."""
    PRICE = "price"
    PIPS = "pips"
    RR_RATIO = "rr_ratio"  # Risk:Reward ratio
    ATR_MULTIPLIER = "atr_multiplier"


@dataclass
class AccountInfo:
    """MT5 Account information."""
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str
    leverage: int
    server: str
    company: str
    trade_allowed: bool = True
    expert_allowed: bool = True


@dataclass
class SymbolInfo:
    """MT5 Symbol information."""
    name: str
    description: str
    point: float
    digits: int
    spread: int
    min_lot: float
    max_lot: float
    lot_step: float
    tick_size: float
    tick_value: float
    contract_size: float
    trade_mode: int
    stops_level: int = 0  # Minimum stop distance in points
    freeze_level: int = 0  # Freeze level in points


@dataclass
class OrderResult:
    """Order execution result."""
    success: bool
    ticket: int = 0
    order_id: int = 0
    volume: float = 0.0
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    comment: str = ""
    retcode: int = 0
    retcode_external: int = 0
    request_id: int = 0
    slippage: float = 0.0
    error_message: str = ""


@dataclass
class ExecutionLog:
    """Log entry for order execution."""
    timestamp: datetime
    symbol: str
    order_type: str
    volume: float
    requested_price: float
    executed_price: float
    slippage: float
    ticket: int
    success: bool
    error: str = ""
    retries: int = 0


class MT5Connector:
    """
    MetaTrader 5 API Wrapper.

    Provides methods for:
    - Connection management with health monitoring
    - Account information retrieval
    - Market data retrieval (OHLCV, ticks)
    - Full order type support (Market, Limit, Stop, Stop Limit)
    - Position management (open, close, partial close, modify)
    - Trailing stop and break-even functionality
    - Order retry logic for requotes

    Example:
        >>> connector = MT5Connector()
        >>> connector.connect(login=12345, password="pass", server="Broker-Demo")
        >>> positions = connector.get_positions()
        >>> connector.place_market_order("XAUUSD", Signal.BUY, 0.1, sl=1900, tp=2000)
    """

    # Timeframe mapping
    TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }

    # MT5 Order type mapping
    MT5_ORDER_TYPES = {
        OrderType.MARKET_BUY: mt5.ORDER_TYPE_BUY,
        OrderType.MARKET_SELL: mt5.ORDER_TYPE_SELL,
        OrderType.BUY_LIMIT: mt5.ORDER_TYPE_BUY_LIMIT,
        OrderType.SELL_LIMIT: mt5.ORDER_TYPE_SELL_LIMIT,
        OrderType.BUY_STOP: mt5.ORDER_TYPE_BUY_STOP,
        OrderType.SELL_STOP: mt5.ORDER_TYPE_SELL_STOP,
        OrderType.BUY_STOP_LIMIT: mt5.ORDER_TYPE_BUY_STOP_LIMIT,
        OrderType.SELL_STOP_LIMIT: mt5.ORDER_TYPE_SELL_STOP_LIMIT,
    }

    def __init__(self, max_retries: int = 3, retry_delay: float = 0.5):
        """
        Initialize MT5 connector.

        Args:
            max_retries: Maximum order retry attempts on requote
            retry_delay: Delay between retries in seconds
        """
        self._connected = False
        self._account_info: Optional[AccountInfo] = None
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._execution_log: List[ExecutionLog] = []
        self._lock = threading.RLock()
        self._symbols_cache: Dict[str, SymbolInfo] = {}

    def connect(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
        timeout: int = 60000
    ) -> bool:
        """
        Connect to MT5 terminal.

        Args:
            login: Account login number (optional if already logged in)
            password: Account password
            server: Broker server name
            path: Path to MT5 terminal executable
            timeout: Connection timeout in milliseconds

        Returns:
            True if connected successfully
        """
        with self._lock:
            try:
                # Initialize MT5
                init_params = {"timeout": timeout}
                if path:
                    init_params["path"] = path

                if not mt5.initialize(**init_params):
                    error = mt5.last_error()
                    logger.error(f"MT5 initialization failed: {error}")
                    return False

                # Login if credentials provided
                if login and password and server:
                    if not mt5.login(login, password=password, server=server):
                        error = mt5.last_error()
                        logger.error(f"MT5 login failed: {error}")
                        mt5.shutdown()
                        return False

                self._connected = True
                self._update_account_info()
                logger.info(f"Connected to MT5: {self._account_info.server if self._account_info else 'Unknown'}")
                return True

            except Exception as e:
                logger.error(f"Connection error: {e}")
                return False

    def disconnect(self) -> None:
        """Disconnect from MT5 terminal."""
        with self._lock:
            if self._connected:
                try:
                    mt5.shutdown()
                except Exception as e:
                    logger.error(f"Disconnect error: {e}")
                finally:
                    self._connected = False
                    logger.info("Disconnected from MT5")

    def is_connected(self) -> bool:
        """
        Check if connected to MT5.

        Returns:
            True if connection is active
        """
        if not self._connected:
            return False
        try:
            info = mt5.terminal_info()
            return info is not None
        except Exception:
            return False

    def _update_account_info(self) -> None:
        """Update cached account information."""
        try:
            info = mt5.account_info()
            if info:
                self._account_info = AccountInfo(
                    login=info.login,
                    balance=info.balance,
                    equity=info.equity,
                    margin=info.margin,
                    free_margin=info.margin_free,
                    margin_level=info.margin_level if info.margin_level else 0,
                    profit=info.profit,
                    currency=info.currency,
                    leverage=info.leverage,
                    server=info.server,
                    company=info.company,
                    trade_allowed=getattr(info, 'trade_allowed', True),
                    expert_allowed=getattr(info, 'trade_expert', True),
                )
        except Exception as e:
            logger.error(f"Failed to update account info: {e}")

    def get_account_info(self) -> Optional[AccountInfo]:
        """
        Get current account information.

        Returns:
            AccountInfo object with current account data
        """
        self._update_account_info()
        return self._account_info

    def get_symbol_info(self, symbol: str, use_cache: bool = True) -> Optional[SymbolInfo]:
        """
        Get symbol information.

        Args:
            symbol: Symbol name (e.g., "XAUUSD")
            use_cache: Whether to use cached info

        Returns:
            SymbolInfo object or None if symbol not found
        """
        if use_cache and symbol in self._symbols_cache:
            return self._symbols_cache[symbol]

        try:
            info = mt5.symbol_info(symbol)
            if not info:
                logger.warning(f"Symbol not found: {symbol}")
                return None

            symbol_info = SymbolInfo(
                name=info.name,
                description=info.description,
                point=info.point,
                digits=info.digits,
                spread=info.spread,
                min_lot=info.volume_min,
                max_lot=info.volume_max,
                lot_step=info.volume_step,
                tick_size=info.trade_tick_size,
                tick_value=info.trade_tick_value,
                contract_size=info.trade_contract_size,
                trade_mode=info.trade_mode,
                stops_level=getattr(info, 'trade_stops_level', 0),
                freeze_level=getattr(info, 'trade_freeze_level', 0),
            )

            self._symbols_cache[symbol] = symbol_info
            return symbol_info

        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current tick for symbol.

        Args:
            symbol: Symbol name

        Returns:
            Dict with bid, ask, last, time, spread
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return None

            symbol_info = self.get_symbol_info(symbol)
            spread_points = 0
            if symbol_info:
                spread_points = round((tick.ask - tick.bid) / symbol_info.point)

            return {
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "volume": tick.volume,
                "time": datetime.fromtimestamp(tick.time),
                "spread": spread_points,
            }
        except Exception as e:
            logger.error(f"Error getting tick for {symbol}: {e}")
            return None

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100,
        start_time: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get OHLCV data for symbol.

        Args:
            symbol: Symbol name
            timeframe: Timeframe string (M1, M5, M15, M30, H1, H4, D1, W1, MN1)
            count: Number of bars to retrieve
            start_time: Start time for historical data

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        tf = self.TIMEFRAMES.get(timeframe.upper())
        if tf is None:
            logger.error(f"Invalid timeframe: {timeframe}")
            return None

        try:
            # Enable symbol if not visible
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Failed to select symbol: {symbol}")

            if start_time:
                rates = mt5.copy_rates_from(symbol, tf, start_time, count)
            else:
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

            if rates is None or len(rates) == 0:
                logger.warning(f"No data retrieved for {symbol} {timeframe}")
                return None

            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.rename(columns={
                "tick_volume": "volume",
                "real_volume": "real_volume",
            })

            return df[["time", "open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.error(f"Error getting OHLCV for {symbol}: {e}")
            return None

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV data for backtesting.

        Args:
            symbol: Symbol name
            timeframe: Timeframe string
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with OHLCV data
        """
        tf = self.TIMEFRAMES.get(timeframe.upper())
        if tf is None:
            logger.error(f"Invalid timeframe: {timeframe}")
            return None

        try:
            rates = mt5.copy_rates_range(symbol, tf, start_date, end_date)

            if rates is None or len(rates) == 0:
                logger.warning(f"No historical data for {symbol}")
                return None

            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.rename(columns={"tick_volume": "volume"})

            return df[["time", "open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return None

    def calculate_sl_tp_price(
        self,
        symbol: str,
        order_type: Signal,
        entry_price: float,
        sl_value: Optional[float] = None,
        tp_value: Optional[float] = None,
        sl_type: SLTPType = SLTPType.PRICE,
        tp_type: SLTPType = SLTPType.PRICE,
        atr_value: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Calculate SL/TP prices from various specification types.

        Args:
            symbol: Trading symbol
            order_type: BUY or SELL signal
            entry_price: Entry price for the order
            sl_value: Stop loss value
            tp_value: Take profit value
            sl_type: How SL is specified (price, pips, RR ratio, ATR mult)
            tp_type: How TP is specified
            atr_value: ATR value for ATR-based calculations

        Returns:
            Tuple of (stop_loss_price, take_profit_price)
        """
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return 0.0, 0.0

        point = symbol_info.point
        is_buy = order_type == Signal.BUY

        sl_price = 0.0
        tp_price = 0.0

        # Calculate Stop Loss
        if sl_value is not None and sl_value > 0:
            if sl_type == SLTPType.PRICE:
                sl_price = sl_value
            elif sl_type == SLTPType.PIPS:
                sl_pips = sl_value * 10 * point  # Convert pips to price distance
                sl_price = entry_price - sl_pips if is_buy else entry_price + sl_pips
            elif sl_type == SLTPType.ATR_MULTIPLIER and atr_value:
                sl_distance = atr_value * sl_value
                sl_price = entry_price - sl_distance if is_buy else entry_price + sl_distance

        # Calculate Take Profit
        if tp_value is not None and tp_value > 0:
            if tp_type == SLTPType.PRICE:
                tp_price = tp_value
            elif tp_type == SLTPType.PIPS:
                tp_pips = tp_value * 10 * point
                tp_price = entry_price + tp_pips if is_buy else entry_price - tp_pips
            elif tp_type == SLTPType.RR_RATIO and sl_price > 0:
                # TP based on R:R ratio (e.g., 1:2 means TP is 2x the SL distance)
                sl_distance = abs(entry_price - sl_price)
                tp_distance = sl_distance * tp_value
                tp_price = entry_price + tp_distance if is_buy else entry_price - tp_distance
            elif tp_type == SLTPType.ATR_MULTIPLIER and atr_value:
                tp_distance = atr_value * tp_value
                tp_price = entry_price + tp_distance if is_buy else entry_price - tp_distance

        # Round to symbol precision
        sl_price = round(sl_price, symbol_info.digits)
        tp_price = round(tp_price, symbol_info.digits)

        return sl_price, tp_price

    def validate_sl_tp(
        self,
        symbol: str,
        order_type: Signal,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Tuple[bool, str]:
        """
        Validate SL/TP against broker minimum stop distance.

        Args:
            symbol: Trading symbol
            order_type: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Tuple of (is_valid, error_message)
        """
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return False, "Symbol info not available"

        min_distance = symbol_info.stops_level * symbol_info.point
        is_buy = order_type == Signal.BUY

        # Validate Stop Loss
        if stop_loss > 0:
            sl_distance = abs(entry_price - stop_loss)
            if sl_distance < min_distance:
                return False, f"SL too close. Minimum distance: {min_distance:.5f}"

            # Check direction
            if is_buy and stop_loss >= entry_price:
                return False, "SL must be below entry price for BUY orders"
            if not is_buy and stop_loss <= entry_price:
                return False, "SL must be above entry price for SELL orders"

        # Validate Take Profit
        if take_profit > 0:
            tp_distance = abs(entry_price - take_profit)
            if tp_distance < min_distance:
                return False, f"TP too close. Minimum distance: {min_distance:.5f}"

            # Check direction
            if is_buy and take_profit <= entry_price:
                return False, "TP must be above entry price for BUY orders"
            if not is_buy and take_profit >= entry_price:
                return False, "TP must be below entry price for SELL orders"

        return True, ""

    def place_market_order(
        self,
        symbol: str,
        order_type: Signal,
        volume: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        magic: int = 0,
        comment: str = "",
        deviation: int = 20
    ) -> OrderResult:
        """
        Place a market order with retry logic.

        Args:
            symbol: Symbol to trade
            order_type: Signal.BUY or Signal.SELL
            volume: Lot size
            stop_loss: Stop loss price (0 to disable)
            take_profit: Take profit price (0 to disable)
            magic: Magic number for EA identification
            comment: Order comment
            deviation: Maximum slippage in points

        Returns:
            OrderResult with execution details
        """
        for attempt in range(self._max_retries + 1):
            try:
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    return OrderResult(
                        success=False,
                        error_message=f"Cannot get tick for {symbol}"
                    )

                if order_type == Signal.BUY:
                    price = tick.ask
                    mt5_type = mt5.ORDER_TYPE_BUY
                elif order_type == Signal.SELL:
                    price = tick.bid
                    mt5_type = mt5.ORDER_TYPE_SELL
                else:
                    return OrderResult(
                        success=False,
                        error_message="Invalid order type"
                    )

                # Validate SL/TP
                if stop_loss > 0 or take_profit > 0:
                    valid, error = self.validate_sl_tp(
                        symbol, order_type, price, stop_loss, take_profit
                    )
                    if not valid:
                        return OrderResult(
                            success=False,
                            error_message=error
                        )

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5_type,
                    "price": price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "deviation": deviation,
                    "magic": magic,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(request)

                if result is None:
                    error = mt5.last_error()
                    if attempt < self._max_retries:
                        logger.warning(f"Order failed (attempt {attempt + 1}): {error}, retrying...")
                        time.sleep(self._retry_delay)
                        continue
                    return OrderResult(
                        success=False,
                        error_message=f"Order failed: {error}"
                    )

                # Check for requote
                if result.retcode == mt5.TRADE_RETCODE_REQUOTE:
                    if attempt < self._max_retries:
                        logger.warning(f"Requote received (attempt {attempt + 1}), retrying...")
                        time.sleep(self._retry_delay)
                        continue

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    return OrderResult(
                        success=False,
                        ticket=0,
                        retcode=result.retcode,
                        error_message=f"Order failed: {result.comment} (code: {result.retcode})"
                    )

                # Calculate slippage
                slippage = abs(result.price - price)

                # Log execution
                self._log_execution(
                    symbol=symbol,
                    order_type=order_type.name,
                    volume=volume,
                    requested_price=price,
                    executed_price=result.price,
                    slippage=slippage,
                    ticket=result.order,
                    success=True,
                    retries=attempt
                )

                logger.info(
                    f"Order placed: {order_type.name} {volume} {symbol} @ {result.price} "
                    f"(requested: {price}, slippage: {slippage:.5f}) - Ticket: {result.order}"
                )

                return OrderResult(
                    success=True,
                    ticket=result.order,
                    order_id=result.deal,
                    volume=result.volume,
                    price=result.price,
                    bid=result.bid,
                    ask=result.ask,
                    comment=result.comment,
                    retcode=result.retcode,
                    slippage=slippage
                )

            except Exception as e:
                if attempt < self._max_retries:
                    logger.warning(f"Order exception (attempt {attempt + 1}): {e}, retrying...")
                    time.sleep(self._retry_delay)
                    continue
                return OrderResult(
                    success=False,
                    error_message=f"Order exception: {e}"
                )

        return OrderResult(
            success=False,
            error_message="Max retries exceeded"
        )

    def place_pending_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        price: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        stop_limit_price: float = 0.0,
        expiration: Optional[datetime] = None,
        magic: int = 0,
        comment: str = ""
    ) -> OrderResult:
        """
        Place a pending order (Limit, Stop, or Stop Limit).

        Args:
            symbol: Symbol to trade
            order_type: One of BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP,
                       BUY_STOP_LIMIT, SELL_STOP_LIMIT
            volume: Lot size
            price: Order price (trigger price for stop orders)
            stop_loss: Stop loss price
            take_profit: Take profit price
            stop_limit_price: Limit price for stop limit orders
            expiration: Order expiration time
            magic: Magic number
            comment: Order comment

        Returns:
            OrderResult with execution details
        """
        try:
            mt5_type = self.MT5_ORDER_TYPES.get(order_type)
            if mt5_type is None:
                return OrderResult(
                    success=False,
                    error_message=f"Invalid order type: {order_type}"
                )

            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": mt5_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "magic": magic,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC if not expiration else mt5.ORDER_TIME_SPECIFIED,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }

            if expiration:
                request["expiration"] = int(expiration.timestamp())

            if stop_limit_price > 0:
                request["stoplimit"] = stop_limit_price

            result = mt5.order_send(request)

            if result is None:
                error = mt5.last_error()
                return OrderResult(
                    success=False,
                    error_message=f"Pending order failed: {error}"
                )

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    success=False,
                    retcode=result.retcode,
                    error_message=f"Pending order failed: {result.comment}"
                )

            logger.info(f"Pending order placed: {order_type.value} {volume} {symbol} @ {price} - Order: {result.order}")

            return OrderResult(
                success=True,
                ticket=result.order,
                volume=volume,
                price=price,
                retcode=result.retcode
            )

        except Exception as e:
            return OrderResult(
                success=False,
                error_message=f"Pending order exception: {e}"
            )

    def close_position(self, ticket: int, deviation: int = 20) -> bool:
        """
        Close a position by ticket number.

        Args:
            ticket: Position ticket number
            deviation: Maximum slippage in points

        Returns:
            True if closed successfully
        """
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"Position not found: {ticket}")
                return False

            position = position[0]
            symbol = position.symbol
            volume = position.volume

            # Determine closing order type
            if position.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": deviation,
                "magic": position.magic,
                "comment": f"Close {ticket}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to close position {ticket}")
                return False

            logger.info(f"Position closed: {ticket} @ {result.price}")
            return True

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return False

    def partial_close(
        self,
        ticket: int,
        volume: Optional[float] = None,
        percent: Optional[float] = None,
        deviation: int = 20
    ) -> bool:
        """
        Partially close a position.

        Args:
            ticket: Position ticket number
            volume: Volume to close (mutually exclusive with percent)
            percent: Percentage to close (0-100)
            deviation: Maximum slippage in points

        Returns:
            True if partial close successful
        """
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"Position not found: {ticket}")
                return False

            position = position[0]
            symbol = position.symbol
            position_volume = position.volume

            # Determine close volume
            if volume is not None:
                close_volume = min(volume, position_volume)
            elif percent is not None:
                close_volume = position_volume * (percent / 100)
            else:
                logger.error("Must specify either volume or percent")
                return False

            # Round to lot step
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                close_volume = round(
                    close_volume / symbol_info.lot_step
                ) * symbol_info.lot_step
                close_volume = max(close_volume, symbol_info.min_lot)

            if close_volume >= position_volume:
                # Full close
                return self.close_position(ticket, deviation)

            # Partial close
            if position.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": deviation,
                "magic": position.magic,
                "comment": f"Partial close {ticket}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to partial close position {ticket}")
                return False

            logger.info(f"Partial close: {ticket} - {close_volume} lots @ {result.price}")
            return True

        except Exception as e:
            logger.error(f"Partial close error: {e}")
            return False

    def close_all_positions(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Close all open positions.

        Args:
            symbol: Only close positions for this symbol
            magic: Only close positions with this magic number

        Returns:
            Tuple of (closed_count, failed_count)
        """
        positions = self.get_positions(symbol, magic)
        closed = 0
        failed = 0

        for pos in positions:
            if self.close_position(pos.ticket):
                closed += 1
            else:
                failed += 1

        logger.info(f"Closed {closed} positions, {failed} failed")
        return closed, failed

    def modify_position(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify position stop loss and/or take profit.

        Args:
            ticket: Position ticket number
            stop_loss: New stop loss (None to keep current)
            take_profit: New take profit (None to keep current)

        Returns:
            True if modified successfully
        """
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"Position not found: {ticket}")
                return False

            position = position[0]

            new_sl = stop_loss if stop_loss is not None else position.sl
            new_tp = take_profit if take_profit is not None else position.tp

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": ticket,
                "sl": new_sl,
                "tp": new_tp,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to modify position {ticket}")
                return False

            logger.debug(f"Position modified: {ticket} SL={new_sl} TP={new_tp}")
            return True

        except Exception as e:
            logger.error(f"Modify position error: {e}")
            return False

    def set_breakeven(
        self,
        ticket: int,
        trigger_pips: float,
        offset_pips: float = 0.0
    ) -> bool:
        """
        Move stop loss to breakeven when position is in profit.

        Args:
            ticket: Position ticket number
            trigger_pips: Pips in profit to trigger breakeven
            offset_pips: Pips above/below entry for SL (0 = exact entry)

        Returns:
            True if breakeven was set
        """
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False

            position = position[0]
            symbol_info = self.get_symbol_info(position.symbol)
            if not symbol_info:
                return False

            tick = self.get_tick(position.symbol)
            if not tick:
                return False

            is_buy = position.type == mt5.ORDER_TYPE_BUY
            entry_price = position.price_open
            current_price = tick["bid"] if is_buy else tick["ask"]

            # Calculate profit in pips
            profit_pips = (current_price - entry_price) / (symbol_info.point * 10)
            if not is_buy:
                profit_pips = -profit_pips

            # Check if trigger reached
            if profit_pips < trigger_pips:
                return False

            # Already at breakeven or better
            if is_buy and position.sl >= entry_price:
                return False
            if not is_buy and position.sl <= entry_price and position.sl > 0:
                return False

            # Calculate breakeven SL
            offset_price = offset_pips * symbol_info.point * 10
            if is_buy:
                new_sl = entry_price + offset_price
            else:
                new_sl = entry_price - offset_price

            new_sl = round(new_sl, symbol_info.digits)

            return self.modify_position(ticket, stop_loss=new_sl)

        except Exception as e:
            logger.error(f"Breakeven error: {e}")
            return False

    def update_trailing_stop(
        self,
        ticket: int,
        trail_pips: float,
        activation_pips: Optional[float] = None
    ) -> bool:
        """
        Update trailing stop for a position.

        Args:
            ticket: Position ticket number
            trail_pips: Trail distance in pips
            activation_pips: Minimum profit in pips to activate trailing

        Returns:
            True if trailing stop was updated
        """
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False

            position = position[0]
            symbol_info = self.get_symbol_info(position.symbol)
            if not symbol_info:
                return False

            tick = self.get_tick(position.symbol)
            if not tick:
                return False

            is_buy = position.type == mt5.ORDER_TYPE_BUY
            entry_price = position.price_open
            current_price = tick["bid"] if is_buy else tick["ask"]
            current_sl = position.sl

            # Calculate values in price
            trail_distance = trail_pips * symbol_info.point * 10

            # Calculate profit in pips
            profit_pips = (current_price - entry_price) / (symbol_info.point * 10)
            if not is_buy:
                profit_pips = -profit_pips

            # Check activation
            if activation_pips and profit_pips < activation_pips:
                return False

            # Calculate new trailing stop
            if is_buy:
                new_sl = current_price - trail_distance
                # Only move SL up for buys
                if current_sl > 0 and new_sl <= current_sl:
                    return False
            else:
                new_sl = current_price + trail_distance
                # Only move SL down for sells
                if current_sl > 0 and new_sl >= current_sl:
                    return False

            new_sl = round(new_sl, symbol_info.digits)

            return self.modify_position(ticket, stop_loss=new_sl)

        except Exception as e:
            logger.error(f"Trailing stop error: {e}")
            return False

    def get_positions(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None
    ) -> List[Position]:
        """
        Get open positions.

        Args:
            symbol: Filter by symbol (optional)
            magic: Filter by magic number (optional)

        Returns:
            List of Position objects
        """
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()

            if positions is None:
                return []

            result = []
            for pos in positions:
                if magic is not None and pos.magic != magic:
                    continue

                result.append(Position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type=Signal.BUY if pos.type == mt5.ORDER_TYPE_BUY else Signal.SELL,
                    volume=pos.volume,
                    open_price=pos.price_open,
                    stop_loss=pos.sl,
                    take_profit=pos.tp,
                    profit=pos.profit,
                    magic_number=pos.magic,
                    comment=pos.comment,
                    open_time=datetime.fromtimestamp(pos.time),
                ))

            return result

        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    def get_pending_orders(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending orders.

        Args:
            symbol: Filter by symbol
            magic: Filter by magic number

        Returns:
            List of pending order dictionaries
        """
        try:
            if symbol:
                orders = mt5.orders_get(symbol=symbol)
            else:
                orders = mt5.orders_get()

            if orders is None:
                return []

            result = []
            for order in orders:
                if magic is not None and order.magic != magic:
                    continue

                result.append({
                    "ticket": order.ticket,
                    "symbol": order.symbol,
                    "type": order.type,
                    "volume": order.volume_current,
                    "price": order.price_open,
                    "sl": order.sl,
                    "tp": order.tp,
                    "time": datetime.fromtimestamp(order.time_setup),
                    "expiration": datetime.fromtimestamp(order.time_expiration)
                        if order.time_expiration else None,
                    "magic": order.magic,
                    "comment": order.comment,
                })

            return result

        except Exception as e:
            logger.error(f"Get pending orders error: {e}")
            return []

    def cancel_pending_order(self, ticket: int) -> bool:
        """
        Cancel a pending order.

        Args:
            ticket: Order ticket number

        Returns:
            True if cancelled successfully
        """
        try:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }

            result = mt5.order_send(request)

            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to cancel order {ticket}")
                return False

            logger.info(f"Pending order cancelled: {ticket}")
            return True

        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False

    def get_history(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            start_date: Start date for history
            end_date: End date (default: now)
            symbol: Filter by symbol (optional)

        Returns:
            List of closed trade dictionaries
        """
        if end_date is None:
            end_date = datetime.now()

        try:
            deals = mt5.history_deals_get(start_date, end_date)

            if deals is None:
                return []

            result = []
            for deal in deals:
                if symbol and deal.symbol != symbol:
                    continue

                result.append({
                    "ticket": deal.ticket,
                    "order": deal.order,
                    "time": datetime.fromtimestamp(deal.time),
                    "symbol": deal.symbol,
                    "type": "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL",
                    "volume": deal.volume,
                    "price": deal.price,
                    "profit": deal.profit,
                    "commission": deal.commission,
                    "swap": deal.swap,
                    "magic": deal.magic,
                    "comment": deal.comment,
                })

            return result

        except Exception as e:
            logger.error(f"Get history error: {e}")
            return []

    def _log_execution(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        requested_price: float,
        executed_price: float,
        slippage: float,
        ticket: int,
        success: bool,
        error: str = "",
        retries: int = 0
    ) -> None:
        """Log order execution details."""
        log_entry = ExecutionLog(
            timestamp=datetime.now(),
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            requested_price=requested_price,
            executed_price=executed_price,
            slippage=slippage,
            ticket=ticket,
            success=success,
            error=error,
            retries=retries
        )
        self._execution_log.append(log_entry)

        # Keep only last 1000 entries
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-1000:]

    def get_execution_log(self, limit: int = 100) -> List[ExecutionLog]:
        """
        Get recent execution log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of ExecutionLog entries
        """
        return self._execution_log[-limit:]

    def test_connection(self) -> bool:
        """
        Test MT5 connection.

        Returns:
            True if connection is working
        """
        try:
            if not self.connect():
                return False

            info = self.get_account_info()
            if info:
                print(f"Connected to: {info.server}")
                print(f"Account: {info.login}")
                print(f"Balance: {info.balance} {info.currency}")
                print(f"Leverage: 1:{info.leverage}")
                return True
            return False
        finally:
            self.disconnect()
