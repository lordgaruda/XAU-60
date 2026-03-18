"""
Chart components for the trading bot UI.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import List, Optional


def create_candlestick_chart(
    data: pd.DataFrame,
    title: str = "",
    height: int = 500
) -> go.Figure:
    """
    Create a candlestick chart.

    Args:
        data: DataFrame with time, open, high, low, close columns
        title: Chart title
        height: Chart height in pixels

    Returns:
        Plotly figure
    """
    fig = go.Figure(data=[go.Candlestick(
        x=data['time'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='Price'
    )])

    fig.update_layout(
        title=title,
        height=height,
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0)
    )

    return fig


def create_equity_curve(
    equity: List[float],
    dates: Optional[List] = None,
    initial_balance: float = 0,
    height: int = 300
) -> go.Figure:
    """
    Create an equity curve chart.

    Args:
        equity: List of equity values
        dates: Optional list of dates
        initial_balance: Initial balance for reference line
        height: Chart height

    Returns:
        Plotly figure
    """
    x = dates if dates else list(range(len(equity)))

    fig = go.Figure()

    # Equity line
    fig.add_trace(go.Scatter(
        x=x,
        y=equity,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#00c853', width=2),
        fillcolor='rgba(0, 200, 83, 0.1)',
        name='Equity'
    ))

    # Initial balance reference
    if initial_balance > 0:
        fig.add_hline(
            y=initial_balance,
            line_dash="dash",
            line_color="gray",
            annotation_text="Initial Balance"
        )

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Time",
        yaxis_title="Equity ($)"
    )

    return fig


def create_pnl_distribution(
    pnl_values: List[float],
    height: int = 300
) -> go.Figure:
    """
    Create a P&L distribution histogram.

    Args:
        pnl_values: List of P&L values
        height: Chart height

    Returns:
        Plotly figure
    """
    colors = ['#00c853' if pnl > 0 else '#ff1744' for pnl in pnl_values]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=pnl_values,
        nbinsx=30,
        marker_color='#2196f3'
    ))

    fig.add_vline(x=0, line_dash="dash", line_color="gray")

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="P&L ($)",
        yaxis_title="Count"
    )

    return fig


def create_drawdown_chart(
    equity: List[float],
    dates: Optional[List] = None,
    height: int = 200
) -> go.Figure:
    """
    Create a drawdown chart.

    Args:
        equity: List of equity values
        dates: Optional list of dates
        height: Chart height

    Returns:
        Plotly figure
    """
    x = dates if dates else list(range(len(equity)))

    # Calculate drawdown
    peak = equity[0]
    drawdown = []
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100
        drawdown.append(-dd)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x,
        y=drawdown,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#ff1744', width=2),
        fillcolor='rgba(255, 23, 68, 0.1)',
        name='Drawdown'
    ))

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Time",
        yaxis_title="Drawdown (%)"
    )

    return fig


def create_win_rate_gauge(
    win_rate: float,
    height: int = 200
) -> go.Figure:
    """
    Create a win rate gauge chart.

    Args:
        win_rate: Win rate percentage (0-100)
        height: Chart height

    Returns:
        Plotly figure
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=win_rate,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Win Rate (%)"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': '#2196f3'},
            'steps': [
                {'range': [0, 40], 'color': '#ffebee'},
                {'range': [40, 60], 'color': '#fff3e0'},
                {'range': [60, 100], 'color': '#e8f5e9'}
            ],
            'threshold': {
                'line': {'color': '#00c853', 'width': 4},
                'thickness': 0.75,
                'value': 50
            }
        }
    ))

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10)
    )

    return fig
