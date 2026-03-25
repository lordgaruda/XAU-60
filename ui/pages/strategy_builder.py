"""
Strategy Builder & Deployer - Create, edit, and deploy trading strategies.

Features:
- View all strategies with parameters
- Edit strategy parameters live
- Deploy/undeploy strategies
- Create new strategies from template
- Strategy status monitoring
"""
import streamlit as st
import yaml
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Strategy template for new strategies
STRATEGY_TEMPLATE = '''"""
{name} Strategy
{description}
"""
from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
import pandas as pd
from typing import Optional, Dict, Any
from loguru import logger


class {class_name}(StrategyBase):
    """
    {name} Strategy Implementation.

    {description}
    """

    name = "{name}"
    version = "1.0.0"
    description = "{description}"

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize strategy with configuration.

        Args:
            config: Strategy configuration from YAML
        """
        self.config = config
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M15")
        self.enabled = config.get("enabled", True)

        # Load strategy parameters
        params = config.get("parameters", {{}})
        # TODO: Add your parameter initialization here

        logger.info(f"{{self.name}} initialized on {{self.symbols}}")

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trading signals.

        Args:
            symbol: Trading symbol
            data: OHLCV DataFrame with columns: time, open, high, low, close, volume

        Returns:
            TradeSignal if entry conditions met, None otherwise
        """
        if len(data) < 50:
            return None

        # TODO: Implement your entry logic here
        # Example:
        # if buy_condition:
        #     return TradeSignal(
        #         signal=Signal.BUY,
        #         symbol=symbol,
        #         entry_price=data['close'].iloc[-1],
        #         stop_loss=stop_loss_price,
        #         take_profit=take_profit_price,
        #         confidence=0.8
        #     )

        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """
        Check if an open position should be closed.

        Args:
            position: Current open position
            data: Latest OHLCV data

        Returns:
            True if position should be closed
        """
        # TODO: Implement your exit logic here
        # Example:
        # if exit_condition:
        #     return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get current strategy status.

        Returns:
            Dictionary with strategy status info
        """
        return {{
            "name": self.name,
            "enabled": self.enabled,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            # Add any custom status fields
        }}
'''


CONFIG_TEMPLATE = """# {name} Strategy Configuration
name: "{name}"
enabled: false
description: "{description}"

# Trading settings
symbols:
  - XAUUSD
timeframe: {timeframe}
magic_number: {magic}

# Strategy parameters
parameters:
  param1: 10
  param2: 2.0

# Risk settings
risk:
  max_risk_percent: 2.0
  lot_size: 0.01
  use_dynamic_sizing: false

# Session filter
sessions:
  london_start: "07:00"
  london_end: "16:00"
  ny_start: "13:00"
  ny_end: "22:00"
  trade_london: true
  trade_ny: true
"""


def render_strategy_builder():
    """Render the strategy builder page."""
    st.markdown("""
    <div class="page-header">
        <h1>Strategy Builder</h1>
        <p>Create, configure, and deploy trading strategies</p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "selected_strategy" not in st.session_state:
        st.session_state["selected_strategy"] = None
    if "strategy_logs" not in st.session_state:
        st.session_state["strategy_logs"] = {}
    if "deployed_strategies" not in st.session_state:
        st.session_state["deployed_strategies"] = set()

    # Tabs
    tab_view, tab_edit, tab_create, tab_monitor = st.tabs([
        "View Strategies", "Edit Parameters", "Create New", "Status Monitor"
    ])

    with tab_view:
        render_strategy_list()

    with tab_edit:
        render_strategy_editor()

    with tab_create:
        render_strategy_creator()

    with tab_monitor:
        render_strategy_monitor()


def get_strategies() -> List[Dict[str, Any]]:
    """Load all strategy configurations."""
    strategies = []
    config_dir = Path(__file__).parent.parent.parent / "config" / "strategies"

    if not config_dir.exists():
        return strategies

    for config_file in config_dir.glob("*.yaml"):
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
                if config:
                    config["_file"] = config_file.name
                    config["_path"] = str(config_file)
                    strategies.append(config)
        except Exception as e:
            st.error(f"Error loading {config_file.name}: {e}")

    return strategies


def get_strategy_module(strategy_name: str) -> Optional[str]:
    """Check if strategy Python module exists."""
    strategies_dir = Path(__file__).parent.parent.parent / "strategies"

    # Try to find the Python file
    possible_names = [
        strategy_name.lower().replace(" ", "_"),
        strategy_name.lower().replace(" ", ""),
        strategy_name.replace(" ", "_"),
    ]

    for name in possible_names:
        module_path = strategies_dir / f"{name}.py"
        if module_path.exists():
            return str(module_path)

    return None


def render_strategy_list():
    """Render the list of all strategies."""
    strategies = get_strategies()

    if not strategies:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">📊</div>
            <h3>No Strategies Found</h3>
            <p>Create your first strategy using the "Create New" tab.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Strategy cards
    for idx, strategy in enumerate(strategies):
        enabled = strategy.get("enabled", False)
        deployed = strategy.get("_file", "").replace(".yaml", "") in st.session_state.get("deployed_strategies", set())

        with st.container():
            # Header
            col_name, col_status = st.columns([4, 1])

            with col_name:
                st.markdown(f"### {strategy.get('name', 'Unknown')}")

            with col_status:
                if deployed:
                    st.markdown("""
                    <span style="background: #10b981; color: white; padding: 0.25rem 0.75rem;
                    border-radius: 20px; font-size: 0.75rem; font-weight: 600;">🟢 LIVE</span>
                    """, unsafe_allow_html=True)
                elif enabled:
                    st.markdown("""
                    <span style="background: #f59e0b; color: white; padding: 0.25rem 0.75rem;
                    border-radius: 20px; font-size: 0.75rem; font-weight: 600;">● ENABLED</span>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <span style="background: #64748b; color: white; padding: 0.25rem 0.75rem;
                    border-radius: 20px; font-size: 0.75rem; font-weight: 600;">○ DISABLED</span>
                    """, unsafe_allow_html=True)

            # Details
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**Description:** {strategy.get('description', 'N/A')}")
                symbols = strategy.get("symbols", [])
                st.markdown(f"**Symbols:** {', '.join(symbols) if symbols else 'N/A'}")

            with col2:
                st.markdown(f"**Timeframe:** {strategy.get('timeframe', 'N/A')}")
                st.markdown(f"**Magic Number:** {strategy.get('magic_number', 'N/A')}")

            with col3:
                params = strategy.get("parameters", {})
                if params:
                    params_preview = ", ".join([f"{k}={v}" for k, v in list(params.items())[:3]])
                    st.markdown(f"**Parameters:** {params_preview}...")

            # Action buttons
            col_toggle, col_deploy, col_edit = st.columns(3)

            with col_toggle:
                new_enabled = st.toggle(
                    "Enabled",
                    value=enabled,
                    key=f"enable_{strategy['_file']}"
                )
                if new_enabled != enabled:
                    update_strategy_config(strategy["_path"], {"enabled": new_enabled})
                    st.rerun()

            with col_deploy:
                if deployed:
                    if st.button("⏹️ Undeploy", key=f"undeploy_{strategy['_file']}", use_container_width=True):
                        st.session_state["deployed_strategies"].discard(
                            strategy.get("_file", "").replace(".yaml", "")
                        )
                        st.success(f"Undeployed: {strategy.get('name')}")
                        st.rerun()
                else:
                    if st.button("▶️ Deploy", key=f"deploy_{strategy['_file']}",
                               type="primary", use_container_width=True, disabled=not enabled):
                        st.session_state["deployed_strategies"].add(
                            strategy.get("_file", "").replace(".yaml", "")
                        )
                        st.success(f"Deployed: {strategy.get('name')}")
                        st.rerun()

            with col_edit:
                if st.button("✏️ Edit", key=f"select_{strategy['_file']}", use_container_width=True):
                    st.session_state["selected_strategy"] = strategy["_path"]
                    st.info(f"Selected: {strategy.get('name')} - Go to 'Edit Parameters' tab")

            # Module status
            module_path = get_strategy_module(strategy.get("name", ""))
            if module_path:
                st.markdown(f"<small style='color: #10b981;'>✓ Python module found: {Path(module_path).name}</small>", unsafe_allow_html=True)
            else:
                st.markdown("<small style='color: #f59e0b;'>⚠ No Python module found - strategy won't execute</small>", unsafe_allow_html=True)

            st.markdown("---")


def render_strategy_editor():
    """Render the strategy parameter editor."""
    selected_path = st.session_state.get("selected_strategy")

    if not selected_path or not Path(selected_path).exists():
        # Strategy selector
        strategies = get_strategies()
        if not strategies:
            st.info("No strategies available to edit")
            return

        strategy_names = {s.get("name", s["_file"]): s["_path"] for s in strategies}
        selected_name = st.selectbox(
            "Select Strategy to Edit",
            list(strategy_names.keys()),
            key="editor_strategy_select"
        )

        if selected_name:
            st.session_state["selected_strategy"] = strategy_names[selected_name]
            st.rerun()
        return

    # Load strategy config
    try:
        with open(selected_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        st.error(f"Failed to load strategy: {e}")
        return

    st.markdown(f"### Editing: {config.get('name', 'Unknown')}")
    st.markdown(f"*File: {Path(selected_path).name}*")

    # Change strategy button
    if st.button("← Select Different Strategy", key="change_strategy"):
        st.session_state["selected_strategy"] = None
        st.rerun()

    st.markdown("---")

    # Basic settings
    st.markdown("### Basic Settings")
    col1, col2 = st.columns(2)

    with col1:
        config["name"] = st.text_input(
            "Strategy Name",
            value=config.get("name", ""),
            key="edit_name"
        )

        config["description"] = st.text_area(
            "Description",
            value=config.get("description", ""),
            key="edit_description",
            height=100
        )

    with col2:
        config["enabled"] = st.toggle(
            "Enabled",
            value=config.get("enabled", False),
            key="edit_enabled"
        )

        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        current_tf = config.get("timeframe", "M15")
        tf_idx = timeframes.index(current_tf) if current_tf in timeframes else 2

        config["timeframe"] = st.selectbox(
            "Timeframe",
            timeframes,
            index=tf_idx,
            key="edit_timeframe"
        )

        symbols_str = ", ".join(config.get("symbols", ["XAUUSD"]))
        new_symbols = st.text_input(
            "Symbols (comma-separated)",
            value=symbols_str,
            key="edit_symbols"
        )
        config["symbols"] = [s.strip() for s in new_symbols.split(",") if s.strip()]

    st.markdown("---")

    # Strategy Parameters
    st.markdown("### Strategy Parameters")

    params = config.get("parameters", {})
    new_params = {}

    if params:
        cols = st.columns(3)
        for i, (key, value) in enumerate(params.items()):
            with cols[i % 3]:
                if isinstance(value, bool):
                    new_params[key] = st.checkbox(
                        key.replace("_", " ").title(),
                        value=value,
                        key=f"edit_param_{key}"
                    )
                elif isinstance(value, float):
                    new_params[key] = st.number_input(
                        key.replace("_", " ").title(),
                        value=value,
                        format="%.4f",
                        key=f"edit_param_{key}"
                    )
                elif isinstance(value, int):
                    new_params[key] = st.number_input(
                        key.replace("_", " ").title(),
                        value=value,
                        step=1,
                        key=f"edit_param_{key}"
                    )
                else:
                    new_params[key] = st.text_input(
                        key.replace("_", " ").title(),
                        value=str(value),
                        key=f"edit_param_{key}"
                    )

        config["parameters"] = new_params

        # Add new parameter
        st.markdown("#### Add New Parameter")
        col_name, col_type, col_value, col_add = st.columns([2, 1, 2, 1])

        with col_name:
            new_param_name = st.text_input("Parameter Name", key="new_param_name", placeholder="my_parameter")
        with col_type:
            new_param_type = st.selectbox("Type", ["int", "float", "bool", "str"], key="new_param_type")
        with col_value:
            new_param_value = st.text_input("Default Value", key="new_param_value", placeholder="10")
        with col_add:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Add", key="add_param_btn", use_container_width=True):
                if new_param_name and new_param_value:
                    # Convert value to correct type
                    try:
                        if new_param_type == "int":
                            config["parameters"][new_param_name] = int(new_param_value)
                        elif new_param_type == "float":
                            config["parameters"][new_param_name] = float(new_param_value)
                        elif new_param_type == "bool":
                            config["parameters"][new_param_name] = new_param_value.lower() in ["true", "1", "yes"]
                        else:
                            config["parameters"][new_param_name] = new_param_value
                        st.success(f"Added parameter: {new_param_name}")
                    except ValueError as e:
                        st.error(f"Invalid value: {e}")
    else:
        st.info("No parameters defined. Add parameters below.")

    st.markdown("---")

    # Risk settings
    st.markdown("### Risk Settings")
    risk = config.get("risk", {})

    col1, col2 = st.columns(2)
    with col1:
        risk["max_risk_percent"] = st.slider(
            "Max Risk Per Trade (%)",
            min_value=0.1,
            max_value=10.0,
            value=risk.get("max_risk_percent", 2.0),
            step=0.1,
            key="edit_risk_percent"
        )

        risk["lot_size"] = st.number_input(
            "Fixed Lot Size",
            value=risk.get("lot_size", 0.01),
            step=0.01,
            format="%.2f",
            key="edit_lot_size"
        )

    with col2:
        risk["use_dynamic_sizing"] = st.toggle(
            "Use Dynamic Position Sizing",
            value=risk.get("use_dynamic_sizing", False),
            key="edit_dynamic_sizing"
        )

    config["risk"] = risk

    st.markdown("---")

    # Save button
    col_save, col_reset = st.columns(2)

    with col_save:
        if st.button("💾 Save Changes", type="primary", use_container_width=True, key="save_strategy"):
            save_strategy_config(selected_path, config)
            st.success("Strategy saved successfully!")
            st.rerun()

    with col_reset:
        if st.button("↩️ Discard Changes", use_container_width=True, key="reset_strategy"):
            st.rerun()


def render_strategy_creator():
    """Render the strategy creation form."""
    st.markdown("### Create New Strategy")

    st.markdown("""
    <div class="info-card">
        <h4>Strategy Creation Guide</h4>
        <ol>
            <li>Fill in the strategy details below</li>
            <li>A YAML configuration file will be created</li>
            <li>A Python strategy template will be generated</li>
            <li>Implement your trading logic in the Python file</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    with st.form("create_strategy_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Strategy Name *",
                placeholder="My Strategy",
                help="A descriptive name for your strategy"
            )

            description = st.text_area(
                "Description",
                placeholder="Brief description of the strategy logic...",
                height=100
            )

            file_name = st.text_input(
                "File Name *",
                placeholder="my_strategy",
                help="Used for Python and YAML file names (no extension)"
            )

        with col2:
            timeframe = st.selectbox(
                "Primary Timeframe",
                ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
                index=2
            )

            symbols = st.text_input(
                "Symbols",
                value="XAUUSD",
                help="Comma-separated list of trading symbols"
            )

            magic_number = st.number_input(
                "Magic Number",
                value=100000 + int(datetime.now().timestamp()) % 100000,
                step=1,
                help="Unique identifier for this strategy's trades"
            )

        submitted = st.form_submit_button("Create Strategy", type="primary", use_container_width=True)

        if submitted:
            if not name or not file_name:
                st.error("Please fill in required fields")
            else:
                create_new_strategy(
                    name=name,
                    file_name=file_name,
                    description=description,
                    timeframe=timeframe,
                    symbols=[s.strip() for s in symbols.split(",")],
                    magic_number=int(magic_number)
                )

    # Code editor section
    st.markdown("---")
    st.markdown("### Strategy Code Editor")

    strategies_dir = Path(__file__).parent.parent.parent / "strategies"
    strategy_files = list(strategies_dir.glob("*.py"))

    if strategy_files:
        file_names = [f.name for f in strategy_files if not f.name.startswith("__")]
        selected_file = st.selectbox(
            "Select strategy file to edit",
            file_names,
            key="code_editor_file"
        )

        if selected_file:
            file_path = strategies_dir / selected_file

            with open(file_path, "r") as f:
                code = f.read()

            new_code = st.text_area(
                "Strategy Code",
                value=code,
                height=400,
                key="strategy_code_editor"
            )

            if st.button("Save Code", type="primary", key="save_code_btn"):
                try:
                    # Basic syntax check
                    compile(new_code, selected_file, 'exec')

                    with open(file_path, "w") as f:
                        f.write(new_code)

                    st.success(f"Saved: {selected_file}")
                except SyntaxError as e:
                    st.error(f"Syntax error: {e}")
    else:
        st.info("No strategy files found. Create a new strategy to get started.")


def render_strategy_monitor():
    """Render the strategy status monitor."""
    st.markdown("### Strategy Status Monitor")

    deployed = st.session_state.get("deployed_strategies", set())

    if not deployed:
        st.info("No strategies are currently deployed. Deploy a strategy from the 'View Strategies' tab.")
        return

    strategies = get_strategies()
    deployed_strategies = [s for s in strategies if s.get("_file", "").replace(".yaml", "") in deployed]

    for strategy in deployed_strategies:
        name = strategy.get("name", "Unknown")

        with st.expander(f"📊 {name}", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                # Last signal
                st.markdown("**Last Signal**")
                # This would come from actual strategy execution
                last_signal = st.session_state.get(f"last_signal_{name}", "NONE")
                signal_time = st.session_state.get(f"signal_time_{name}", "N/A")

                if last_signal == "BUY":
                    st.markdown(f"<span style='color: #10b981; font-size: 1.2rem;'>▲ BUY</span>", unsafe_allow_html=True)
                elif last_signal == "SELL":
                    st.markdown(f"<span style='color: #ef4444; font-size: 1.2rem;'>▼ SELL</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: #64748b; font-size: 1.2rem;'>— NONE</span>", unsafe_allow_html=True)

                st.caption(f"Time: {signal_time}")

            with col2:
                # Today's stats
                st.markdown("**Today's Stats**")
                trades_today = st.session_state.get(f"trades_today_{name}", 0)
                wins_today = st.session_state.get(f"wins_today_{name}", 0)
                profit_today = st.session_state.get(f"profit_today_{name}", 0.0)

                st.metric("Trades", trades_today)
                win_rate = (wins_today / trades_today * 100) if trades_today > 0 else 0
                st.metric("Win Rate", f"{win_rate:.1f}%")

            with col3:
                # P&L
                st.markdown("**Performance**")
                st.metric("Today's P&L", f"${profit_today:+,.2f}")

            # Log output
            st.markdown("**Recent Log**")

            logs = st.session_state.get(f"strategy_logs_{name}", [
                f"[{datetime.now().strftime('%H:%M:%S')}] Strategy {name} initialized",
                f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for market data...",
            ])

            log_container = st.container()
            with log_container:
                for log in logs[-10:]:  # Last 10 logs
                    st.text(log)

            # Control buttons
            col_pause, col_stop = st.columns(2)

            with col_pause:
                if st.button("⏸️ Pause", key=f"pause_{name}", use_container_width=True):
                    st.warning(f"Paused: {name}")

            with col_stop:
                if st.button("⏹️ Stop", key=f"stop_{name}", use_container_width=True):
                    st.session_state["deployed_strategies"].discard(
                        strategy.get("_file", "").replace(".yaml", "")
                    )
                    st.info(f"Stopped: {name}")
                    st.rerun()


def update_strategy_config(config_path: str, updates: Dict[str, Any]) -> bool:
    """Update specific fields in strategy config."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        config.update(updates)

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        return True
    except Exception as e:
        st.error(f"Failed to update config: {e}")
        return False


def save_strategy_config(config_path: str, config: Dict[str, Any]) -> bool:
    """Save complete strategy config."""
    try:
        # Remove internal fields
        clean_config = {k: v for k, v in config.items() if not k.startswith("_")}

        with open(config_path, "w") as f:
            yaml.dump(clean_config, f, default_flow_style=False)

        return True
    except Exception as e:
        st.error(f"Failed to save config: {e}")
        return False


def create_new_strategy(
    name: str,
    file_name: str,
    description: str,
    timeframe: str,
    symbols: List[str],
    magic_number: int
):
    """Create a new strategy with Python module and YAML config."""
    # Paths
    base_dir = Path(__file__).parent.parent.parent
    config_dir = base_dir / "config" / "strategies"
    strategies_dir = base_dir / "strategies"

    config_dir.mkdir(parents=True, exist_ok=True)
    strategies_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / f"{file_name}.yaml"
    module_path = strategies_dir / f"{file_name}.py"

    # Check if files already exist
    if config_path.exists():
        st.error(f"Config file already exists: {file_name}.yaml")
        return

    if module_path.exists():
        st.error(f"Python module already exists: {file_name}.py")
        return

    # Generate class name from file name
    class_name = "".join(word.title() for word in file_name.split("_"))

    # Create YAML config
    config_content = CONFIG_TEMPLATE.format(
        name=name,
        description=description or "Custom trading strategy",
        timeframe=timeframe,
        magic=magic_number
    )

    # Update symbols in config
    config = yaml.safe_load(config_content)
    config["symbols"] = symbols

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        # Create Python module
        module_content = STRATEGY_TEMPLATE.format(
            name=name,
            description=description or "Custom trading strategy",
            class_name=class_name
        )

        with open(module_path, "w") as f:
            f.write(module_content)

        st.success(f"""
        Strategy created successfully!

        - Config: `config/strategies/{file_name}.yaml`
        - Module: `strategies/{file_name}.py`

        Next steps:
        1. Open `strategies/{file_name}.py`
        2. Implement your entry logic in `analyze()`
        3. Implement your exit logic in `should_close()`
        4. Enable and deploy the strategy
        """)

    except Exception as e:
        st.error(f"Failed to create strategy: {e}")
        # Cleanup on failure
        if config_path.exists():
            os.remove(config_path)
        if module_path.exists():
            os.remove(module_path)
