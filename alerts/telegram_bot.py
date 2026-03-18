"""
Telegram Alert System.
"""
import asyncio
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


@dataclass
class TradeAlert:
    """Trade alert data."""
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    strategy: str
    timestamp: datetime


@dataclass
class CloseAlert:
    """Position close alert data."""
    symbol: str
    direction: str
    entry_price: float
    close_price: float
    profit: float
    pips: float
    duration: str
    strategy: str
    timestamp: datetime


class TelegramAlert:
    """
    Telegram notification system.

    Send alerts for:
    - Trade entries
    - Trade exits
    - Daily summaries
    - Error notifications
    """

    def __init__(self, token: str = "", chat_id: str = ""):
        """
        Initialize Telegram bot.

        Args:
            token: Telegram bot token
            chat_id: Chat ID to send messages to
        """
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        self._bot: Optional[Bot] = None

        if self.enabled and TELEGRAM_AVAILABLE:
            self._bot = Bot(token=token)
            logger.info("Telegram alerts initialized")
        elif not TELEGRAM_AVAILABLE:
            logger.warning("python-telegram-bot not installed. Telegram alerts disabled.")

    async def send_message(self, message: str) -> bool:
        """
        Send a message to Telegram.

        Args:
            message: Message text (supports Markdown)

        Returns:
            True if sent successfully
        """
        if not self.enabled or not self._bot:
            return False

        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

    def send_message_sync(self, message: str) -> bool:
        """Synchronous wrapper for send_message."""
        try:
            return asyncio.run(self.send_message(message))
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_trade_alert(self, alert: TradeAlert) -> bool:
        """
        Send trade entry alert.

        Args:
            alert: Trade alert data
        """
        emoji = "🟢" if alert.direction == "BUY" else "🔴"
        rr = abs(alert.take_profit - alert.entry_price) / abs(alert.entry_price - alert.stop_loss)

        message = f"""
{emoji} *NEW TRADE ALERT*

📊 *Symbol:* `{alert.symbol}`
📈 *Direction:* {alert.direction}
💰 *Entry:* `{alert.entry_price:.5f}`
🛑 *Stop Loss:* `{alert.stop_loss:.5f}`
🎯 *Take Profit:* `{alert.take_profit:.5f}`
📏 *R:R Ratio:* `{rr:.2f}`
📦 *Lot Size:* `{alert.lot_size}`
🤖 *Strategy:* {alert.strategy}
⏰ *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(message.strip())

    def send_close_alert(self, alert: CloseAlert) -> bool:
        """
        Send position close alert.

        Args:
            alert: Close alert data
        """
        emoji = "✅" if alert.profit > 0 else "❌"
        color = "🟢" if alert.profit > 0 else "🔴"

        message = f"""
{emoji} *TRADE CLOSED*

📊 *Symbol:* `{alert.symbol}`
📈 *Direction:* {alert.direction}
💰 *Entry:* `{alert.entry_price:.5f}`
💵 *Close:* `{alert.close_price:.5f}`
{color} *P&L:* `${alert.profit:.2f}` ({alert.pips:.1f} pips)
⏱ *Duration:* {alert.duration}
🤖 *Strategy:* {alert.strategy}
⏰ *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(message.strip())

    def send_daily_summary(
        self,
        date: datetime,
        total_trades: int,
        winning_trades: int,
        total_profit: float,
        win_rate: float,
        best_trade: float,
        worst_trade: float
    ) -> bool:
        """Send daily trading summary."""
        emoji = "📈" if total_profit > 0 else "📉"

        message = f"""
{emoji} *DAILY SUMMARY - {date.strftime('%Y-%m-%d')}*

📊 *Total Trades:* {total_trades}
✅ *Winning Trades:* {winning_trades}
🎯 *Win Rate:* {win_rate:.1f}%
💰 *Total P&L:* `${total_profit:.2f}`
🏆 *Best Trade:* `${best_trade:.2f}`
💀 *Worst Trade:* `${worst_trade:.2f}`
"""
        return self.send_message_sync(message.strip())

    def send_error_alert(self, error: str, context: str = "") -> bool:
        """Send error notification."""
        message = f"""
⚠️ *ERROR ALERT*

🔴 *Error:* {error}
📍 *Context:* {context if context else "N/A"}
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(message.strip())

    def send_startup_message(self, strategies: list) -> bool:
        """Send bot startup notification."""
        strategy_list = "\n".join([f"  • {s}" for s in strategies])

        message = f"""
🚀 *TRADING BOT STARTED*

📊 *Active Strategies:*
{strategy_list}

⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(message.strip())

    def send_shutdown_message(self, reason: str = "Manual shutdown") -> bool:
        """Send bot shutdown notification."""
        message = f"""
🛑 *TRADING BOT STOPPED*

📍 *Reason:* {reason}
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(message.strip())
