"""
Mock MetaTrader5 module for development on non-Windows platforms.

This module provides a simulation of the MT5 Python API so the bot can run
for UI development and strategy testing without an actual MT5 connection.
"""
import random
import time as time_module  # Renamed to avoid conflict with dataclass field names
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict
import numpy as np
import pandas as pd


def _current_time() -> int:
    return int(time_module.time())


def _current_time_msc() -> int:
    return int(time_module.time() * 1000)

# ============================================================================
# MT5 Constants (matching real MT5 API)
# ============================================================================

# Timeframes
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 60
TIMEFRAME_H4 = 240
TIMEFRAME_D1 = 1440
TIMEFRAME_W1 = 10080
TIMEFRAME_MN1 = 43200

# Order types
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5

# Trade actions
TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_SLTP = 6
TRADE_ACTION_MODIFY = 7
TRADE_ACTION_REMOVE = 8
TRADE_ACTION_CLOSE_BY = 10

# Order time
ORDER_TIME_GTC = 0
ORDER_TIME_DAY = 1
ORDER_TIME_SPECIFIED = 2
ORDER_TIME_SPECIFIED_DAY = 3

# Order filling
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

# Trade return codes
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_REQUOTE = 10004
TRADE_RETCODE_REJECT = 10006
TRADE_RETCODE_ERROR = 10011

# Deal types
DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1

# Trade modes
SYMBOL_TRADE_MODE_DISABLED = 0
SYMBOL_TRADE_MODE_LONGONLY = 1
SYMBOL_TRADE_MODE_SHORTONLY = 2
SYMBOL_TRADE_MODE_CLOSEONLY = 3
SYMBOL_TRADE_MODE_FULL = 4


# ============================================================================
# Mock Data Classes
# ============================================================================

@dataclass
class MockAccountInfo:
    login: int = 12345678
    trade_mode: int = 0
    leverage: int = 100
    limit_orders: int = 200
    margin_so_mode: int = 0
    trade_allowed: bool = True
    trade_expert: bool = True
    margin_mode: int = 0
    currency_digits: int = 2
    fifo_close: bool = False
    balance: float = 10000.0
    credit: float = 0.0
    profit: float = 0.0
    equity: float = 10000.0
    margin: float = 0.0
    margin_free: float = 10000.0
    margin_level: float = 0.0
    margin_so_call: float = 50.0
    margin_so_so: float = 30.0
    margin_initial: float = 0.0
    margin_maintenance: float = 0.0
    assets: float = 0.0
    liabilities: float = 0.0
    commission_blocked: float = 0.0
    name: str = "Demo Account"
    server: str = "MockBroker-Demo"
    currency: str = "USD"
    company: str = "Mock Broker"


@dataclass
class MockSymbolInfo:
    name: str = "XAUUSD"
    description: str = "Gold vs US Dollar"
    path: str = "Metals\\XAUUSD"
    point: float = 0.01
    digits: int = 2
    spread: int = 25
    spread_float: bool = True
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    trade_tick_size: float = 0.01
    trade_tick_value: float = 1.0
    trade_contract_size: float = 100.0
    trade_mode: int = SYMBOL_TRADE_MODE_FULL
    visible: bool = True
    time: int = field(default_factory=_current_time)
    bid: float = 1950.00
    ask: float = 1950.25
    last: float = 1950.12
    volume: int = 0


@dataclass
class MockTick:
    time: int = field(default_factory=_current_time)
    bid: float = 1950.00
    ask: float = 1950.25
    last: float = 1950.12
    volume: int = 100
    time_msc: int = field(default_factory=_current_time_msc)
    flags: int = 0
    volume_real: float = 100.0


