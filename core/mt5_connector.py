"""
MetaTrader 5 Connection and API Wrapper.
Handles all communication with the MT5 terminal.
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from loguru import logger

from .strategy_base import Signal, Position


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


class MT5Connector:
    """
    MetaTrader 5 API Wrapper.

    Provides methods for:
    - Connection management
    - Account information
    - Market data retrieval
    - Order placement and management
    - Position tracking
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

    def __init__(self):
        """Initialize MT5 connector."""
        self._connected = False
        self._account_info: Optional[AccountInfo] = None

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

    def disconnect(self) -> None:
        """Disconnect from MT5 terminal."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("Disconnected from MT5")

    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        if not self._connected:
            return False
        # Verify connection is still alive
        info = mt5.terminal_info()
        return info is not None

    def _update_account_info(self) -> None:
        """Update cached account information."""
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
            )

    def get_account_info(self) -> Optional[AccountInfo]:
        """Get current account information."""
        self._update_account_info()
        return self._account_info

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        Get symbol information.

        Args:
            symbol: Symbol name (e.g., "XAUUSD")

        Returns:
            SymbolInfo object or None if symbol not found
        """
        info = mt5.symbol_info(symbol)
        if not info:
            logger.warning(f"Symbol not found: {symbol}")
            return None

        return SymbolInfo(
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
        )

    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current tick for symbol.

        Args:
            symbol: Symbol name

        Returns:
            Dict with bid, ask, last, time
        """
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
            "time": datetime.fromtimestamp(tick.time),
        }

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

        rates = mt5.copy_rates_range(symbol, tf, start_date, end_date)

        if rates is None or len(rates) == 0:
            logger.warning(f"No historical data for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})

        return df[["time", "open", "high", "low", "close", "volume"]]

    def place_market_order(
        self,
        symbol: str,
        order_type: Signal,
        volume: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        magic: int = 0,
        comment: str = ""
    ) -> Tuple[bool, int]:
        """
        Place a market order.

        Args:
            symbol: Symbol to trade
            order_type: Signal.BUY or Signal.SELL
            volume: Lot size
            stop_loss: Stop loss price (0 to disable)
            take_profit: Take profit price (0 to disable)
            magic: Magic number for EA identification
            comment: Order comment

        Returns:
            Tuple of (success, ticket_number)
        """
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"Cannot get tick for {symbol}")
            return False, 0

        if order_type == Signal.BUY:
            price = tick.ask
            mt5_type = mt5.ORDER_TYPE_BUY
        elif order_type == Signal.SELL:
            price = tick.bid
            mt5_type = mt5.ORDER_TYPE_SELL
        else:
            logger.error("Invalid order type")
            return False, 0

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            logger.error(f"Order failed: {error}")
            return False, 0

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.comment} (code: {result.retcode})")
            return False, 0

        logger.info(f"Order placed: {order_type.name} {volume} {symbol} @ {price} - Ticket: {result.order}")
        return True, result.order

    def close_position(self, ticket: int) -> bool:
        """
        Close a position by ticket number.

        Args:
            ticket: Position ticket number

        Returns:
            True if closed successfully
        """
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
            "magic": position.magic,
            "comment": f"Close {ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to close position {ticket}")
            return False

        logger.info(f"Position closed: {ticket}")
        return True

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
        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.warning(f"Position not found: {ticket}")
            return False

        position = position[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": ticket,
            "sl": stop_loss if stop_loss is not None else position.sl,
            "tp": take_profit if take_profit is not None else position.tp,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to modify position {ticket}")
            return False

        logger.debug(f"Position modified: {ticket} SL={stop_loss} TP={take_profit}")
        return True

    def get_positions(self, symbol: Optional[str] = None, magic: Optional[int] = None) -> List[Position]:
        """
        Get open positions.

        Args:
            symbol: Filter by symbol (optional)
            magic: Filter by magic number (optional)

        Returns:
            List of Position objects
        """
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
