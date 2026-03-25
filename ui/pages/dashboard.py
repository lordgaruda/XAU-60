"""
Dashboard Page - Live trading overview.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render_dashboard():
    """Render the dashboard page."""
    st.markdown("""
    <div class="page-header">
        <h1>Trading Dashboard</h1>
        <p>Real-time overview of your trading performance</p>
    </div>
    """, unsafe_allow_html=True)

    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Balance", "$10,450.00", "+$450.00")

    with col2:
        st.metric("Equity", "$10,520.00", "+$70.00")

    with col3:
        st.metric("Open P&L", "+$70.00", "0.67%")

    with col4:
        st.metric("Today's P&L", "+$185.00", "1.8%")

    with col5:
        st.metric("Win Rate", "68%", "+3%")

    st.markdown("<br>", unsafe_allow_html=True)

    # Two column layout
    col_left, col_right = st.columns([2, 1])

    with col_left:
        # Equity curve
        st.markdown("### Equity Curve")

        # Sample data
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
        equity = [10000 + i * 15 + (i % 5) * 10 - (i % 3) * 5 for i in range(len(dates))]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity,
            mode='lines',
            fill='tozeroy',
            line=dict(color='#6366f1', width=2),
            fillcolor='rgba(99, 102, 241, 0.1)'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            yaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            font=dict(color='#94a3b8')
        )
        st.plotly_chart(fig, use_container_width=True, key="dashboard_equity_chart")

        # Open positions
        st.markdown("### Open Positions")

        positions_data = {
            "Ticket": [12345, 12346],
            "Symbol": ["XAUUSD", "XAUUSD"],
            "Type": ["BUY", "SELL"],
            "Volume": [0.02, 0.01],
            "Entry": [2015.50, 2018.30],
            "Current": [2017.80, 2016.50],
            "P&L": ["+$46.00", "+$18.00"],
            "Strategy": ["SMC Scalper", "Trend Break"]
        }

        if positions_data["Ticket"]:
            df = pd.DataFrame(positions_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions")

    with col_right:
        # Risk status
        st.markdown("### Risk Status")

        risk_data = {
            "Metric": ["Daily Loss", "Drawdown", "Open Positions", "Margin Level"],
            "Current": ["1.2%", "3.5%", "2/5", "850%"],
            "Limit": ["5.0%", "20.0%", "5", "150%"],
            "Status": ["🟢", "🟢", "🟢", "🟢"]
        }
        st.dataframe(pd.DataFrame(risk_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Recent trades
        st.markdown("### Recent Trades")

        trades = [
            {"time": "14:32", "symbol": "XAUUSD", "type": "BUY", "pnl": "+$32.50"},
            {"time": "12:15", "symbol": "XAUUSD", "type": "SELL", "pnl": "-$12.00"},
            {"time": "10:45", "symbol": "XAUUSD", "type": "BUY", "pnl": "+$45.00"},
            {"time": "09:20", "symbol": "EURUSD", "type": "SELL", "pnl": "+$28.00"},
        ]

        for trade in trades:
            pnl_class = "profit" if "+" in trade["pnl"] else "loss"
            type_icon = "🟢" if trade["type"] == "BUY" else "🔴"
            st.markdown(
                f"{type_icon} **{trade['time']}** {trade['symbol']} "
                f"<span class='{pnl_class}'>{trade['pnl']}</span>",
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Strategy performance
        st.markdown("### Strategy Performance")

        strategy_perf = {
            "Strategy": ["SMC Scalper", "Trend Break"],
            "Trades": [45, 23],
            "Win %": ["72%", "61%"],
            "P&L": ["+$680", "+$245"]
        }
        st.dataframe(pd.DataFrame(strategy_perf), use_container_width=True, hide_index=True)

    # Bottom: Trade log
    st.markdown("---")
    st.markdown("### Trade History")

    history_data = {
        "Date": ["2024-01-15", "2024-01-15", "2024-01-14", "2024-01-14", "2024-01-13"],
        "Symbol": ["XAUUSD", "XAUUSD", "XAUUSD", "EURUSD", "XAUUSD"],
        "Type": ["BUY", "SELL", "BUY", "SELL", "BUY"],
        "Entry": [2015.50, 2020.30, 2010.00, 1.08520, 2005.00],
        "Exit": [2018.20, 2018.50, 2015.50, 1.08420, 2010.00],
        "P&L": ["+$54.00", "+$36.00", "+$110.00", "+$25.00", "+$100.00"],
        "Strategy": ["SMC Scalper", "SMC Scalper", "Trend Break", "Trend Break", "SMC Scalper"]
    }

    df_history = pd.DataFrame(history_data)
    st.dataframe(df_history, use_container_width=True, hide_index=True)