@dataclass
class MockPosition:
    ticket: int = 0
    time: int = field(default_factory=_current_time)
    time_msc: int = field(default_factory=_current_time_msc)
    time_update: int = field(default_factory=_current_time)
    time_update_msc: int = field(default_factory=_current_time_msc)
    type: int = ORDER_TYPE_BUY
    magic: int = 0
    identifier: int = 0
    reason: int = 0
    volume: float = 0.01
    price_open: float = 1950.00
    sl: float = 1940.00
    tp: float = 1960.00
    price_current: float = 1950.25
    swap: float = 0.0
    profit: float = 25.0
    symbol: str = "XAUUSD"
    comment: str = ""
    external_id: str = ""


@dataclass
class MockDeal:
    ticket: int = 0
    order: int = 0
    time: int = field(default_factory=_current_time)
    time_msc: int = field(default_factory=_current_time_msc)
    type: int = DEAL_TYPE_BUY
    entry: int = 0
    magic: int = 0
    position_id: int = 0
    reason: int = 0
    volume: float = 0.01
    price: float = 1950.00
    commission: float = -2.50
    swap: float = 0.0
    profit: float = 0.0
    fee: float = 0.0
    symbol: str = "XAUUSD"
    comment: str = ""
    external_id: str = ""


@dataclass
class MockOrderResult:
    retcode: int = TRADE_RETCODE_DONE
    deal: int = 0
    order: int = 0
    volume: float = 0.01
    price: float = 1950.00
    bid: float = 1950.00
    ask: float = 1950.25
    comment: str = "Request executed"
    request_id: int = 0


@dataclass
class MockTerminalInfo:
    community_account: bool = False
    community_connection: bool = False
    connected: bool = True
    dlls_allowed: bool = True
    trade_allowed: bool = True
    tradeapi_disabled: bool = False
    email_enabled: bool = False
    ftp_enabled: bool = False
    notifications_enabled: bool = False
    mqid: bool = False
    build: int = 3480
    maxbars: int = 100000
    codepage: int = 0
    ping_last: int = 30
    community_balance: float = 0.0
    retransmission: float = 0.0
    company: str = "Mock MT5"
    name: str = "MockTerminal"
    language: str = "English"
    path: str = "/mock/path"
    data_path: str = "/mock/data"
    commondata_path: str = "/mock/common"


# ============================================================================
# Mock State (simulates MT5 state)
# ============================================================================

class MockState:
    """Holds the simulated MT5 state."""

    def __init__(self):
        self.initialized = False
        self.connected = False
        self.account = MockAccountInfo()
        self.positions: Dict[int, MockPosition] = {}
        self.deals: List[MockDeal] = []
        self.next_ticket = 1000
        self._last_error = (0, "")

        # Symbol prices (simulated)
        self._prices = {
            "XAUUSD": {"bid": 1950.00, "ask": 1950.25, "point": 0.01, "digits": 2},
            "EURUSD": {"bid": 1.0850, "ask": 1.0852, "point": 0.00001, "digits": 5},
            "GBPUSD": {"bid": 1.2650, "ask": 1.2653, "point": 0.00001, "digits": 5},
            "USDJPY": {"bid": 149.50, "ask": 149.53, "point": 0.001, "digits": 3},
        }

    def get_symbol_price(self, symbol: str) -> Dict[str, float]:
        """Get simulated price with small random movement."""
        if symbol not in self._prices:
            self._prices[symbol] = {"bid": 100.00, "ask": 100.05, "point": 0.01, "digits": 2}

        base = self._prices[symbol].copy()
        # Add small random movement
        movement = random.uniform(-0.0005, 0.0005) * base["bid"]
        base["bid"] += movement
        base["ask"] = base["bid"] + (base["ask"] - base["bid"])
        return base

    def generate_ohlcv(self, symbol: str, timeframe: int, count: int,
                       start_time: Optional[datetime] = None) -> np.ndarray:
        """Generate synthetic OHLCV data."""
        if start_time is None:
            start_time = datetime.now() - timedelta(minutes=count * timeframe)

        price_info = self.get_symbol_price(symbol)
        base_price = price_info["bid"]

        # Generate synthetic price data
        dtype = [
            ('time', 'i8'), ('open', 'f8'), ('high', 'f8'),
            ('low', 'f8'), ('close', 'f8'), ('tick_volume', 'i8'),
            ('spread', 'i4'), ('real_volume', 'i8')
        ]
        rates = np.zeros(count, dtype=dtype)

        current_price = base_price
        for i in range(count):
            bar_time = start_time + timedelta(minutes=i * timeframe)

            # Random walk
            change = random.uniform(-0.002, 0.002) * current_price
            open_price = current_price
            close_price = current_price + change
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.001))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.001))

            rates[i] = (
                int(bar_time.timestamp()),
                round(open_price, price_info["digits"]),
                round(high_price, price_info["digits"]),
                round(low_price, price_info["digits"]),
                round(close_price, price_info["digits"]),
                random.randint(100, 10000),
                25,
                0
            )
            current_price = close_price

        return rates


