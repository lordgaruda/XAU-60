"""
Backtest Page - Strategy backtesting interface.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render_backtest():
    """Render the backtesting page."""
    st.markdown("""
    <div class="page-header">
        <h1>Strategy Backtesting</h1>
        <p>Test your strategies against historical data</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar configuration
    with st.sidebar:
        st.markdown("### Backtest Settings")

        # Load available strategies
        config_dir = Path(__file__).parent.parent.parent / "config" / "strategies"
        strategy_files = list(config_dir.glob("*.yaml")) if config_dir.exists() else []

        strategies = {}
        for f in strategy_files:
            try:
                with open(f, "r") as file:
                    config = yaml.safe_load(file)
                    strategies[config.get('name', f.stem)] = f.stem
            except Exception:
                pass

        selected_strategy = st.selectbox(
            "Strategy",
            options=list(strategies.keys()) if strategies else ["No strategies found"],
            key="backtest_strategy_select"
        )

        symbol = st.selectbox(
            "Symbol",
            options=["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"],
            key="backtest_symbol_select"
        )

        timeframe = st.selectbox(
            "Timeframe",
            options=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            index=2,
            key="backtest_timeframe_select"
        )

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=90),
                key="backtest_start_date"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                key="backtest_end_date"
            )

        initial_balance = st.number_input(
            "Initial Balance ($)",
            value=10000.0,
            step=1000.0,
            key="backtest_initial_balance"
        )

        lot_size = st.number_input(
            "Lot Size",
            value=0.1,
            step=0.01,
            format="%.2f",
            key="backtest_lot_size"
        )

        run_backtest = st.button(
            "Run Backtest",
            type="primary",
            use_container_width=True,
            key="backtest_run_button"
        )

    # Main content
    if run_backtest:
        with st.spinner("Running backtest..."):
            # Simulate backtest results
            results = simulate_backtest_results(
                initial_balance=initial_balance,
                days=(end_date - start_date).days
            )

            display_backtest_results(results)
    else:
        st.markdown("""
        <div class="info-card">
            <h4>Ready to Backtest</h4>
            <p>Configure your backtest parameters in the sidebar and click <strong>Run Backtest</strong> to start.</p>
        </div>
        """, unsafe_allow_html=True)

        # Show sample results preview
        st.markdown("### Sample Results Preview")

        results = simulate_backtest_results(initial_balance=10000, days=30)
        display_backtest_results(results)


def simulate_backtest_results(initial_balance: float, days: int) -> dict:
    """Simulate backtest results for demo."""
    import random

    # Generate equity curve
    equity = [initial_balance]
    for i in range(days):
        change = random.uniform(-0.02, 0.03) * equity[-1]
        equity.append(equity[-1] + change)

    # Generate trades
    trades = []
    num_trades = max(10, days // 3)
    for i in range(num_trades):
        pnl = random.uniform(-100, 200)
        trades.append({
            "date": datetime.now() - timedelta(days=random.randint(0, days)),
            "symbol": "XAUUSD",
            "type": random.choice(["BUY", "SELL"]),
            "entry": round(2000 + random.uniform(-50, 50), 2),
            "exit": round(2000 + random.uniform(-50, 50), 2),
            "pnl": round(pnl, 2),
            "pips": round(pnl / 10, 1)
        })

    # Calculate metrics
    final_balance = equity[-1]
    profits = [t['pnl'] for t in trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in trades if t['pnl'] < 0]

    # Drawdown
    peak = equity[0]
    max_dd = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        "equity_curve": equity,
        "trades": sorted(trades, key=lambda x: x['date'], reverse=True),
        "metrics": {
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "total_profit": final_balance - initial_balance,
            "total_profit_pct": (final_balance - initial_balance) / initial_balance * 100,
            "total_trades": len(trades),
            "winning_trades": len(profits),
            "losing_trades": len(losses),
            "win_rate": len(profits) / len(trades) * 100 if trades else 0,
            "profit_factor": abs(sum(profits) / sum(losses)) if losses else 0,
            "max_drawdown": max_dd,
            "avg_win": sum(profits) / len(profits) if profits else 0,
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "sharpe_ratio": 1.5 + random.uniform(-0.5, 0.5)
        }
    }


def display_backtest_results(results: dict):
    """Display backtest results."""
    metrics = results["metrics"]

    # Key metrics
    st.markdown("### Performance Summary")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Total P&L",
            f"${metrics['total_profit']:.2f}",
            f"{metrics['total_profit_pct']:.2f}%"
        )

    with col2:
        st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")

    with col3:
        st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")

    with col4:
        st.metric("Max Drawdown", f"{metrics['max_drawdown']:.2f}%")

    with col5:
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")

    st.markdown("---")

    # Equity curve chart
    st.markdown("### Equity Curve")

    dates = pd.date_range(
        end=datetime.now(),
        periods=len(results["equity_curve"]),
        freq='D'
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=results["equity_curve"],
        mode='lines',
        fill='tozeroy',
        line=dict(color='#6366f1', width=2),
        fillcolor='rgba(99, 102, 241, 0.1)',
        name='Equity'
    ))

    # Add initial balance line
    fig.add_hline(
        y=metrics["initial_balance"],
        line_dash="dash",
        line_color="#64748b",
        annotation_text="Initial Balance"
    )

    fig.update_layout(
        height=400,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
        yaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
        font=dict(color='#94a3b8')
    )
    st.plotly_chart(fig, use_container_width=True, key="backtest_equity_chart")

    # Two column layout for detailed stats and trades
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### Detailed Statistics")

        stats_df = pd.DataFrame({
            "Metric": [
                "Initial Balance",
                "Final Balance",
                "Total Profit",
                "Total Trades",
                "Winning Trades",
                "Losing Trades",
                "Win Rate",
                "Average Win",
                "Average Loss",
                "Profit Factor",
                "Max Drawdown",
                "Sharpe Ratio"
            ],
            "Value": [
                f"${metrics['initial_balance']:.2f}",
                f"${metrics['final_balance']:.2f}",
                f"${metrics['total_profit']:.2f}",
                metrics['total_trades'],
                metrics['winning_trades'],
                metrics['losing_trades'],
                f"{metrics['win_rate']:.1f}%",
                f"${metrics['avg_win']:.2f}",
                f"${metrics['avg_loss']:.2f}",
                f"{metrics['profit_factor']:.2f}",
                f"{metrics['max_drawdown']:.2f}%",
                f"{metrics['sharpe_ratio']:.2f}"
            ]
        })

        st.dataframe(stats_df, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("### Trade Distribution")

        # P&L distribution
        pnls = [t['pnl'] for t in results['trades']]

        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=pnls,
            nbinsx=20,
            marker_color='#6366f1'
        ))
        fig_dist.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="P&L ($)",
            yaxis_title="Count",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            yaxis=dict(gridcolor='rgba(51, 65, 85, 0.5)'),
            font=dict(color='#94a3b8')
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="backtest_distribution_chart")

    # Trade log
    st.markdown("---")
    st.markdown("### Trade Log")

    trades_df = pd.DataFrame(results['trades'])
    trades_df['date'] = pd.to_datetime(trades_df['date']).dt.strftime('%Y-%m-%d %H:%M')

    st.dataframe(trades_df, use_container_width=True, hide_index=True)

    # Export button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        csv = trades_df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            "backtest_trades.csv",
            "text/csv",
            use_container_width=True,
            key="backtest_download_csv"
        )
