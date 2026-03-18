"""
Reusable UI widgets for the trading bot.
"""
import streamlit as st
from typing import Dict, Any, List, Optional


def metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal"
):
    """
    Display a metric card.

    Args:
        label: Metric label
        value: Metric value
        delta: Delta value (optional)
        delta_color: "normal", "inverse", or "off"
    """
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def status_badge(status: str, labels: Dict[str, str] = None):
    """
    Display a status badge.

    Args:
        status: Status key
        labels: Optional mapping of status to display text
    """
    colors = {
        "running": "green",
        "stopped": "red",
        "paused": "orange",
        "error": "red",
        "connected": "green",
        "disconnected": "red"
    }

    texts = labels or {
        "running": "🟢 Running",
        "stopped": "🔴 Stopped",
        "paused": "🟡 Paused",
        "error": "🔴 Error",
        "connected": "🟢 Connected",
        "disconnected": "🔴 Disconnected"
    }

    st.markdown(f"**Status:** {texts.get(status, status)}")


def trade_row(
    symbol: str,
    direction: str,
    entry: float,
    current: float,
    pnl: float,
    strategy: str
):
    """
    Display a trade row.

    Args:
        symbol: Trading symbol
        direction: BUY or SELL
        entry: Entry price
        current: Current price
        pnl: Profit/Loss
        strategy: Strategy name
    """
    direction_emoji = "🟢" if direction == "BUY" else "🔴"
    pnl_color = "green" if pnl >= 0 else "red"
    pnl_sign = "+" if pnl >= 0 else ""

    st.markdown(
        f"{direction_emoji} **{symbol}** {direction} | "
        f"Entry: {entry:.5f} → {current:.5f} | "
        f"<span style='color:{pnl_color}'>{pnl_sign}${pnl:.2f}</span> | "
        f"_{strategy}_",
        unsafe_allow_html=True
    )


def risk_indicator(
    current: float,
    limit: float,
    label: str = "Risk"
):
    """
    Display a risk indicator.

    Args:
        current: Current value
        limit: Limit value
        label: Indicator label
    """
    percentage = (current / limit) * 100 if limit > 0 else 0

    if percentage < 50:
        status = "🟢"
    elif percentage < 80:
        status = "🟡"
    else:
        status = "🔴"

    st.markdown(f"{status} **{label}:** {current:.1f}% / {limit:.1f}%")


def strategy_card(
    name: str,
    enabled: bool,
    symbols: List[str],
    timeframe: str,
    stats: Dict[str, Any] = None
):
    """
    Display a strategy card.

    Args:
        name: Strategy name
        enabled: Whether strategy is enabled
        symbols: List of symbols
        timeframe: Timeframe
        stats: Optional statistics dict
    """
    status = "🟢 Enabled" if enabled else "🔴 Disabled"

    st.markdown(f"""
    ### {name}
    **Status:** {status}
    **Symbols:** {', '.join(symbols)}
    **Timeframe:** {timeframe}
    """)

    if stats:
        cols = st.columns(4)
        with cols[0]:
            st.metric("Trades", stats.get("trades", 0))
        with cols[1]:
            st.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
        with cols[2]:
            st.metric("P&L", f"${stats.get('pnl', 0):.2f}")
        with cols[3]:
            st.metric("Profit Factor", f"{stats.get('profit_factor', 0):.2f}")


def confirmation_dialog(
    title: str,
    message: str,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel"
) -> Optional[bool]:
    """
    Display a confirmation dialog.

    Args:
        title: Dialog title
        message: Dialog message
        confirm_label: Confirm button label
        cancel_label: Cancel button label

    Returns:
        True if confirmed, False if cancelled, None if no action
    """
    st.markdown(f"### {title}")
    st.markdown(message)

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button(confirm_label, type="primary"):
            return True

    with col2:
        if st.button(cancel_label):
            return False

    return None


def info_box(message: str, type: str = "info"):
    """
    Display an info box.

    Args:
        message: Message to display
        type: "info", "success", "warning", or "error"
    """
    if type == "success":
        st.success(message)
    elif type == "warning":
        st.warning(message)
    elif type == "error":
        st.error(message)
    else:
        st.info(message)
