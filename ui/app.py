"""
Streamlit Trading Bot UI - Main Application.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="MT5 Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern CSS styling
st.markdown("""
<style>
    /* CSS Variables for theming */
    :root {
        --primary: #6366f1;
        --primary-dark: #4f46e5;
        --success: #10b981;
        --danger: #ef4444;
        --warning: #f59e0b;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --bg-card-hover: #334155;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --border-color: #334155;
    }

    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    /* Fix column layout for metrics */
    [data-testid="column"] {
        overflow: visible !important;
    }

    [data-testid="stHorizontalBlock"] {
        gap: 1rem;
        flex-wrap: wrap;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }

    [data-testid="stSidebar"] .stMarkdown {
        color: #f8fafc;
    }

    /* Page header styling */
    .page-header {
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--border-color);
    }

    .page-header h1 {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .page-header p {
        color: var(--text-secondary);
        margin: 0;
    }

    /* Card styling */
    .card {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border-color);
        transition: all 0.2s ease;
    }

    .card:hover {
        border-color: var(--primary);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
    }

    /* Strategy card */
    .strategy-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid var(--border-color);
    }

    .strategy-card.enabled {
        border-left-color: var(--success);
    }

    .strategy-card.disabled {
        border-left-color: var(--danger);
    }

    .strategy-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .strategy-title {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .strategy-name {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .strategy-timeframe {
        background: var(--primary);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }

    /* Badges */
    .badge-success {
        background: var(--success);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .badge-secondary {
        background: var(--text-secondary);
        color: var(--bg-dark);
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1rem 1.25rem;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        overflow: visible !important;
    }

    [data-testid="stMetric"]:hover {
        border-color: var(--primary);
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-size: 0.85rem;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: unset !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 700;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: unset !important;
        font-size: 1.5rem !important;
    }

    [data-testid="stMetricDelta"] {
        white-space: nowrap !important;
        overflow: visible !important;
    }

    /* Fix metric container overflow */
    [data-testid="stMetric"] > div {
        overflow: visible !important;
    }

    [data-testid="stMetric"] > div > div {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: nowrap !important;
    }

    /* Positive delta */
    [data-testid="stMetricDelta"] svg {
        stroke: var(--success);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border: none;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        transform: translateY(-1px);
    }

    .stButton > button[kind="secondary"] {
        background: transparent;
        border: 1px solid var(--border-color);
        color: var(--text-primary);
    }

    .stButton > button[kind="secondary"]:hover {
        border-color: var(--primary);
        background: rgba(99, 102, 241, 0.1);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        background: var(--bg-card);
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        border: 1px solid var(--border-color);
        color: var(--text-secondary);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border-color: transparent !important;
    }

    /* Input fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        color: var(--text-primary);
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: var(--bg-card);
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    /* Info card */
    .info-card {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .info-card h4 {
        color: var(--primary);
        margin-bottom: 1rem;
    }

    .info-card ol {
        margin: 0;
        padding-left: 1.25rem;
        color: var(--text-secondary);
    }

    .info-card li {
        margin-bottom: 0.5rem;
    }

    .info-card code {
        background: var(--bg-card);
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.85rem;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem;
        color: var(--text-secondary);
    }

    .empty-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }

    .empty-state h3 {
        color: var(--text-primary);
        margin-bottom: 0.5rem;
    }

    /* Symbol tags */
    .symbol-tag {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.25rem;
    }

    /* Profit/Loss colors */
    .profit {
        color: var(--success) !important;
    }

    .loss {
        color: var(--danger) !important;
    }

    /* Dividers */
    hr {
        border-color: var(--border-color);
        opacity: 0.5;
    }

    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--bg-dark);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-secondary);
    }

    /* Status indicators */
    .status-running {
        color: var(--success);
    }

    .status-stopped {
        color: var(--danger);
    }

    /* Sidebar nav items */
    [data-testid="stSidebar"] .stRadio > label {
        color: var(--text-primary);
    }

    /* Toggle switch */
    .stToggle > label > div {
        background: var(--bg-card);
    }
</style>
""", unsafe_allow_html=True)


def get_connection_status():
    """Get MT5 connection status from account manager."""
    try:
        from core.account_manager import get_account_manager, ConnectionStatus
        manager = get_account_manager()
        status = manager.get_connection_status()
        active = manager.get_active_account()

        if status == ConnectionStatus.CONNECTED:
            return "connected", active.name if active else "Connected"
        elif status == ConnectionStatus.CONNECTING:
            return "connecting", "Connecting..."
        elif status == ConnectionStatus.RECONNECTING:
            return "reconnecting", "Reconnecting..."
        else:
            return "disconnected", "Disconnected"
    except Exception:
        return "disconnected", "Not Initialized"


def main():
    """Main application entry point."""
    # Get connection status
    conn_status, conn_text = get_connection_status()

    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="margin: 0; background: linear-gradient(135deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">MT5 Trading Bot</h2>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Navigation - Updated with new pages
        page = st.radio(
            "Navigation",
            ["Dashboard", "Strategies", "Strategy Builder", "Backtest", "Accounts", "Settings"],
            index=0,
            key="main_navigation",
            label_visibility="collapsed"
        )

        st.markdown("---")

        # Dynamic status indicators
        if conn_status == "connected":
            status_color = "#10b981"
            status_icon = "●"
        elif conn_status in ["connecting", "reconnecting"]:
            status_color = "#f59e0b"
            status_icon = "○"
        else:
            status_color = "#ef4444"
            status_icon = "●"

        st.markdown(f"""
        <div style="padding: 0.5rem 0;">
            <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                <span style="color: {status_color};">{status_icon}</span> MT5: {conn_text}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Quick account selector
        try:
            from core.account_manager import get_account_manager
            manager = get_account_manager()
            accounts = manager.list_accounts()

            if accounts:
                account_names = [f"{a.name} ({a.login})" for a in accounts]
                active = manager.get_active_account()
                active_idx = 0
                if active:
                    for i, a in enumerate(accounts):
                        if a.id == active.id:
                            active_idx = i
                            break

                selected = st.selectbox(
                    "Account",
                    account_names,
                    index=active_idx,
                    key="sidebar_account_select",
                    label_visibility="collapsed"
                )

                # Switch account if changed
                selected_idx = account_names.index(selected)
                if accounts[selected_idx].id != (active.id if active else None):
                    if st.button("Switch", key="sidebar_switch_btn", use_container_width=True):
                        manager.switch_account(accounts[selected_idx].id)
                        st.rerun()
        except Exception:
            pass

        st.markdown("---")

        # Version info
        st.markdown("""
        <div style="text-align: center; color: #64748b; font-size: 0.75rem;">
            v2.0.0 Pro
        </div>
        """, unsafe_allow_html=True)

    # Page routing
    if page == "Dashboard":
        from pages.dashboard import render_dashboard
        render_dashboard()
    elif page == "Strategies":
        from pages.strategies import render_strategies
        render_strategies()
    elif page == "Strategy Builder":
        from pages.strategy_builder import render_strategy_builder
        render_strategy_builder()
    elif page == "Backtest":
        from pages.backtest import render_backtest
        render_backtest()
    elif page == "Accounts":
        from pages.accounts import render_accounts
        render_accounts()
    elif page == "Settings":
        from pages.settings import render_settings
        render_settings()


if __name__ == "__main__":
    main()
