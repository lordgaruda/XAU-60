"""
MT5 Multi-Account Manager with Encrypted Storage.

This module provides secure storage and management of multiple MT5 trading accounts
using Fernet symmetric encryption for credential protection.
"""
import os
import json
import threading
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from loguru import logger


class AccountType(Enum):
    """Account type enumeration."""
    DEMO = "demo"
    LIVE = "live"


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class MT5Account:
    """
    Represents an MT5 trading account.

    Attributes:
        id: Unique account identifier
        name: Display name for the account
        login: MT5 account login number
        password: Account password (stored encrypted)
        server: Broker server name
        account_type: Demo or Live account
        path: Optional path to MT5 terminal executable
        enabled: Whether account is enabled for trading
        created_at: Account creation timestamp
        last_connected: Last successful connection timestamp
    """
    id: str
    name: str
    login: int
    password: str  # Stored encrypted on disk, decrypted in memory
    server: str
    account_type: AccountType = AccountType.DEMO
    path: Optional[str] = None
    enabled: bool = True
    created_at: str = ""
    last_connected: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if isinstance(self.account_type, str):
            self.account_type = AccountType(self.account_type)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['account_type'] = self.account_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MT5Account':
        """Create from dictionary."""
        if 'account_type' in data and isinstance(data['account_type'], str):
            data['account_type'] = AccountType(data['account_type'])
        return cls(**data)


@dataclass
class AccountInfo:
    """
    Live account information from MT5.

    Attributes:
        login: Account login number
        balance: Account balance
        equity: Account equity
        margin: Used margin
        free_margin: Available margin
        margin_level: Margin level percentage
        profit: Floating profit/loss
        currency: Account currency
        leverage: Account leverage
        server: Connected server
        company: Broker company name
        trade_allowed: Whether trading is allowed
        connected: Connection status
    """
    login: int = 0
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    currency: str = "USD"
    leverage: int = 100
    server: str = ""
    company: str = ""
    trade_allowed: bool = False
    connected: bool = False


class EncryptionManager:
    """
    Manages encryption/decryption of sensitive data using Fernet.

    Uses PBKDF2 key derivation from a master password stored in environment
    or derived from machine-specific data.
    """

    def __init__(self, key_file: Optional[Path] = None):
        """
        Initialize encryption manager.

        Args:
            key_file: Optional path to key file. If not provided,
                     uses default location.
        """
        self.key_file = key_file or Path(__file__).parent.parent / "config" / ".encryption_key"
        self._fernet: Optional[Fernet] = None
        self._initialize_encryption()

    def _initialize_encryption(self) -> None:
        """Initialize or load encryption key."""
        if self.key_file.exists():
            # Load existing key
            try:
                with open(self.key_file, "rb") as f:
                    key = f.read()
                self._fernet = Fernet(key)
                logger.debug("Loaded existing encryption key")
            except Exception as e:
                logger.error(f"Failed to load encryption key: {e}")
                self._generate_new_key()
        else:
            self._generate_new_key()

    def _generate_new_key(self) -> None:
        """Generate a new encryption key."""
        # Use environment variable or generate random key
        master_password = os.environ.get("XAU60_MASTER_KEY", "")

        if master_password:
            # Derive key from master password
            salt = b"xau60_trading_bot_salt_v1"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        else:
            # Generate random key
            key = Fernet.generate_key()

        # Save key to file
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.key_file, "wb") as f:
            f.write(key)

        # Restrict file permissions (Unix-like systems)
        try:
            os.chmod(self.key_file, 0o600)
        except Exception:
            pass

        self._fernet = Fernet(key)
        logger.info("Generated new encryption key")

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: Plain text to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted plain text
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.decrypt(encrypted_data.encode()).decode()


