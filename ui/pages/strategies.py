"""
Strategies Page - Manage trading strategies.
"""
import streamlit as st
import pandas as pd
import yaml
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render_strategies():
    """Render the strategies management page."""
    st.markdown("""
    <div class="page-header">
        <h1>Strategy Management</h1>
        <p>Configure and manage your trading strategies</p>
    </div>
    """, unsafe_allow_html=True)

    # Strategy tabs with modern icons
    tab1, tab2, tab3 = st.tabs(["Active Strategies", "Configure", "Add New"])

    with tab1:
        render_active_strategies()

    with tab2:
        render_strategy_config()

    with tab3:
        render_add_strategy()


def render_active_strategies():
    """Render the list of active strategies."""
    # Load strategy configs
    config_dir = Path(__file__).parent.parent.parent / "config" / "strategies"

    strategies = []
    if config_dir.exists():
        for config_file in config_dir.glob("*.yaml"):
            try:
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)
                    strategies.append({
                        "file": config_file.name,
                        **config
                    })
            except Exception as e:
                st.error(f"Error loading {config_file.name}: {e}")

    if not strategies:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">📊</div>
            <h3>No Strategies Found</h3>
            <p>Create your first strategy to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Strategy cards grid
    for idx, strategy in enumerate(strategies):
        enabled = strategy.get('enabled', False)
        status_class = "enabled" if enabled else "disabled"

        with st.container():
            st.markdown(f"""
            <div class="strategy-card {status_class}">
                <div class="strategy-header">
                    <div class="strategy-title">
                        <span class="strategy-name">{strategy.get('name', 'Unknown')}</span>
                        <span class="strategy-badge {'badge-success' if enabled else 'badge-secondary'}">{
                            'Active' if enabled else 'Inactive'
                        }</span>
                    </div>
                    <span class="strategy-timeframe">{strategy.get('timeframe', 'N/A')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.markdown(f"**Description:** {strategy.get('description', 'N/A')}")
                symbols = strategy.get('symbols', [])
                if symbols:
                    symbols_html = " ".join([f'<span class="symbol-tag">{s}</span>' for s in symbols])
                    st.markdown(f"**Symbols:** {', '.join(symbols)}")

            with col2:
                params = strategy.get('parameters', {})
                if params:
                    st.markdown("**Parameters:**")
                    params_str = " | ".join([f"`{k}: {v}`" for k, v in list(params.items())[:3]])
                    st.markdown(params_str)

            with col3:
                if st.button(
                    "Disable" if enabled else "Enable",
                    key=f"toggle_strategy_{idx}_{strategy['file']}",
                    type="primary" if not enabled else "secondary",
                    use_container_width=True
                ):
                    toggle_strategy(config_dir / strategy['file'], not enabled)
                    st.rerun()

            st.markdown("---")


def render_strategy_config():
    """Render strategy configuration editor."""
    config_dir = Path(__file__).parent.parent.parent / "config" / "strategies"
    config_files = list(config_dir.glob("*.yaml")) if config_dir.exists() else []

    if not config_files:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">⚙️</div>
            <h3>No Strategies to Configure</h3>
            <p>Add a new strategy first.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Strategy selector
    selected_file = st.selectbox(
        "Select Strategy to Configure",
        options=config_files,
        format_func=lambda x: x.stem.replace("_", " ").title(),
        key="config_strategy_selector"
    )

    if selected_file:
        try:
            with open(selected_file, "r") as f:
                config = yaml.safe_load(f)

            st.markdown("---")

            # Basic settings section
            st.markdown("### Basic Settings")

            col1, col2 = st.columns(2)

            with col1:
                new_name = st.text_input(
                    "Strategy Name",
                    value=config.get('name', ''),
                    key="config_strategy_name"
                )

                timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
                current_tf = config.get('timeframe', 'M15')
                tf_index = timeframe_options.index(current_tf) if current_tf in timeframe_options else 2

                new_timeframe = st.selectbox(
                    "Timeframe",
                    options=timeframe_options,
                    index=tf_index,
                    key="config_timeframe_select"
                )

            with col2:
                new_enabled = st.toggle(
                    "Strategy Enabled",
                    value=config.get('enabled', False),
                    key="config_enabled_toggle"
                )

                new_symbols = st.text_input(
                    "Symbols (comma-separated)",
                    value=", ".join(config.get('symbols', [])),
                    key="config_symbols_input"
                )

            col3, col4 = st.columns(2)
            with col3:
                new_magic = st.number_input(
                    "Magic Number",
                    value=config.get('magic_number', 123456),
                    step=1,
                    key="config_magic_number"
                )

            st.markdown("---")
            st.markdown("### Strategy Parameters")

            params = config.get('parameters', {})
            new_params = {}

            if params:
                cols = st.columns(3)
                for i, (key, value) in enumerate(params.items()):
                    with cols[i % 3]:
                        if isinstance(value, bool):
                            new_params[key] = st.checkbox(
                                key.replace("_", " ").title(),
                                value=value,
                                key=f"config_param_{key}"
                            )
                        elif isinstance(value, float):
                            new_params[key] = st.number_input(
                                key.replace("_", " ").title(),
                                value=value,
                                format="%.2f",
                                key=f"config_param_{key}"
                            )
                        elif isinstance(value, int):
                            new_params[key] = st.number_input(
                                key.replace("_", " ").title(),
                                value=value,
                                step=1,
                                key=f"config_param_{key}"
                            )
                        else:
                            new_params[key] = st.text_input(
                                key.replace("_", " ").title(),
                                value=str(value),
                                key=f"config_param_{key}"
                            )
            else:
                st.info("No parameters defined for this strategy.")

            st.markdown("---")

            col_save, col_space = st.columns([1, 3])
            with col_save:
                if st.button("Save Configuration", type="primary", use_container_width=True):
                    # Update config
                    config['name'] = new_name
                    config['enabled'] = new_enabled
                    config['timeframe'] = new_timeframe
                    config['symbols'] = [s.strip() for s in new_symbols.split(",")]
                    config['magic_number'] = int(new_magic)
                    config['parameters'] = new_params

                    with open(selected_file, "w") as f:
                        yaml.dump(config, f, default_flow_style=False)

                    st.success("Configuration saved successfully!")
                    st.rerun()

        except Exception as e:
            st.error(f"Error loading configuration: {e}")


def render_add_strategy():
    """Render form to add a new strategy."""
    st.markdown("""
    <div class="info-card">
        <h4>Getting Started</h4>
        <ol>
            <li>Create a Python file in <code>strategies/</code> folder that inherits from <code>StrategyBase</code></li>
            <li>Implement the required methods: <code>initialize()</code>, <code>analyze()</code>, <code>should_close()</code></li>
            <li>Create a YAML configuration file using the form below</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    # Strategy template expander
    with st.expander("View Strategy Template", expanded=False):
        template_code = '''"""
My Custom Strategy
"""
from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
import pandas as pd
from typing import Optional, Dict, Any

class MyStrategy(StrategyBase):
    name = "My Strategy"
    version = "1.0.0"
    description = "My custom trading strategy"

    def initialize(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M15")
        self.enabled = config.get("enabled", True)
        # Load your parameters here

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        # Implement your entry logic here
        # Return TradeSignal for entry, None otherwise
        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        # Implement your exit logic here
        return False
'''
        st.code(template_code, language="python")

    st.markdown("---")
    st.markdown("### Create Configuration")

    col1, col2 = st.columns(2)

    with col1:
        new_name = st.text_input(
            "Strategy Name",
            placeholder="My Strategy",
            key="add_strategy_name"
        )
        new_symbols = st.text_input(
            "Symbols",
            value="XAUUSD",
            key="add_strategy_symbols"
        )

    with col2:
        new_file = st.text_input(
            "File Name (without .yaml)",
            placeholder="my_strategy",
            key="add_strategy_file"
        )
        new_timeframe = st.selectbox(
            "Timeframe",
            ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            index=2,
            key="add_strategy_timeframe"
        )

    st.markdown("---")

    col_create, col_space = st.columns([1, 3])
    with col_create:
        if st.button("Create Strategy", type="primary", use_container_width=True):
            if not new_name or not new_file:
                st.error("Please fill in Strategy Name and File Name.")
            else:
                config = {
                    "name": new_name,
                    "enabled": False,
                    "description": "My custom strategy",
                    "symbols": [s.strip() for s in new_symbols.split(",")],
                    "timeframe": new_timeframe,
                    "magic_number": 123456,
                    "parameters": {
                        "param1": 10,
                        "param2": 2.0,
                    },
                    "risk": {
                        "max_risk_percent": 2.0,
                        "lot_size": 0.01
                    }
                }

                config_dir = Path(__file__).parent.parent.parent / "config" / "strategies"
                config_dir.mkdir(parents=True, exist_ok=True)

                config_path = config_dir / f"{new_file}.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)

                st.success(f"Strategy configuration created: `{new_file}.yaml`")
                st.info(f"Now create `strategies/{new_file}.py` with your strategy implementation.")


def toggle_strategy(config_path: Path, enabled: bool):
    """Toggle strategy enabled/disabled."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        config['enabled'] = enabled

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    except Exception as e:
        st.error(f"Error toggling strategy: {e}")
