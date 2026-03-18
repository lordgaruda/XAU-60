"""
Environment configuration loader.
Loads settings from environment variables with fallback to defaults.
"""
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


# Load .env file if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_env(key: str, default: Any = None, cast: type = str) -> Any:
    """
    Get environment variable with type casting.

    Args:
        key: Environment variable name
        default: Default value if not set
        cast: Type to cast the value to

    Returns:
        Environment variable value or default
    """
    value = os.getenv(key)

    if value is None:
        return default

    if cast == bool:
        return value.lower() in ("true", "1", "yes", "on")
    elif cast == int:
        try:
            return int(value)
        except ValueError:
            return default
    elif cast == float:
        try:
            return float(value)
        except ValueError:
            return default
    else:
        return value


@dataclass
class MT5Config:
    """MetaTrader 5 connection configuration."""
    login: int = field(default_factory=lambda: get_env("MT5_LOGIN", 0, int))
    password: str = field(default_factory=lambda: get_env("MT5_PASSWORD", ""))
    server: str = field(default_factory=lambda: get_env("MT5_SERVER", ""))
    path: str = field(default_factory=lambda: get_env("MT5_PATH", ""))
    timeout: int = field(default_factory=lambda: get_env("MT5_TIMEOUT", 60000, int))


@dataclass
class TelegramConfig:
    """Telegram alert configuration."""
    enabled: bool = field(default_factory=lambda: get_env("TELEGRAM_ENABLED", False, bool))
    token: str = field(default_factory=lambda: get_env("TELEGRAM_BOT_TOKEN", ""))
    chat_id: str = field(default_factory=lambda: get_env("TELEGRAM_CHAT_ID", ""))


@dataclass
class DiscordConfig:
    """Discord alert configuration."""
    enabled: bool = field(default_factory=lambda: get_env("DISCORD_ENABLED", False, bool))
    webhook_url: str = field(default_factory=lambda: get_env("DISCORD_WEBHOOK_URL", ""))


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_risk_per_trade: float = field(default_factory=lambda: get_env("MAX_RISK_PER_TRADE", 2.0, float))
    max_daily_loss: float = field(default_factory=lambda: get_env("MAX_DAILY_LOSS", 5.0, float))
    max_drawdown: float = field(default_factory=lambda: get_env("MAX_DRAWDOWN", 20.0, float))
    max_positions: int = field(default_factory=lambda: get_env("MAX_POSITIONS", 5, int))
    max_positions_per_symbol: int = field(default_factory=lambda: get_env("MAX_POSITIONS_PER_SYMBOL", 2, int))


@dataclass
class TradingConfig:
    """Trading settings configuration."""
    default_lot_size: float = field(default_factory=lambda: get_env("DEFAULT_LOT_SIZE", 0.01, float))
    default_magic_number: int = field(default_factory=lambda: get_env("DEFAULT_MAGIC_NUMBER", 123456, int))
    slippage: int = field(default_factory=lambda: get_env("SLIPPAGE", 10, int))
    check_interval: int = field(default_factory=lambda: get_env("CHECK_INTERVAL", 1, int))


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: get_env("LOG_LEVEL", "INFO"))
    file: str = field(default_factory=lambda: get_env("LOG_FILE", "logs/trading_bot.log"))
    rotation: str = field(default_factory=lambda: get_env("LOG_ROTATION", "10 MB"))
    retention: str = field(default_factory=lambda: get_env("LOG_RETENTION", "7 days"))


@dataclass
class UIConfig:
    """UI configuration."""
    refresh_rate: int = field(default_factory=lambda: get_env("UI_REFRESH_RATE", 5, int))
    theme: str = field(default_factory=lambda: get_env("UI_THEME", "light"))


@dataclass
class Config:
    """Main configuration class."""
    mt5: MT5Config = field(default_factory=MT5Config)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "mt5": {
                "login": self.mt5.login,
                "password": self.mt5.password,
                "server": self.mt5.server,
                "path": self.mt5.path,
                "timeout": self.mt5.timeout,
            },
            "alerts": {
                "telegram": {
                    "enabled": self.telegram.enabled,
                    "token": self.telegram.token,
                    "chat_id": self.telegram.chat_id,
                },
                "discord": {
                    "enabled": self.discord.enabled,
                    "webhook_url": self.discord.webhook_url,
                },
            },
            "risk": {
                "max_risk_per_trade": self.risk.max_risk_per_trade,
                "max_daily_loss": self.risk.max_daily_loss,
                "max_drawdown": self.risk.max_drawdown,
                "max_positions": self.risk.max_positions,
                "max_positions_per_symbol": self.risk.max_positions_per_symbol,
            },
            "trading": {
                "default_lot_size": self.trading.default_lot_size,
                "default_magic_number": self.trading.default_magic_number,
                "slippage": self.trading.slippage,
                "check_interval": self.trading.check_interval,
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file,
                "rotation": self.logging.rotation,
                "retention": self.logging.retention,
            },
            "ui": {
                "refresh_rate": self.ui.refresh_rate,
                "theme": self.ui.theme,
            },
        }


def load_config() -> Config:
    """
    Load configuration from environment variables.

    Returns:
        Config object with all settings
    """
    return Config()


# Global config instance
config = load_config()