class AccountManager:
    """
    Manages multiple MT5 trading accounts with encrypted storage.

    Provides functionality for:
    - Adding, removing, and switching between accounts
    - Secure credential storage with Fernet encryption
    - Connection health monitoring with auto-reconnect
    - Account info caching and refresh

    Example:
        >>> manager = AccountManager()
        >>> manager.add_account("Main", 12345678, "password", "Broker-Server")
        >>> manager.switch_account("Main")
        >>> info = manager.get_account_info()
    """

    def __init__(
        self,
        accounts_file: Optional[Path] = None,
        ping_interval: int = 30,
        auto_reconnect: bool = True
    ):
        """
        Initialize account manager.

        Args:
            accounts_file: Path to encrypted accounts file
            ping_interval: Seconds between connection health checks
            auto_reconnect: Whether to auto-reconnect on disconnect
        """
        self.accounts_file = accounts_file or Path(__file__).parent.parent / "config" / "accounts.enc"
        self.ping_interval = ping_interval
        self.auto_reconnect = auto_reconnect

        # Encryption manager
        self._encryption = EncryptionManager()

        # Account storage
        self._accounts: Dict[str, MT5Account] = {}
        self._active_account_id: Optional[str] = None

        # Connection state
        self._connectors: Dict[str, Any] = {}  # MT5Connector instances per account
        self._connection_status: Dict[str, ConnectionStatus] = {}
        self._account_info_cache: Dict[str, AccountInfo] = {}
        self._last_ping: Dict[str, datetime] = {}

        # Health monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        self._status_callbacks: List[Callable[[str, ConnectionStatus], None]] = []

        # Lock for thread safety
        self._lock = threading.RLock()

        # Load existing accounts
        self._load_accounts()

        logger.info(f"AccountManager initialized with {len(self._accounts)} accounts")

    def _load_accounts(self) -> None:
        """Load accounts from encrypted file."""
        if not self.accounts_file.exists():
            logger.info("No existing accounts file found")
            return

        try:
            with open(self.accounts_file, "r") as f:
                encrypted_data = f.read()

            if not encrypted_data.strip():
                return

            decrypted_data = self._encryption.decrypt(encrypted_data)
            data = json.loads(decrypted_data)

            for account_data in data.get("accounts", []):
                account = MT5Account.from_dict(account_data)
                self._accounts[account.id] = account
                self._connection_status[account.id] = ConnectionStatus.DISCONNECTED

            self._active_account_id = data.get("active_account_id")

            logger.info(f"Loaded {len(self._accounts)} accounts from encrypted storage")

        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")

    def _save_accounts(self) -> None:
        """Save accounts to encrypted file."""
        try:
            data = {
                "accounts": [acc.to_dict() for acc in self._accounts.values()],
                "active_account_id": self._active_account_id
            }

            json_data = json.dumps(data, indent=2)
            encrypted_data = self._encryption.encrypt(json_data)

            self.accounts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.accounts_file, "w") as f:
                f.write(encrypted_data)

            logger.debug("Accounts saved to encrypted storage")

        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")

    def add_account(
        self,
        name: str,
        login: int,
        password: str,
        server: str,
        account_type: AccountType = AccountType.DEMO,
        path: Optional[str] = None,
        enabled: bool = True
    ) -> MT5Account:
        """
        Add a new MT5 account.

        Args:
            name: Display name for the account
            login: MT5 account login number
            password: Account password
            server: Broker server name
            account_type: Demo or Live account
            path: Optional path to MT5 terminal
            enabled: Whether account is enabled

        Returns:
            The created MT5Account object

        Raises:
            ValueError: If account with same login already exists
        """
        with self._lock:
            # Check for duplicate login
            for existing in self._accounts.values():
                if existing.login == login and existing.server == server:
                    raise ValueError(f"Account with login {login} on {server} already exists")

            # Generate unique ID
            account_id = f"{name.lower().replace(' ', '_')}_{login}"

            # Create account object
            account = MT5Account(
                id=account_id,
                name=name,
                login=login,
                password=password,
                server=server,
                account_type=account_type,
                path=path,
                enabled=enabled
            )

            self._accounts[account_id] = account
            self._connection_status[account_id] = ConnectionStatus.DISCONNECTED

            self._save_accounts()

            logger.info(f"Added account: {name} ({login}@{server})")

            return account

    def remove_account(self, account_id: str) -> bool:
        """
        Remove an account.

        Args:
            account_id: Account identifier to remove

        Returns:
            True if account was removed
        """
        with self._lock:
            if account_id not in self._accounts:
                logger.warning(f"Account not found: {account_id}")
                return False

            # Disconnect if connected
            if account_id in self._connectors:
                try:
                    self._connectors[account_id].disconnect()
                except Exception:
                    pass
                del self._connectors[account_id]

            # Remove account
            account = self._accounts.pop(account_id)
            del self._connection_status[account_id]

            if account_id in self._account_info_cache:
                del self._account_info_cache[account_id]

            # Clear active if this was active
            if self._active_account_id == account_id:
                self._active_account_id = None

            self._save_accounts()

            logger.info(f"Removed account: {account.name} ({account.login})")

            return True

    def update_account(
        self,
        account_id: str,
        name: Optional[str] = None,
        password: Optional[str] = None,
        enabled: Optional[bool] = None,
        path: Optional[str] = None
    ) -> bool:
        """
        Update account details.

        Args:
            account_id: Account identifier
            name: New display name
            password: New password
            enabled: New enabled state
            path: New MT5 terminal path

        Returns:
            True if account was updated
        """
        with self._lock:
            if account_id not in self._accounts:
                return False

            account = self._accounts[account_id]

            if name is not None:
                account.name = name
            if password is not None:
                account.password = password
            if enabled is not None:
                account.enabled = enabled
            if path is not None:
                account.path = path

            self._save_accounts()

            logger.info(f"Updated account: {account.name}")

            return True

    def switch_account(self, account_id: str, connect: bool = True) -> bool:
        """
        Switch to a different account.

        Args:
            account_id: Account identifier to switch to
            connect: Whether to establish connection

        Returns:
            True if switch was successful
        """
        with self._lock:
            if account_id not in self._accounts:
                logger.error(f"Account not found: {account_id}")
                return False

            self._active_account_id = account_id
            self._save_accounts()

            if connect:
                return self.connect(account_id)

            return True

    def get_active_account(self) -> Optional[MT5Account]:
        """
        Get the currently active account.

        Returns:
            Active MT5Account or None if no active account
        """
        if self._active_account_id:
            return self._accounts.get(self._active_account_id)
        return None

    def get_account(self, account_id: str) -> Optional[MT5Account]:
        """
        Get account by ID.

        Args:
            account_id: Account identifier

        Returns:
            MT5Account or None if not found
        """
        return self._accounts.get(account_id)

    def list_accounts(self) -> List[MT5Account]:
        """
        List all accounts.

        Returns:
            List of all MT5Account objects
        """
        return list(self._accounts.values())

    def connect(self, account_id: Optional[str] = None) -> bool:
        """
        Connect to MT5 with specified account.

        Args:
            account_id: Account to connect (uses active if not specified)

        Returns:
            True if connection successful
        """
        account_id = account_id or self._active_account_id

        if not account_id:
            logger.error("No account specified for connection")
            return False

        account = self._accounts.get(account_id)
        if not account:
            logger.error(f"Account not found: {account_id}")
            return False

        with self._lock:
            self._connection_status[account_id] = ConnectionStatus.CONNECTING
            self._notify_status_change(account_id, ConnectionStatus.CONNECTING)

        try:
            # Import connector here to avoid circular imports
            from core.mt5_connector import MT5Connector

            # Create or reuse connector
            if account_id not in self._connectors:
                self._connectors[account_id] = MT5Connector()

            connector = self._connectors[account_id]

            # Connect with credentials
            success = connector.connect(
                login=account.login,
                password=account.password,
                server=account.server,
                path=account.path,
                timeout=60000
            )

            if success:
                with self._lock:
                    self._connection_status[account_id] = ConnectionStatus.CONNECTED
                    self._last_ping[account_id] = datetime.now()
                    account.last_connected = datetime.now().isoformat()
                    self._save_accounts()

                # Update account info cache
                self._update_account_info(account_id)

                self._notify_status_change(account_id, ConnectionStatus.CONNECTED)

                logger.info(f"Connected to account: {account.name} ({account.login})")
                return True
            else:
                with self._lock:
                    self._connection_status[account_id] = ConnectionStatus.ERROR

                self._notify_status_change(account_id, ConnectionStatus.ERROR)

                logger.error(f"Failed to connect to account: {account.name}")
                return False

        except Exception as e:
            with self._lock:
                self._connection_status[account_id] = ConnectionStatus.ERROR

            self._notify_status_change(account_id, ConnectionStatus.ERROR)

            logger.error(f"Connection error for {account_id}: {e}")
            return False

    def disconnect(self, account_id: Optional[str] = None) -> bool:
        """
        Disconnect from MT5.

        Args:
            account_id: Account to disconnect (uses active if not specified)

        Returns:
            True if disconnection successful
        """
        account_id = account_id or self._active_account_id

        if not account_id:
            return False

        try:
            if account_id in self._connectors:
                self._connectors[account_id].disconnect()

            with self._lock:
                self._connection_status[account_id] = ConnectionStatus.DISCONNECTED

            self._notify_status_change(account_id, ConnectionStatus.DISCONNECTED)

            logger.info(f"Disconnected from account: {account_id}")
            return True

        except Exception as e:
            logger.error(f"Disconnect error for {account_id}: {e}")
            return False

    def disconnect_all(self) -> None:
        """Disconnect all connected accounts."""
        for account_id in list(self._connectors.keys()):
            self.disconnect(account_id)

    def get_connector(self, account_id: Optional[str] = None) -> Optional[Any]:
        """
        Get MT5Connector for an account.

        Args:
            account_id: Account identifier (uses active if not specified)

        Returns:
            MT5Connector instance or None
        """
        account_id = account_id or self._active_account_id
        if account_id:
            return self._connectors.get(account_id)
        return None

    def get_connection_status(self, account_id: Optional[str] = None) -> ConnectionStatus:
        """
        Get connection status for an account.

        Args:
            account_id: Account identifier (uses active if not specified)

        Returns:
            ConnectionStatus enum value
        """
        account_id = account_id or self._active_account_id
        if account_id:
            return self._connection_status.get(account_id, ConnectionStatus.DISCONNECTED)
        return ConnectionStatus.DISCONNECTED

    def get_account_info(self, account_id: Optional[str] = None, refresh: bool = False) -> Optional[AccountInfo]:
        """
        Get account information.

        Args:
            account_id: Account identifier (uses active if not specified)
            refresh: Force refresh from MT5

        Returns:
            AccountInfo object or None
        """
        account_id = account_id or self._active_account_id

        if not account_id:
            return None

        if refresh or account_id not in self._account_info_cache:
            self._update_account_info(account_id)

        return self._account_info_cache.get(account_id)

    def _update_account_info(self, account_id: str) -> None:
        """Update cached account info from MT5."""
        connector = self._connectors.get(account_id)
        if not connector:
            return

        try:
            info = connector.get_account_info()
            if info:
                self._account_info_cache[account_id] = AccountInfo(
                    login=info.login,
                    balance=info.balance,
                    equity=info.equity,
                    margin=info.margin,
                    free_margin=info.free_margin,
                    margin_level=info.margin_level,
                    profit=info.profit,
                    currency=info.currency,
                    leverage=info.leverage,
                    server=info.server,
                    company=info.company,
                    trade_allowed=True,
                    connected=True
                )
        except Exception as e:
            logger.error(f"Failed to update account info for {account_id}: {e}")

    def start_health_monitoring(self) -> None:
        """Start background health monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="AccountHealthMonitor"
        )
        self._monitor_thread.start()
        logger.info("Started account health monitoring")

    def stop_health_monitoring(self) -> None:
        """Stop health monitoring thread."""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped account health monitoring")

    def _health_monitor_loop(self) -> None:
        """Background loop for connection health checks."""
        while not self._stop_monitor.is_set():
            try:
                for account_id, connector in list(self._connectors.items()):
                    if self._stop_monitor.is_set():
                        break

                    status = self._connection_status.get(account_id)

                    if status == ConnectionStatus.CONNECTED:
                        # Ping check
                        try:
                            if connector.is_connected():
                                self._last_ping[account_id] = datetime.now()
                                # Refresh account info
                                self._update_account_info(account_id)
                            else:
                                # Connection lost
                                with self._lock:
                                    self._connection_status[account_id] = ConnectionStatus.DISCONNECTED
                                self._notify_status_change(account_id, ConnectionStatus.DISCONNECTED)

                                if self.auto_reconnect:
                                    # Attempt reconnection
                                    logger.warning(f"Connection lost for {account_id}, attempting reconnect...")
                                    self._connection_status[account_id] = ConnectionStatus.RECONNECTING
                                    self._notify_status_change(account_id, ConnectionStatus.RECONNECTING)
                                    self.connect(account_id)
                        except Exception as e:
                            logger.error(f"Health check failed for {account_id}: {e}")
                            with self._lock:
                                self._connection_status[account_id] = ConnectionStatus.ERROR
                            self._notify_status_change(account_id, ConnectionStatus.ERROR)

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

            # Sleep in intervals to allow quick shutdown
            for _ in range(self.ping_interval):
                if self._stop_monitor.is_set():
                    break
                time.sleep(1)

    def register_status_callback(self, callback: Callable[[str, ConnectionStatus], None]) -> None:
        """
        Register a callback for connection status changes.

        Args:
            callback: Function(account_id, status) to call on status change
        """
        self._status_callbacks.append(callback)

    def unregister_status_callback(self, callback: Callable[[str, ConnectionStatus], None]) -> None:
        """
        Unregister a status callback.

        Args:
            callback: Previously registered callback function
        """
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def _notify_status_change(self, account_id: str, status: ConnectionStatus) -> None:
        """Notify all registered callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                callback(account_id, status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    def get_all_account_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get info for all accounts including connection status.

        Returns:
            Dictionary mapping account_id to account details
        """
        result = {}

        for account_id, account in self._accounts.items():
            info = self._account_info_cache.get(account_id)

            result[account_id] = {
                "account": account.to_dict(),
                "connection_status": self._connection_status.get(
                    account_id, ConnectionStatus.DISCONNECTED
                ).value,
                "is_active": account_id == self._active_account_id,
                "account_info": asdict(info) if info else None,
                "last_ping": self._last_ping.get(account_id, datetime.min).isoformat()
                    if account_id in self._last_ping else None
            }

        return result

    def __enter__(self):
        """Context manager entry."""
        self.start_health_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_health_monitoring()
        self.disconnect_all()


# Global singleton instance
_account_manager: Optional[AccountManager] = None


def get_account_manager() -> AccountManager:
    """
    Get or create the global AccountManager singleton.

    Returns:
        AccountManager instance
    """
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager
