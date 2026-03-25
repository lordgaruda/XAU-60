"""
Professional Trading Dashboard - Real-time trading overview.

Features:
- Live candlestick chart with EMA overlays
- Manual trade panel (Buy/Sell)
- Open positions table with real-time P&L
- Account summary bar
- Trade history table
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sys
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import core modules
try:
    from core.account_manager import (
        get_account_manager, AccountManager, ConnectionStatus, AccountInfo
    )
    from core.mt5_connector import MT5Connector, Signal, OrderResult
    from core.strategy_base import Position
except ImportError as e:
    st.error(f"Import error: {e}")


# Session state keys
STATE_KEYS = {
    "selected_symbol": "XAUUSD",
    "selected_timeframe": "M15",
    "chart_bars": 200,
    "auto_refresh": False,
    "refresh_interval": 5,
    "last_refresh": None,
    "trade_result": None,
    "show_trade_modal": False,
}


def init_session_state():
    """Initialize session state with default values."""
    for key, default in STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_connector() -> Optional[MT5Connector]:
    """Get the active MT5 connector."""
    try:
        manager = get_account_manager()
        return manager.get_connector()
    except Exception:
        return None


def render_dashboard():
    """Render the professional trading dashboard."""
    init_session_state()

    # Page header
    st.markdown("""
    <div class="page-header">
        <h1>Trading Dashboard</h1>
        <p>Real-time trading and account monitoring</p>
    </div>
    """, unsafe_allow_html=True)

    # Account Summary Bar
    render_account_summary()

    st.markdown("---")

    # Main layout: Chart + Trade Panel
    col_chart, col_trade = st.columns([3, 1])

    with col_chart:
        render_chart_panel()

    with col_trade:
        render_trade_panel()

    st.markdown("---")

    # Bottom: Positions and History
    tab_positions, tab_history, tab_pending = st.tabs([
        "Open Positions", "Trade History", "Pending Orders"
    ])

    with tab_positions:
        render_positions_table()

    with tab_history:
        render_trade_history()

    with tab_pending:
        render_pending_orders()

    # Auto-refresh logic
    if st.session_state.get("auto_refresh", False):
        time.sleep(st.session_state.get("refresh_interval", 5))
        st.rerun()


def render_account_summary():
    """Render the account summary bar."""
    manager = get_account_manager()
    connector = manager.get_connector()

    # Get account info
    account_info = None
    connection_status = manager.get_connection_status()

    if connector and connector.is_connected():
        try:
            account_info = connector.get_account_info()
        except Exception:
            pass

    # Connection status indicator
    status_col, account_col = st.columns([1, 5])

    with status_col:
        if connection_status == ConnectionStatus.CONNECTED:
            st.markdown("**Status:** <span style='color: #10b981;'>● Connected</span>", unsafe_allow_html=True)
        elif connection_status == ConnectionStatus.CONNECTING:
            st.markdown("**Status:** <span style='color: #f59e0b;'>○ Connecting...</span>", unsafe_allow_html=True)
        elif connection_status == ConnectionStatus.RECONNECTING:
            st.markdown("**Status:** <span style='color: #f59e0b;'>○ Reconnecting...</span>", unsafe_allow_html=True)
        else:
            st.markdown("**Status:** <span style='color: #ef4444;'>● Disconnected</span>", unsafe_allow_html=True)

    with account_col:
        active_account = manager.get_active_account()
        if active_account:
            st.markdown(f"**Account:** {active_account.name} ({active_account.login}@{active_account.server})")

    # Metrics row
    if account_info:
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric(
                "Balance",
                f"{account_info.balance:,.2f} {account_info.currency}"
            )

        with col2:
            delta = account_info.profit
            st.metric(
                "Equity",
                f"{account_info.equity:,.2f}",
                f"{delta:+,.2f}" if delta != 0 else None
            )

        with col3:
            st.metric(
                "Margin",
                f"{account_info.margin:,.2f}"
            )

        with col4:
            st.metric(
                "Free Margin",
                f"{account_info.free_margin:,.2f}"
            )

        with col5:
            st.metric(
                "Open P&L",
                f"{account_info.profit:+,.2f}",
                delta_color="normal" if account_info.profit >= 0 else "inverse"
            )

        with col6:
            margin_level = account_info.margin_level
            st.metric(
                "Margin Level",
                f"{margin_level:,.0f}%" if margin_level > 0 else "N/A"
            )

        # Daily P&L calculation - get from today's history
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if connector:
            try:
                history = connector.get_history(start_date=today)
                daily_pnl = sum(h.get("profit", 0) for h in history if h.get("profit"))
                wins = sum(1 for h in history if h.get("profit", 0) > 0)
                total = len([h for h in history if h.get("profit", 0) != 0])
                win_rate = (wins / total * 100) if total > 0 else 0

                col_daily, col_winrate, col_refresh = st.columns([1, 1, 2])
                with col_daily:
                    st.markdown(f"**Daily P&L:** <span style='color: {'#10b981' if daily_pnl >= 0 else '#ef4444'};'>{daily_pnl:+,.2f}</span>", unsafe_allow_html=True)
                with col_winrate:
                    st.markdown(f"**Win Rate Today:** {win_rate:.1f}% ({wins}/{total})")
            except Exception:
                pass
    else:
        # Mock data for disconnected state
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Balance", "-- --")
        with col2:
            st.metric("Equity", "-- --")
        with col3:
            st.metric("Margin", "-- --")
        with col4:
            st.metric("Free Margin", "-- --")
        with col5:
            st.metric("Open P&L", "-- --")
        with col6:
            st.metric("Margin Level", "-- --")


def render_chart_panel():
    """Render the live candlestick chart panel."""
    st.markdown("### Live Chart")

    # Chart controls
    col_symbol, col_tf, col_bars, col_refresh = st.columns([2, 1, 1, 2])

    with col_symbol:
        symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US500", "US30"]
        st.session_state["selected_symbol"] = st.selectbox(
            "Symbol",
            symbols,
            index=symbols.index(st.session_state.get("selected_symbol", "XAUUSD")),
            key="chart_symbol_select"
        )

    with col_tf:
        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        st.session_state["selected_timeframe"] = st.selectbox(
            "Timeframe",
            timeframes,
            index=timeframes.index(st.session_state.get("selected_timeframe", "M15")),
            key="chart_tf_select"
        )

    with col_bars:
        st.session_state["chart_bars"] = st.number_input(
            "Bars",
            min_value=50,
            max_value=500,
            value=st.session_state.get("chart_bars", 200),
            step=50,
            key="chart_bars_input"
        )

    with col_refresh:
        col_auto, col_btn = st.columns(2)
        with col_auto:
            st.session_state["auto_refresh"] = st.toggle(
                "Auto-refresh",
                value=st.session_state.get("auto_refresh", False),
                key="chart_auto_refresh"
            )
        with col_btn:
            if st.button("🔄 Refresh", use_container_width=True, key="chart_refresh_btn"):
                st.rerun()

    # Get chart data
    connector = get_connector()
    symbol = st.session_state["selected_symbol"]
    timeframe = st.session_state["selected_timeframe"]
    bars = st.session_state["chart_bars"]

    df = None
    if connector and connector.is_connected():
        try:
            df = connector.get_ohlcv(symbol, timeframe, count=bars)
        except Exception as e:
            st.warning(f"Failed to get chart data: {e}")

    if df is None or df.empty:
        # Generate mock data for demonstration
        df = generate_mock_ohlcv(symbol, bars)

    # Create candlestick chart
    fig = create_candlestick_chart(df, symbol, timeframe, connector)
    st.plotly_chart(fig, use_container_width=True, key="main_chart")

    # Current price display
    if connector and connector.is_connected():
        tick = connector.get_tick(symbol)
        if tick:
            col_bid, col_ask, col_spread = st.columns(3)
            with col_bid:
                st.markdown(f"**Bid:** {tick['bid']:.5f}")
            with col_ask:
                st.markdown(f"**Ask:** {tick['ask']:.5f}")
            with col_spread:
                st.markdown(f"**Spread:** {tick.get('spread', 0):.1f} points")


def create_candlestick_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    connector: Optional[MT5Connector] = None
) -> go.Figure:
    """Create a professional candlestick chart with EMAs and position markers."""

    # Calculate EMAs
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Create figure with secondary y-axis for volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
        subplot_titles=(f"{symbol} - {timeframe}", "Volume")
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df['time'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price',
            increasing_line_color='#10b981',
            decreasing_line_color='#ef4444',
            increasing_fillcolor='#10b981',
            decreasing_fillcolor='#ef4444',
        ),
        row=1, col=1
    )

    # EMAs
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['ema_20'],
            name='EMA 20',
            line=dict(color='#3b82f6', width=1),
            opacity=0.8
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['ema_50'],
            name='EMA 50',
            line=dict(color='#f59e0b', width=1),
            opacity=0.8
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['ema_200'],
            name='EMA 200',
            line=dict(color='#8b5cf6', width=1),
            opacity=0.8
        ),
        row=1, col=1
    )

    # Volume bars
    colors = ['#10b981' if c >= o else '#ef4444'
              for c, o in zip(df['close'], df['open'])]
    fig.add_trace(
        go.Bar(
            x=df['time'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.5
        ),
        row=2, col=1
    )

    # Add position markers if connected
    if connector and connector.is_connected():
        try:
            positions = connector.get_positions(symbol=symbol)
            for pos in positions:
                # Entry line
                fig.add_hline(
                    y=pos.open_price,
                    line_dash="dash",
                    line_color="#3b82f6",
                    annotation_text=f"Entry {pos.ticket}",
                    row=1, col=1
                )

                # SL line
                if pos.stop_loss > 0:
                    fig.add_hline(
                        y=pos.stop_loss,
                        line_dash="dot",
                        line_color="#ef4444",
                        annotation_text="SL",
                        row=1, col=1
                    )

                # TP line
                if pos.take_profit > 0:
                    fig.add_hline(
                        y=pos.take_profit,
                        line_dash="dot",
                        line_color="#10b981",
                        annotation_text="TP",
                        row=1, col=1
                    )

                # Entry arrow
                fig.add_annotation(
                    x=pos.open_time,
                    y=pos.open_price,
                    text="▲" if pos.type == Signal.BUY else "▼",
                    showarrow=False,
                    font=dict(
                        size=16,
                        color="#10b981" if pos.type == Signal.BUY else "#ef4444"
                    ),
                    row=1, col=1
                )
        except Exception:
            pass

    # Update layout
    fig.update_layout(
        height=500,
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor='rgba(15, 23, 42, 0.8)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#94a3b8'),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    fig.update_xaxes(
        gridcolor='rgba(51, 65, 85, 0.5)',
        showgrid=True
    )

    fig.update_yaxes(
        gridcolor='rgba(51, 65, 85, 0.5)',
        showgrid=True
    )

    return fig


def generate_mock_ohlcv(symbol: str, bars: int) -> pd.DataFrame:
    """Generate mock OHLCV data for demonstration."""
    base_prices = {
        "XAUUSD": 2000.0,
        "EURUSD": 1.0850,
        "GBPUSD": 1.2650,
        "USDJPY": 150.0,
        "BTCUSD": 45000.0,
        "US500": 5000.0,
        "US30": 38000.0,
    }

    base = base_prices.get(symbol, 1000.0)
    dates = pd.date_range(end=datetime.now(), periods=bars, freq='15min')

    np.random.seed(42)
    returns = np.random.normal(0, 0.001, bars)
    prices = base * (1 + np.cumsum(returns))

    data = []
    for i, (date, price) in enumerate(zip(dates, prices)):
        volatility = np.random.uniform(0.001, 0.003)
        open_price = price
        close_price = price * (1 + np.random.normal(0, volatility))
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.002))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.002))

        data.append({
            'time': date,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.randint(100, 10000)
        })

    return pd.DataFrame(data)


def render_trade_panel():
    """Render the manual trade panel."""
    st.markdown("### Quick Trade")

    connector = get_connector()
    symbol = st.session_state.get("selected_symbol", "XAUUSD")

    # Current price
    if connector and connector.is_connected():
        tick = connector.get_tick(symbol)
        if tick:
            col_bid, col_ask = st.columns(2)
            with col_bid:
                st.markdown(f"<h3 style='color: #ef4444; margin: 0;'>{tick['bid']:.5f}</h3>", unsafe_allow_html=True)
                st.caption("BID")
            with col_ask:
                st.markdown(f"<h3 style='color: #10b981; margin: 0;'>{tick['ask']:.5f}</h3>", unsafe_allow_html=True)
                st.caption("ASK")

    st.markdown("---")

    # Trade inputs
    lot_size = st.number_input(
        "Lot Size",
        min_value=0.01,
        max_value=100.0,
        value=0.01,
        step=0.01,
        format="%.2f",
        key="trade_lot_size"
    )

    order_type = st.selectbox(
        "Order Type",
        ["Market", "Limit", "Stop"],
        key="trade_order_type"
    )

    if order_type != "Market":
        entry_price = st.number_input(
            "Entry Price",
            value=0.0,
            format="%.5f",
            key="trade_entry_price"
        )

    sl_type = st.selectbox(
        "SL Type",
        ["Price", "Pips", "Off"],
        key="trade_sl_type"
    )

    if sl_type != "Off":
        sl_value = st.number_input(
            "Stop Loss" + (" (pips)" if sl_type == "Pips" else ""),
            value=0.0,
            format="%.2f" if sl_type == "Pips" else "%.5f",
            key="trade_sl_value"
        )
    else:
        sl_value = 0.0

    tp_type = st.selectbox(
        "TP Type",
        ["Price", "Pips", "R:R", "Off"],
        key="trade_tp_type"
    )

    if tp_type != "Off":
        tp_value = st.number_input(
            "Take Profit" + (" (pips)" if tp_type == "Pips" else " (ratio)" if tp_type == "R:R" else ""),
            value=2.0 if tp_type == "R:R" else 0.0,
            format="%.2f" if tp_type in ["Pips", "R:R"] else "%.5f",
            key="trade_tp_value"
        )
    else:
        tp_value = 0.0

    comment = st.text_input("Comment", value="Manual Trade", key="trade_comment")

    st.markdown("---")

    # Buy/Sell buttons
    col_buy, col_sell = st.columns(2)

    with col_buy:
        buy_clicked = st.button(
            "🟢 BUY",
            type="primary",
            use_container_width=True,
            key="trade_buy_btn"
        )

    with col_sell:
        sell_clicked = st.button(
            "🔴 SELL",
            type="secondary",
            use_container_width=True,
            key="trade_sell_btn"
        )

    # Execute trade
    if buy_clicked or sell_clicked:
        execute_trade(
            symbol=symbol,
            order_type_str=order_type,
            signal=Signal.BUY if buy_clicked else Signal.SELL,
            lot_size=lot_size,
            sl_type=sl_type,
            sl_value=sl_value,
            tp_type=tp_type,
            tp_value=tp_value,
            comment=comment,
            entry_price=entry_price if order_type != "Market" else None
        )

    st.markdown("---")

    # Close All button
    if st.button("❌ Close All Positions", type="secondary", use_container_width=True, key="close_all_btn"):
        close_all_positions()

    # Trade result display
    if st.session_state.get("trade_result"):
        result = st.session_state["trade_result"]
        if result.get("success"):
            st.success(f"✅ Order executed! Ticket: {result.get('ticket', 'N/A')}")
        else:
            st.error(f"❌ Order failed: {result.get('error', 'Unknown error')}")
        # Clear after display
        st.session_state["trade_result"] = None


def execute_trade(
    symbol: str,
    order_type_str: str,
    signal: Signal,
    lot_size: float,
    sl_type: str,
    sl_value: float,
    tp_type: str,
    tp_value: float,
    comment: str,
    entry_price: Optional[float] = None
):
    """Execute a trade order."""
    connector = get_connector()

    if not connector or not connector.is_connected():
        st.session_state["trade_result"] = {
            "success": False,
            "error": "Not connected to MT5"
        }
        return

    try:
        # Get current price
        tick = connector.get_tick(symbol)
        if not tick:
            st.session_state["trade_result"] = {
                "success": False,
                "error": "Cannot get current price"
            }
            return

        price = tick["ask"] if signal == Signal.BUY else tick["bid"]

        # Calculate SL/TP
        from core.mt5_connector import SLTPType

        sl_price = 0.0
        tp_price = 0.0

        if sl_type == "Price" and sl_value > 0:
            sl_price = sl_value
        elif sl_type == "Pips" and sl_value > 0:
            symbol_info = connector.get_symbol_info(symbol)
            if symbol_info:
                sl_distance = sl_value * symbol_info.point * 10
                sl_price = price - sl_distance if signal == Signal.BUY else price + sl_distance

        if tp_type == "Price" and tp_value > 0:
            tp_price = tp_value
        elif tp_type == "Pips" and tp_value > 0:
            symbol_info = connector.get_symbol_info(symbol)
            if symbol_info:
                tp_distance = tp_value * symbol_info.point * 10
                tp_price = price + tp_distance if signal == Signal.BUY else price - tp_distance
        elif tp_type == "R:R" and sl_price > 0 and tp_value > 0:
            sl_distance = abs(price - sl_price)
            tp_distance = sl_distance * tp_value
            tp_price = price + tp_distance if signal == Signal.BUY else price - tp_distance

        # Execute order
        if order_type_str == "Market":
            result = connector.place_market_order(
                symbol=symbol,
                order_type=signal,
                volume=lot_size,
                stop_loss=sl_price,
                take_profit=tp_price,
                comment=comment
            )

            st.session_state["trade_result"] = {
                "success": result.success,
                "ticket": result.ticket,
                "error": result.error_message
            }
        else:
            # Pending orders
            from core.mt5_connector import OrderType as OT

            if order_type_str == "Limit":
                mt5_order_type = OT.BUY_LIMIT if signal == Signal.BUY else OT.SELL_LIMIT
            else:  # Stop
                mt5_order_type = OT.BUY_STOP if signal == Signal.BUY else OT.SELL_STOP

            result = connector.place_pending_order(
                symbol=symbol,
                order_type=mt5_order_type,
                volume=lot_size,
                price=entry_price or price,
                stop_loss=sl_price,
                take_profit=tp_price,
                comment=comment
            )

            st.session_state["trade_result"] = {
                "success": result.success,
                "ticket": result.ticket,
                "error": result.error_message
            }

    except Exception as e:
        st.session_state["trade_result"] = {
            "success": False,
            "error": str(e)
        }


def close_all_positions():
    """Close all open positions."""
    connector = get_connector()

    if not connector or not connector.is_connected():
        st.error("Not connected to MT5")
        return

    try:
        closed, failed = connector.close_all_positions()
        if closed > 0:
            st.success(f"Closed {closed} positions")
        if failed > 0:
            st.warning(f"Failed to close {failed} positions")
    except Exception as e:
        st.error(f"Error closing positions: {e}")


def render_positions_table():
    """Render the open positions table."""
    connector = get_connector()

    if not connector or not connector.is_connected():
        st.info("Connect to MT5 to view open positions")
        return

    try:
        positions = connector.get_positions()

        if not positions:
            st.info("No open positions")
            return

        # Build positions data
        data = []
        for pos in positions:
            # Calculate duration
            duration = datetime.now() - pos.open_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m"

            # Calculate profit in pips
            symbol_info = connector.get_symbol_info(pos.symbol)
            pips = 0
            if symbol_info:
                tick = connector.get_tick(pos.symbol)
                if tick:
                    current_price = tick["bid"] if pos.type == Signal.BUY else tick["ask"]
                    price_diff = current_price - pos.open_price
                    if pos.type == Signal.SELL:
                        price_diff = -price_diff
                    pips = price_diff / (symbol_info.point * 10)

            data.append({
                "Ticket": pos.ticket,
                "Symbol": pos.symbol,
                "Type": "BUY" if pos.type == Signal.BUY else "SELL",
                "Lots": pos.volume,
                "Entry": f"{pos.open_price:.5f}",
                "SL": f"{pos.stop_loss:.5f}" if pos.stop_loss > 0 else "-",
                "TP": f"{pos.take_profit:.5f}" if pos.take_profit > 0 else "-",
                "Pips": f"{pips:+.1f}",
                "Profit": f"${pos.profit:+.2f}",
                "Duration": duration_str,
                "ticket_id": pos.ticket  # For close button
            })

        df = pd.DataFrame(data)

        # Style the dataframe
        def highlight_profit(val):
            if isinstance(val, str) and val.startswith('$'):
                try:
                    profit = float(val.replace('$', '').replace('+', ''))
                    if profit > 0:
                        return 'color: #10b981'
                    elif profit < 0:
                        return 'color: #ef4444'
                except ValueError:
                    pass
            return ''

        # Display with close buttons
        for idx, row in df.iterrows():
            col_data, col_close = st.columns([10, 1])

            with col_data:
                cols = st.columns(10)
                for i, (col_name, value) in enumerate(list(row.items())[:-1]):
                    with cols[i]:
                        if col_name == "Profit":
                            profit_val = float(value.replace('$', '').replace('+', ''))
                            color = "#10b981" if profit_val >= 0 else "#ef4444"
                            st.markdown(f"<span style='color: {color};'>{value}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{value}**")

            with col_close:
                if st.button("✕", key=f"close_{row['ticket_id']}", help="Close position"):
                    if connector.close_position(row['ticket_id']):
                        st.success(f"Closed position {row['ticket_id']}")
                        st.rerun()
                    else:
                        st.error(f"Failed to close position {row['ticket_id']}")

    except Exception as e:
        st.error(f"Error loading positions: {e}")


def render_trade_history():
    """Render the trade history table."""
    connector = get_connector()

    if not connector or not connector.is_connected():
        st.info("Connect to MT5 to view trade history")
        return

    # Date range
    col_from, col_to = st.columns(2)
    with col_from:
        from_date = st.date_input(
            "From",
            value=datetime.now() - timedelta(days=7),
            key="history_from_date"
        )
    with col_to:
        to_date = st.date_input(
            "To",
            value=datetime.now(),
            key="history_to_date"
        )

    try:
        history = connector.get_history(
            start_date=datetime.combine(from_date, datetime.min.time()),
            end_date=datetime.combine(to_date, datetime.max.time())
        )

        if not history:
            st.info("No trade history found")
            return

        # Filter to show only entry/exit deals
        data = []
        for deal in history[-50:]:  # Last 50
            if deal.get("symbol"):  # Skip balance operations
                data.append({
                    "Ticket": deal["ticket"],
                    "Time": deal["time"].strftime("%Y-%m-%d %H:%M"),
                    "Symbol": deal["symbol"],
                    "Type": deal["type"],
                    "Volume": deal["volume"],
                    "Price": f"{deal['price']:.5f}",
                    "Profit": f"${deal['profit']:+.2f}",
                    "Commission": f"${deal.get('commission', 0):.2f}",
                    "Comment": deal.get("comment", "")[:20]
                })

        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Summary stats
            total_profit = sum(float(d["Profit"].replace("$", "").replace("+", "")) for d in data)
            wins = sum(1 for d in data if float(d["Profit"].replace("$", "").replace("+", "")) > 0)
            total = len(data)

            col_total, col_wins, col_rate = st.columns(3)
            with col_total:
                st.metric("Total P&L", f"${total_profit:+,.2f}")
            with col_wins:
                st.metric("Wins/Total", f"{wins}/{total}")
            with col_rate:
                rate = (wins / total * 100) if total > 0 else 0
                st.metric("Win Rate", f"{rate:.1f}%")

    except Exception as e:
        st.error(f"Error loading history: {e}")


def render_pending_orders():
    """Render pending orders table."""
    connector = get_connector()

    if not connector or not connector.is_connected():
        st.info("Connect to MT5 to view pending orders")
        return

    try:
        orders = connector.get_pending_orders()

        if not orders:
            st.info("No pending orders")
            return

        data = []
        for order in orders:
            data.append({
                "Ticket": order["ticket"],
                "Symbol": order["symbol"],
                "Type": order["type"],
                "Volume": order["volume"],
                "Price": f"{order['price']:.5f}",
                "SL": f"{order['sl']:.5f}" if order['sl'] > 0 else "-",
                "TP": f"{order['tp']:.5f}" if order['tp'] > 0 else "-",
                "Comment": order.get("comment", "")[:20],
                "ticket_id": order["ticket"]
            })

        df = pd.DataFrame(data)

        # Display with cancel buttons
        for idx, row in df.iterrows():
            col_data, col_cancel = st.columns([10, 1])

            with col_data:
                cols = st.columns(8)
                for i, (col_name, value) in enumerate(list(row.items())[:-1]):
                    with cols[i]:
                        st.markdown(f"**{value}**")

            with col_cancel:
                if st.button("✕", key=f"cancel_{row['ticket_id']}", help="Cancel order"):
                    if connector.cancel_pending_order(row['ticket_id']):
                        st.success(f"Cancelled order {row['ticket_id']}")
                        st.rerun()
                    else:
                        st.error(f"Failed to cancel order {row['ticket_id']}")

    except Exception as e:
        st.error(f"Error loading pending orders: {e}")
