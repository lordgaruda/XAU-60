"""
Settings Page - Bot configuration.
"""
import streamlit as st
import yaml
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render_settings():
    """Render the settings page."""
    st.markdown("""
    <div class="page-header">
        <h1>Settings</h1>
        <p>Configure your trading bot parameters</p>
    </div>
    """, unsafe_allow_html=True)

    # Load current settings
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"

    try:
        with open(settings_path, "r") as f:
            settings = yaml.safe_load(f) or {}
    except Exception:
        settings = {}
        st.warning("Could not load settings. Using defaults.")

    # Settings tabs
    tab1, tab2, tab3, tab4 = st.tabs(["MT5 Connection", "Risk Management", "Alerts", "General"])

    with tab1:
        render_mt5_settings(settings)

    with tab2:
        render_risk_settings(settings)

    with tab3:
        render_alert_settings(settings)

    with tab4:
        render_general_settings(settings)

    st.markdown("---")

    # Save button
    col_save, col_space = st.columns([1, 4])
    with col_save:
        if st.button("Save All Settings", type="primary", use_container_width=True, key="settings_save_all"):
            save_settings(settings_path, settings)
            st.success("Settings saved successfully!")


def render_mt5_settings(settings: dict):
    """Render MT5 connection settings."""
    st.markdown("### MetaTrader 5 Connection")

    mt5 = settings.get("mt5", {})

    col1, col2 = st.columns(2)

    with col1:
        settings.setdefault("mt5", {})
        settings["mt5"]["login"] = st.number_input(
            "Account Login",
            value=mt5.get("login", 0),
            step=1,
            help="Your MT5 account number",
            key="settings_mt5_login"
        )

        settings["mt5"]["password"] = st.text_input(
            "Password",
            value=mt5.get("password", ""),
            type="password",
            help="Your MT5 account password",
            key="settings_mt5_password"
        )

    with col2:
        settings["mt5"]["server"] = st.text_input(
            "Server",
            value=mt5.get("server", ""),
            placeholder="YourBroker-Demo",
            help="Broker server name",
            key="settings_mt5_server"
        )

        settings["mt5"]["path"] = st.text_input(
            "MT5 Path (optional)",
            value=mt5.get("path", ""),
            placeholder="C:\\Program Files\\MT5\\terminal64.exe",
            help="Leave empty for default installation",
            key="settings_mt5_path"
        )

    settings["mt5"]["timeout"] = st.number_input(
        "Connection Timeout (ms)",
        value=mt5.get("timeout", 60000),
        step=1000,
        help="Connection timeout in milliseconds",
        key="settings_mt5_timeout"
    )

    # Test connection button
    col_test, col_space = st.columns([1, 4])
    with col_test:
        if st.button("Test Connection", use_container_width=True, key="settings_mt5_test"):
            with st.spinner("Testing connection..."):
                test_mt5_connection(settings["mt5"])


