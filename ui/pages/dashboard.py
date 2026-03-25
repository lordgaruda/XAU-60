"""
Dashboard Page - Live trading overview.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path
import yaml
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_mt5_connector():
    """Get MT5 connector with connection handling."""
    try:
        from core.mt5_connector import MT5Connector
        return MT5Connector()
    except ImportError:
        return None


def load_settings():
    """Load settings from YAML file."""
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    try:
        with open(settings_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_mt5_credentials():
    """Get MT5 credentials from settings or environment."""
    import os
    settings = load_settings()
    mt5_settings = settings.get("mt5", {})

    return {
        "login": int(os.environ.get("MT5_LOGIN", mt5_settings.get("login", 0))),
        "password": os.environ.get("MT5_PASSWORD", mt5_settings.get("password", "")),
        "server": os.environ.get("MT5_SERVER", mt5_settings.get("server", "")),
        "path": os.environ.get("MT5_PATH", mt5_settings.get("path")),
        "timeout": mt5_settings.get("timeout", 60000)
    }


@st.cache_data(ttl=5)
def get_account_data():
    """Get account data from MT5 or mock data."""
    mt5 = get_mt5_connector()
    if mt5:
        try:
            creds = get_mt5_credentials()
            if creds["login"] and creds["password"] and creds["server"]:
                if mt5.connect(
                    login=creds["login"],
                    password=creds["password"],
                    server=creds["server"],
                    path=creds["path"] or None,
                    timeout=creds["timeout"]
                ):
                    account = mt5.get_account_info()
                    if account:
                        data = {
                            "connected": True,
                            "balance": account.balance,
                            "equity": account.equity,
                            "profit": account.profit,
                            "margin": account.margin,
                            "free_margin": account.free_margin,
                            "margin_level": account.margin_level,
                            "currency": account.currency,
                            "server": account.server,
                            "login": account.login,
                            "leverage": account.leverage
                        }
                        mt5.disconnect()
                        return data
            else:
                # Try connecting without credentials (auto-connect)
                if mt5.connect():
                    account = mt5.get_account_info()
                    if account:
                        data = {
                            "connected": True,
                            "balance": account.balance,
                            "equity": account.equity,
                            "profit": account.profit,
                            "margin": account.margin,
                            "free_margin": account.free_margin,
                            "margin_level": account.margin_level,
                            "currency": account.currency,
                            "server": account.server,
                            "login": account.login,
                            "leverage": account.leverage
                        }
                        mt5.disconnect()
                        return data
        except Exception as e:
            st.session_state["mt5_error"] = str(e)

    # Return mock data
    return {
        "connected": False,
        "balance": 10000.00,
        "equity": 10000.00,
        "profit": 0.00,
        "margin": 0.00,
        "free_margin": 10000.00,
        "margin_level": 0.00,
        "currency": "USD",
        "server": "Demo (Mock)",
        "login": 12345678,
        "leverage": 100
    }


@st.cache_data(ttl=5)
def get_positions_data():
    """Get open positions from MT5 or mock data."""
    mt5 = get_mt5_connector()
    if mt5:
        try:
            creds = get_mt5_credentials()
            connected = False
            if creds["login"] and creds["password"] and creds["server"]:
                connected = mt5.connect(
                    login=creds["login"],
                    password=creds["password"],
                    server=creds["server"],
                    path=creds["path"] or None
                )
            else:
                connected = mt5.connect()

            if connected:
                positions = mt5.get_positions()
                mt5.disconnect()

                if positions:
                    return [{
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": "BUY" if p.type.name == "BUY" else "SELL",
                        "volume": p.volume,
                        "entry": p.open_price,
                        "current": p.open_price + (p.profit / (p.volume * 100)),
                        "sl": p.stop_loss,
                        "tp": p.take_profit,
                        "profit": p.profit,
                        "strategy": p.comment or "Manual"
                    } for p in positions]
        except Exception:
            pass

    # Return mock data
    return [
        {
            "ticket": 12345,
            "symbol": "XAUUSD",
            "type": "BUY",
            "volume": 0.02,
            "entry": 2015.50,
            "current": 2017.80,
            "sl": 2010.00,
            "tp": 2025.00,
            "profit": 46.00,
            "strategy": "SMC Scalper"
        },
        {
            "ticket": 12346,
            "symbol": "XAUUSD",
            "type": "SELL",
            "volume": 0.01,
            "entry": 2018.30,
            "current": 2016.50,
            "sl": 2025.00,
            "tp": 2010.00,
            "profit": 18.00,
            "strategy": "Trend Break"
        }
    ]


@st.cache_data(ttl=60)
def get_trade_history():
    """Get trade history from MT5 or mock data."""
    mt5 = get_mt5_connector()
    if mt5:
        try:
            creds = get_mt5_credentials()
            connected = False
            if creds["login"] and creds["password"] and creds["server"]:
                connected = mt5.connect(
                    login=creds["login"],
                    password=creds["password"],
                    server=creds["server"],
                    path=creds["path"] or None
                )
            else:
                connected = mt5.connect()

            if connected:
                history = mt5.get_history(
                    start_date=datetime.now() - timedelta(days=30),
                    end_date=datetime.now()
                )
                mt5.disconnect()

                if history:
                    return [{
                        "time": h["time"].strftime("%H:%M") if isinstance(h["time"], datetime) else h["time"],
                        "date": h["time"].strftime("%Y-%m-%d") if isinstance(h["time"], datetime) else "",
                        "symbol": h["symbol"],
                        "type": h["type"],
                        "profit": h["profit"]
                    } for h in history[-10:]]
        except Exception:
            pass

    # Return mock data
    return [
        {"time": "14:32", "date": "2024-01-15", "symbol": "XAUUSD", "type": "BUY", "profit": 32.50},
        {"time": "12:15", "date": "2024-01-15", "symbol": "XAUUSD", "type": "SELL", "profit": -12.00},
        {"time": "10:45", "date": "2024-01-15", "symbol": "XAUUSD", "type": "BUY", "profit": 45.00},
        {"time": "09:20", "date": "2024-01-14", "symbol": "EURUSD", "type": "SELL", "profit": 28.00},
        {"time": "16:30", "date": "2024-01-14", "symbol": "XAUUSD", "type": "BUY", "profit": 55.00},
    ]


def render_dashboard():
    """Render the dashboard page."""
    st.markdown("""
    <div class="page-header">
        <h1>Trading Dashboard</h1>
        <p>Real-time overview of your trading performance</p>
    </div>
    """, unsafe_allow_html=True)

    # Get data
    account = get_account_data()
    positions = get_positions_data()

    # Connection status
    if account["connected"]:
        st.success(f"Connected to {account['server']} | Account: {account['login']}")
    else:
        st.warning("Running in demo mode - Configure MT5 credentials in Settings to connect")

    # Auto-refresh toggle
    col_refresh, col_status = st.columns([3, 1])
    with col_refresh:
        auto_refresh = st.toggle("Auto-refresh (5s)", value=False, key="dashboard_auto_refresh")
    with col_status:
        st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")

    if auto_refresh:
        time.sleep(5)
        st.rerun()

    st.markdown("---")

    # Top metrics row - use 4 columns for better display
    col1, col2, col3, col4 = st.columns(4)

    currency = account.get("currency", "USD")

    with col1:
        st.metric(
            "Balance",
            f"{account['balance']:,.2f} {currency}",
            help="Account balance"
        )

    with col2:
        st.metric(
            "Equity",
            f"{account['equity']:,.2f} {currency}",
            f"{account['profit']:+,.2f}" if account['profit'] != 0 else None,
            help="Account equity (balance + open P&L)"
        )

    with col3:
        open_pnl = sum(p["profit"] for p in positions) if positions else 0
        st.metric(
            "Open P&L",
            f"{open_pnl:+,.2f} {currency}",
            f"{len(positions)} positions",
            help="Total profit/loss from open positions"
        )

    with col4:
        margin_level = account.get("margin_level", 0)
        st.metric(
            "Margin Level",
            f"{margin_level:,.0f}%" if margin_level > 0 else "N/A",
            help="Account margin level"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Two column layout
    col_left, col_right = st.columns([2, 1])

    with col_left:
        # Equity curve
        st.markdown("### Equity Curve")

        # Generate sample equity curve (in real app, this would come from trade history)
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
        base_balance = account['balance'] - 450  # Simulate starting balance
        equity = [base_balance + i * 15 + (i % 5) * 10 - (i % 3) * 5 for i in range(len(dates))]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity,
            mode='lines',
            fill='tozeroy',
            line=dict(color='#6366f1', width=2),
            fillcolor='rgba(99, 102, 241, 0.1)',
            name='Equity',
            hovertemplate='%{x}<br>Equity: $%{y:,.2f}<extra></extra>'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="Date",
            yaxis_title=f"Equity ({currency})",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            yaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            font=dict(color='#94a3b8')
        )
        st.plotly_chart(fig, use_container_width=True, key="dashboard_equity_chart")

        # Open positions
        st.markdown("### Open Positions")

        if positions:
            positions_df = pd.DataFrame(positions)
            positions_df["Profit"] = positions_df["profit"].apply(
                lambda x: f"+${x:.2f}" if x >= 0 else f"-${abs(x):.2f}"
            )
            positions_df = positions_df.rename(columns={
                "ticket": "Ticket",
                "symbol": "Symbol",
                "type": "Type",
                "volume": "Volume",
                "entry": "Entry",
                "current": "Current",
                "strategy": "Strategy"
            })

            display_cols = ["Ticket", "Symbol", "Type", "Volume", "Entry", "Current", "Profit", "Strategy"]
            st.dataframe(
                positions_df[display_cols],
                use_container_width=True,
                hide_index=True
            )

            # Quick actions
            col_close, col_space = st.columns([1, 3])
            with col_close:
                if st.button("Close All Positions", type="secondary", use_container_width=True, key="close_all_btn"):
                    st.warning("This feature requires MT5 connection. Configure in Settings.")
        else:
            st.info("No open positions")

    with col_right:
        # Risk status
        st.markdown("### Risk Status")

        # Calculate risk metrics
        daily_loss_pct = abs(account["profit"] / account["balance"] * 100) if account["balance"] > 0 else 0
        positions_count = len(positions) if positions else 0
        margin_level = account.get("margin_level", 0)

        settings = load_settings()
        risk_settings = settings.get("risk", {})

        risk_data = {
            "Metric": ["Daily P&L", "Open Positions", "Margin Level", "Free Margin"],
            "Current": [
                f"{account['profit']:+,.2f}",
                f"{positions_count}",
                f"{margin_level:,.0f}%" if margin_level > 0 else "N/A",
                f"{account['free_margin']:,.2f}"
            ],
            "Limit": [
                f"{risk_settings.get('max_daily_loss', 5.0)}%",
                f"{risk_settings.get('max_positions', 5)}",
                "150%",
                "-"
            ],
            "Status": [
                "🟢" if daily_loss_pct < risk_settings.get('max_daily_loss', 5.0) else "🔴",
                "🟢" if positions_count <= risk_settings.get('max_positions', 5) else "🔴",
                "🟢" if margin_level > 150 or margin_level == 0 else "🔴",
                "🟢"
            ]
        }
        st.dataframe(pd.DataFrame(risk_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Recent trades
        st.markdown("### Recent Trades")

        trades = get_trade_history()
        for trade in trades[:5]:
            profit = trade["profit"]
            pnl_class = "profit" if profit >= 0 else "loss"
            pnl_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
            type_icon = "🟢" if trade["type"] == "BUY" else "🔴"
            st.markdown(
                f"{type_icon} **{trade['time']}** {trade['symbol']} "
                f"<span class='{pnl_class}'>{pnl_str}</span>",
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Account info
        st.markdown("### Account Info")
        st.markdown(f"""
        **Server:** {account['server']}
        **Account:** {account['login']}
        **Leverage:** 1:{account['leverage']}
        **Currency:** {account['currency']}
        """)

    # Bottom: Trade log
    st.markdown("---")
    st.markdown("### Trade History (Last 30 Days)")

    history = get_trade_history()
    if history:
        history_df = pd.DataFrame(history)
        history_df["P&L"] = history_df["profit"].apply(
            lambda x: f"+${x:.2f}" if x >= 0 else f"-${abs(x):.2f}"
        )
        history_df = history_df.rename(columns={
            "date": "Date",
            "time": "Time",
            "symbol": "Symbol",
            "type": "Type"
        })
        display_cols = ["Date", "Time", "Symbol", "Type", "P&L"]
        st.dataframe(history_df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No trade history available")