# Global mock state
_state = MockState()


# ============================================================================
# Mock MT5 Functions
# ============================================================================

def initialize(path: str = None, login: int = None, password: str = None,
               server: str = None, timeout: int = 60000, portable: bool = False) -> bool:
    """Initialize connection to MT5 terminal."""
    _state.initialized = True
    _state.connected = True
    _state._last_error = (0, "")
    return True


def shutdown() -> None:
    """Shut down connection to MT5 terminal."""
    _state.initialized = False
    _state.connected = False


def login(login: int, password: str = "", server: str = "", timeout: int = 60000) -> bool:
    """Login to MT5 account."""
    if not _state.initialized:
        _state._last_error = (1, "MT5 not initialized")
        return False

    _state.account.login = login
    _state.account.server = server if server else "MockBroker-Demo"
    _state.connected = True
    return True


def last_error() -> tuple:
    """Get last error code and description."""
    return _state._last_error


def terminal_info() -> Optional[MockTerminalInfo]:
    """Get terminal info."""
    if not _state.initialized:
        return None
    return MockTerminalInfo()


def account_info() -> Optional[MockAccountInfo]:
    """Get account info."""
    if not _state.connected:
        return None

    # Update profit from open positions
    total_profit = sum(pos.profit for pos in _state.positions.values())
    _state.account.profit = total_profit
    _state.account.equity = _state.account.balance + total_profit

    return _state.account


def symbol_info(symbol: str) -> Optional[MockSymbolInfo]:
    """Get symbol info."""
    if not _state.connected:
        return None

    prices = _state.get_symbol_price(symbol)
    return MockSymbolInfo(
        name=symbol,
        description=f"Mock {symbol}",
        point=prices["point"],
        digits=prices["digits"],
        spread=int((prices["ask"] - prices["bid"]) / prices["point"]),
        bid=prices["bid"],
        ask=prices["ask"]
    )


def symbol_info_tick(symbol: str) -> Optional[MockTick]:
    """Get current tick for symbol."""
    if not _state.connected:
        return None

    prices = _state.get_symbol_price(symbol)
    return MockTick(
        time=int(time_module.time()),
        bid=prices["bid"],
        ask=prices["ask"],
        last=prices["bid"],
        volume=random.randint(10, 1000)
    )


def symbol_select(symbol: str, enable: bool = True) -> bool:
    """Select/enable symbol in Market Watch."""
    return True


def copy_rates_from(symbol: str, timeframe: int, date_from: datetime, count: int) -> Optional[np.ndarray]:
    """Copy rates starting from specified date."""
    if not _state.connected:
        return None
    return _state.generate_ohlcv(symbol, timeframe, count, date_from)


def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int) -> Optional[np.ndarray]:
    """Copy rates from specified position."""
    if not _state.connected:
        return None
    return _state.generate_ohlcv(symbol, timeframe, count)