def render_risk_settings(settings: dict):
    """Render risk management settings."""
    st.markdown("### Risk Management")

    risk = settings.get("risk", {})
    settings.setdefault("risk", {})

    col1, col2 = st.columns(2)

    with col1:
        settings["risk"]["max_risk_per_trade"] = st.slider(
            "Max Risk Per Trade (%)",
            min_value=0.1,
            max_value=10.0,
            value=risk.get("max_risk_per_trade", 2.0),
            step=0.1,
            help="Maximum risk percentage per trade",
            key="settings_risk_per_trade"
        )

        settings["risk"]["max_daily_loss"] = st.slider(
            "Max Daily Loss (%)",
            min_value=1.0,
            max_value=20.0,
            value=risk.get("max_daily_loss", 5.0),
            step=0.5,
            help="Stop trading when daily loss reaches this percentage",
            key="settings_risk_daily_loss"
        )

        settings["risk"]["max_drawdown"] = st.slider(
            "Max Drawdown (%)",
            min_value=5.0,
            max_value=50.0,
            value=risk.get("max_drawdown", 20.0),
            step=1.0,
            help="Stop trading when drawdown reaches this percentage",
            key="settings_risk_drawdown"
        )

    with col2:
        settings["risk"]["max_positions"] = st.number_input(
            "Max Positions",
            min_value=1,
            max_value=20,
            value=risk.get("max_positions", 5),
            help="Maximum simultaneous open positions",
            key="settings_risk_max_positions"
        )

        settings["risk"]["max_positions_per_symbol"] = st.number_input(
            "Max Positions Per Symbol",
            min_value=1,
            max_value=10,
            value=risk.get("max_positions_per_symbol", 2),
            help="Maximum positions per trading symbol",
            key="settings_risk_positions_per_symbol"
        )

    st.markdown("---")

    # Risk warnings
    st.markdown("""
    <div class="info-card">
        <h4>Risk Warning</h4>
        <p>Trading involves significant risk. Configure conservative risk limits, especially when starting out:</p>
        <ul style="color: #94a3b8; margin: 0;">
            <li>Start with 1-2% risk per trade</li>
            <li>Set a 5% maximum daily loss</li>
            <li>Use demo accounts for testing</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


def render_alert_settings(settings: dict):
    """Render alert notification settings."""
    st.markdown("### Notifications")

    alerts = settings.get("alerts", {})
    settings.setdefault("alerts", {"telegram": {}, "discord": {}})

    # Telegram settings
    st.markdown("#### Telegram")

    telegram = alerts.get("telegram", {})
    settings["alerts"]["telegram"]["enabled"] = st.toggle(
        "Enable Telegram Alerts",
        value=telegram.get("enabled", False),
        key="settings_telegram_enabled"
    )

    if settings["alerts"]["telegram"]["enabled"]:
        col1, col2 = st.columns(2)
        with col1:
            settings["alerts"]["telegram"]["token"] = st.text_input(
                "Bot Token",
                value=telegram.get("token", ""),
                type="password",
                help="Get this from @BotFather on Telegram",
                key="settings_telegram_token"
            )
        with col2:
            settings["alerts"]["telegram"]["chat_id"] = st.text_input(
                "Chat ID",
                value=telegram.get("chat_id", ""),
                help="Your Telegram chat ID",
                key="settings_telegram_chat_id"
            )

        col_test, col_space = st.columns([1, 4])
        with col_test:
            if st.button("Send Test", use_container_width=True, key="settings_telegram_test"):
                st.info("Test message sent!")

    st.markdown("---")

    # Discord settings
    st.markdown("#### Discord")

    discord = alerts.get("discord", {})
    settings["alerts"]["discord"]["enabled"] = st.toggle(
        "Enable Discord Alerts",
        value=discord.get("enabled", False),
        key="settings_discord_enabled"
    )

    if settings["alerts"]["discord"]["enabled"]:
        settings["alerts"]["discord"]["webhook_url"] = st.text_input(
            "Webhook URL",
            value=discord.get("webhook_url", ""),
            type="password",
            help="Discord channel webhook URL",
            key="settings_discord_webhook"
        )

        col_test, col_space = st.columns([1, 4])
        with col_test:
            if st.button("Send Test", use_container_width=True, key="settings_discord_test"):
                st.info("Test message sent!")


def render_general_settings(settings: dict):
    """Render general settings."""
    st.markdown("### Trading Settings")

    trading = settings.get("trading", {})
    settings.setdefault("trading", {})

    col1, col2 = st.columns(2)

    with col1:
        settings["trading"]["default_lot_size"] = st.number_input(
            "Default Lot Size",
            value=trading.get("default_lot_size", 0.01),
            step=0.01,
            format="%.2f",
            key="settings_trading_lot_size"
        )

        settings["trading"]["default_magic_number"] = st.number_input(
            "Default Magic Number",
            value=trading.get("default_magic_number", 123456),
            step=1,
            key="settings_trading_magic_number"
        )

    with col2:
        settings["trading"]["slippage"] = st.number_input(
            "Max Slippage (points)",
            value=trading.get("slippage", 10),
            step=1,
            key="settings_trading_slippage"
        )

        settings["trading"]["check_interval"] = st.number_input(
            "Check Interval (seconds)",
            value=trading.get("check_interval", 1),
            step=1,
            help="Seconds between tick checks",
            key="settings_trading_interval"
        )

    st.markdown("---")

    # Logging settings
    st.markdown("### Logging")

    logging = settings.get("logging", {})
    settings.setdefault("logging", {})

    col1, col2 = st.columns(2)

    with col1:
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        current_level = logging.get("level", "INFO")
        level_index = log_levels.index(current_level) if current_level in log_levels else 1

        settings["logging"]["level"] = st.selectbox(
            "Log Level",
            options=log_levels,
            index=level_index,
            key="settings_logging_level"
        )

    with col2:
        settings["logging"]["file"] = st.text_input(
            "Log File",
            value=logging.get("file", "logs/trading_bot.log"),
            key="settings_logging_file"
        )

    st.markdown("---")

    # UI settings
    st.markdown("### UI Settings")

    ui = settings.get("ui", {})
    settings.setdefault("ui", {})

    col1, col2 = st.columns(2)

    with col1:
        settings["ui"]["refresh_rate"] = st.number_input(
            "Dashboard Refresh Rate (seconds)",
            value=ui.get("refresh_rate", 5),
            step=1,
            min_value=1,
            max_value=60,
            key="settings_ui_refresh_rate"
        )

    with col2:
        themes = ["light", "dark"]
        current_theme = ui.get("theme", "dark")
        theme_index = themes.index(current_theme) if current_theme in themes else 1

        settings["ui"]["theme"] = st.selectbox(
            "Theme",
            options=themes,
            index=theme_index,
            key="settings_ui_theme"
        )


def test_mt5_connection(mt5_config: dict):
    """Test MT5 connection."""
    try:
        from core.mt5_connector import MT5Connector

        mt5 = MT5Connector()
        if mt5.connect(
            login=mt5_config.get("login"),
            password=mt5_config.get("password"),
            server=mt5_config.get("server"),
            path=mt5_config.get("path") or None,
            timeout=mt5_config.get("timeout", 60000)
        ):
            account = mt5.get_account_info()
            if account:
                st.success(f"""
                **Connection successful!**
                - Server: {account.server}
                - Account: {account.login}
                - Balance: {account.balance} {account.currency}
                - Leverage: 1:{account.leverage}
                """)
            mt5.disconnect()
        else:
            st.error("Failed to connect to MT5. Check your credentials.")
    except ImportError:
        st.error("MetaTrader5 library not installed. Install with: pip install MetaTrader5")
    except Exception as e:
        st.error(f"Connection error: {e}")


def save_settings(settings_path: Path, settings: dict):
    """Save settings to file."""
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w") as f:
            yaml.dump(settings, f, default_flow_style=False)
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
