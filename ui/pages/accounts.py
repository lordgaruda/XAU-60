"""
Accounts Page - MT5 multi-account management.

Features:
- Add/remove/edit trading accounts
- Secure encrypted credential storage
- Connection management
- Account switching
"""
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from core.account_manager import (
        get_account_manager, AccountManager, AccountType,
        ConnectionStatus, MT5Account
    )
except ImportError as e:
    st.error(f"Import error: {e}")


def render_accounts():
    """Render the accounts management page."""
    st.markdown("""
    <div class="page-header">
        <h1>Account Management</h1>
        <p>Manage your MT5 trading accounts with secure encrypted storage</p>
    </div>
    """, unsafe_allow_html=True)

    manager = get_account_manager()

    # Tabs for different sections
    tab_accounts, tab_add, tab_connection = st.tabs([
        "My Accounts", "Add Account", "Connection Monitor"
    ])

    with tab_accounts:
        render_accounts_list(manager)

    with tab_add:
        render_add_account(manager)

    with tab_connection:
        render_connection_monitor(manager)


def render_accounts_list(manager: AccountManager):
    """Render the list of saved accounts."""
    accounts = manager.list_accounts()
    active_account = manager.get_active_account()

    if not accounts:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">💼</div>
            <h3>No Accounts Found</h3>
            <p>Add your first MT5 trading account to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Account cards
    for account in accounts:
        is_active = active_account and account.id == active_account.id
        status = manager.get_connection_status(account.id)

        # Status color
        if status == ConnectionStatus.CONNECTED:
            status_color = "#10b981"
            status_text = "Connected"
            status_icon = "●"
        elif status in [ConnectionStatus.CONNECTING, ConnectionStatus.RECONNECTING]:
            status_color = "#f59e0b"
            status_text = status.value.title()
            status_icon = "○"
        else:
            status_color = "#ef4444"
            status_text = "Disconnected"
            status_icon = "●"

        # Account type badge
        type_badge = "🟢 DEMO" if account.account_type == AccountType.DEMO else "🔴 LIVE"

        with st.container():
            st.markdown(f"""
            <div class="strategy-card {'enabled' if is_active else 'disabled'}">
                <div class="strategy-header">
                    <div class="strategy-title">
                        <span class="strategy-name">{account.name}</span>
                        <span class="strategy-badge {'badge-success' if is_active else 'badge-secondary'}">
                            {'ACTIVE' if is_active else 'INACTIVE'}
                        </span>
                        <span style="font-size: 0.8rem;">{type_badge}</span>
                    </div>
                    <span style="color: {status_color};">{status_icon} {status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

            with col1:
                st.markdown(f"**Login:** {account.login}")
                st.markdown(f"**Server:** {account.server}")

            with col2:
                if account.last_connected:
                    last_conn = datetime.fromisoformat(account.last_connected)
                    st.markdown(f"**Last Connected:** {last_conn.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.markdown("**Last Connected:** Never")

                created = datetime.fromisoformat(account.created_at)
                st.markdown(f"**Added:** {created.strftime('%Y-%m-%d')}")

            with col3:
                # Connect/Disconnect button
                if status == ConnectionStatus.CONNECTED:
                    if st.button("Disconnect", key=f"disconnect_{account.id}", use_container_width=True):
                        manager.disconnect(account.id)
                        st.rerun()
                else:
                    if st.button("Connect", key=f"connect_{account.id}", type="primary", use_container_width=True):
                        with st.spinner("Connecting..."):
                            if manager.connect(account.id):
                                st.success("Connected!")
                                st.rerun()
                            else:
                                st.error("Connection failed")

            with col4:
                # Set Active / Remove
                if not is_active:
                    if st.button("Set Active", key=f"activate_{account.id}", use_container_width=True):
                        manager.switch_account(account.id, connect=False)
                        st.rerun()

                if st.button("🗑️ Remove", key=f"remove_{account.id}", use_container_width=True):
                    if st.session_state.get(f"confirm_remove_{account.id}"):
                        manager.remove_account(account.id)
                        st.success(f"Removed account: {account.name}")
                        st.session_state[f"confirm_remove_{account.id}"] = False
                        st.rerun()
                    else:
                        st.session_state[f"confirm_remove_{account.id}"] = True
                        st.warning("Click again to confirm removal")

            # Show account info if connected
            if status == ConnectionStatus.CONNECTED:
                account_info = manager.get_account_info(account.id, refresh=True)
                if account_info:
                    st.markdown("---")
                    info_cols = st.columns(6)
                    with info_cols[0]:
                        st.metric("Balance", f"{account_info.balance:,.2f}")
                    with info_cols[1]:
                        st.metric("Equity", f"{account_info.equity:,.2f}")
                    with info_cols[2]:
                        st.metric("Margin", f"{account_info.margin:,.2f}")
                    with info_cols[3]:
                        st.metric("Free Margin", f"{account_info.free_margin:,.2f}")
                    with info_cols[4]:
                        st.metric("Profit", f"{account_info.profit:+,.2f}")
                    with info_cols[5]:
                        st.metric("Leverage", f"1:{account_info.leverage}")

            st.markdown("---")


def render_add_account(manager: AccountManager):
    """Render the add account form."""
    st.markdown("### Add New Account")

    st.markdown("""
    <div class="info-card">
        <h4>Security Notice</h4>
        <p>Your credentials are stored locally with AES-256 encryption (Fernet).
        The encryption key is stored separately and can be backed up for recovery.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("add_account_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Account Name *",
                placeholder="My Trading Account",
                help="A friendly name for this account"
            )

            login = st.number_input(
                "Login Number *",
                min_value=1,
                step=1,
                help="Your MT5 account number"
            )

            password = st.text_input(
                "Password *",
                type="password",
                help="Your MT5 account password"
            )

        with col2:
            server = st.text_input(
                "Server *",
                placeholder="YourBroker-Demo",
                help="Broker server name (e.g., ICMarkets-Demo)"
            )

            account_type = st.selectbox(
                "Account Type",
                ["Demo", "Live"],
                help="Demo accounts are for testing, Live accounts trade real money"
            )

            path = st.text_input(
                "MT5 Path (Optional)",
                placeholder="C:\\Program Files\\MT5\\terminal64.exe",
                help="Path to MT5 terminal (leave empty for default)"
            )

        submitted = st.form_submit_button("Add Account", type="primary", use_container_width=True)

        if submitted:
            if not name or not login or not password or not server:
                st.error("Please fill in all required fields")
            else:
                try:
                    acc_type = AccountType.DEMO if account_type == "Demo" else AccountType.LIVE

                    account = manager.add_account(
                        name=name,
                        login=int(login),
                        password=password,
                        server=server,
                        account_type=acc_type,
                        path=path if path else None
                    )

                    st.success(f"Account added: {account.name}")

                    # Ask if user wants to connect
                    if st.button("Connect Now", key="connect_new_account"):
                        with st.spinner("Connecting..."):
                            if manager.connect(account.id):
                                st.success("Connected successfully!")
                            else:
                                st.error("Connection failed. Check your credentials.")

                    st.rerun()

                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Failed to add account: {e}")


def render_connection_monitor(manager: AccountManager):
    """Render connection monitoring panel."""
    st.markdown("### Connection Monitor")

    # Health monitoring controls
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("""
        Connection health monitoring automatically:
        - Pings MT5 terminal every 30 seconds
        - Auto-reconnects on disconnect
        - Updates account info every 5 seconds
        """)

    with col2:
        if st.button("Start Monitoring", use_container_width=True, key="start_monitor"):
            manager.start_health_monitoring()
            st.success("Health monitoring started")

        if st.button("Stop Monitoring", use_container_width=True, key="stop_monitor"):
            manager.stop_health_monitoring()
            st.info("Health monitoring stopped")

    st.markdown("---")

    # Current status
    st.markdown("### Account Status")

    all_info = manager.get_all_account_info()

    if not all_info:
        st.info("No accounts configured")
        return

    # Status table
    data = []
    for account_id, info in all_info.items():
        account = info["account"]
        status = info["connection_status"]
        is_active = info["is_active"]
        last_ping = info["last_ping"]

        # Parse last ping time
        if last_ping:
            try:
                ping_time = datetime.fromisoformat(last_ping)
                ping_str = ping_time.strftime("%H:%M:%S")
            except Exception:
                ping_str = "N/A"
        else:
            ping_str = "N/A"

        # Account info summary
        acc_info = info["account_info"]
        balance = f"${acc_info['balance']:,.2f}" if acc_info else "N/A"
        equity = f"${acc_info['equity']:,.2f}" if acc_info else "N/A"

        data.append({
            "Account": account["name"],
            "Login": account["login"],
            "Server": account["server"],
            "Type": account["account_type"].upper(),
            "Status": status.upper(),
            "Active": "✓" if is_active else "",
            "Balance": balance,
            "Equity": equity,
            "Last Ping": ping_str
        })

    import pandas as pd
    df = pd.DataFrame(data)

    # Color code status
    def highlight_status(val):
        if val == "CONNECTED":
            return 'color: #10b981'
        elif val in ["CONNECTING", "RECONNECTING"]:
            return 'color: #f59e0b'
        else:
            return 'color: #ef4444'

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Refresh button
    if st.button("🔄 Refresh Status", use_container_width=True, key="refresh_status"):
        st.rerun()

    # Connection log
    st.markdown("---")
    st.markdown("### Connection Log")

    # Get recent connection events (would need to implement logging in account manager)
    st.info("Connection log will show recent connection events here.")