def copy_rates_range(symbol: str, timeframe: int, date_from: datetime, date_to: datetime) -> Optional[np.ndarray]:
    """Copy rates within time range."""
    if not _state.connected:
        return None

    delta = date_to - date_from
    count = int(delta.total_seconds() / (timeframe * 60)) + 1
    return _state.generate_ohlcv(symbol, timeframe, count, date_from)


def order_send(request: dict) -> Optional[MockOrderResult]:
    """Send trading order."""
    if not _state.connected:
        _state._last_error = (1, "Not connected")
        return None

    action = request.get("action")
    symbol = request.get("symbol", "")
    volume = request.get("volume", 0.01)
    order_type = request.get("type", ORDER_TYPE_BUY)
    price = request.get("price", 0)
    sl = request.get("sl", 0)
    tp = request.get("tp", 0)
    magic = request.get("magic", 0)
    comment = request.get("comment", "")
    position_ticket = request.get("position", 0)

    if action == TRADE_ACTION_DEAL:
        # Market order or close position
        if position_ticket:
            # Closing position
            if position_ticket in _state.positions:
                pos = _state.positions[position_ticket]
                # Create closing deal
                deal = MockDeal(
                    ticket=_state.next_ticket,
                    order=_state.next_ticket,
                    time=int(time_module.time()),
                    type=DEAL_TYPE_SELL if pos.type == ORDER_TYPE_BUY else DEAL_TYPE_BUY,
                    volume=pos.volume,
                    price=price,
                    profit=pos.profit,
                    symbol=pos.symbol,
                    magic=pos.magic,
                    comment=comment
                )
                _state.deals.append(deal)
                del _state.positions[position_ticket]
                _state.next_ticket += 1
        else:
            # Opening new position
            ticket = _state.next_ticket
            _state.next_ticket += 1

            _state.positions[ticket] = MockPosition(
                ticket=ticket,
                time=int(time_module.time()),
                type=order_type,
                magic=magic,
                volume=volume,
                price_open=price,
                sl=sl,
                tp=tp,
                price_current=price,
                symbol=symbol,
                comment=comment,
                profit=0.0
            )

            return MockOrderResult(
                retcode=TRADE_RETCODE_DONE,
                order=ticket,
                deal=ticket,
                volume=volume,
                price=price
            )

    elif action == TRADE_ACTION_SLTP:
        # Modify SL/TP
        ticket = request.get("position", 0)
        if ticket in _state.positions:
            _state.positions[ticket].sl = request.get("sl", _state.positions[ticket].sl)
            _state.positions[ticket].tp = request.get("tp", _state.positions[ticket].tp)

    return MockOrderResult(retcode=TRADE_RETCODE_DONE)


def positions_get(symbol: str = None, ticket: int = None) -> Optional[tuple]:
    """Get open positions."""
    if not _state.connected:
        return None

    positions = list(_state.positions.values())

    if ticket:
        positions = [p for p in positions if p.ticket == ticket]
    if symbol:
        positions = [p for p in positions if p.symbol == symbol]

    # Update current prices and profit
    for pos in positions:
        prices = _state.get_symbol_price(pos.symbol)
        pos.price_current = prices["bid"] if pos.type == ORDER_TYPE_BUY else prices["ask"]

        # Calculate profit (simplified)
        if pos.type == ORDER_TYPE_BUY:
            pos.profit = (pos.price_current - pos.price_open) * pos.volume * 100
        else:
            pos.profit = (pos.price_open - pos.price_current) * pos.volume * 100

    return tuple(positions) if positions else None


def history_deals_get(date_from: datetime, date_to: datetime) -> Optional[tuple]:
    """Get deal history."""
    if not _state.connected:
        return None

    deals = [d for d in _state.deals
             if date_from.timestamp() <= d.time <= date_to.timestamp()]

    return tuple(deals) if deals else None


# ============================================================================
# Version info
# ============================================================================

def version() -> tuple:
    """Return MT5 version info."""
    return (5, 0, 45)


__version__ = "5.0.45.mock"
__name__ = "MetaTrader5 (Mock)"
