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

# Custom CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .profit {
        color: #00c853;
    }
    .loss {
        color: #ff1744;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    st.sidebar.title("📈 Trading Bot")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Strategies", "Backtest", "Settings"],
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Status:** 🟢 Running")
    st.sidebar.markdown("**MT5:** Connected")

    # Page routing
    if page == "Dashboard":
        from pages.dashboard import render_dashboard
        render_dashboard()
    elif page == "Strategies":
        from pages.strategies import render_strategies
        render_strategies()
    elif page == "Backtest":
        from pages.backtest import render_backtest
        render_backtest()
    elif page == "Settings":
        from pages.settings import render_settings
        render_settings()


if __name__ == "__main__":
    main()
