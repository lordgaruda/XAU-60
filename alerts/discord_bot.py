"""
Discord Alert System using webhooks.
"""
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


@dataclass
class TradeAlert:
    """Trade alert data."""
    symbol: str
    direction: str
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


class DiscordAlert:
    """
    Discord webhook notification system.

    Send alerts for:
    - Trade entries
    - Trade exits
    - Daily summaries
    - Error notifications
    """

    def __init__(self, webhook_url: str = ""):
        """
        Initialize Discord webhook.

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
        self.username = "Trading Bot"
        self.avatar_url = ""

        if self.enabled:
            logger.info("Discord alerts initialized")

    def send_message(self, content: str = "", embed: Dict[str, Any] = None) -> bool:
        """
        Send a message to Discord.

        Args:
            content: Plain text content
            embed: Discord embed object

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        payload = {
            "username": self.username,
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        if content:
            payload["content"] = content

        if embed:
            payload["embeds"] = [embed]

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            return response.status_code == 204
        except requests.RequestException as e:
            logger.error(f"Discord webhook error: {e}")
            return False

    def send_trade_alert(self, alert: TradeAlert) -> bool:
        """Send trade entry alert."""
        color = 0x00FF00 if alert.direction == "BUY" else 0xFF0000
        rr = abs(alert.take_profit - alert.entry_price) / abs(alert.entry_price - alert.stop_loss)

        embed = {
            "title": f"{'🟢' if alert.direction == 'BUY' else '🔴'} NEW TRADE: {alert.symbol}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": alert.direction, "inline": True},
                {"name": "Entry", "value": f"`{alert.entry_price:.5f}`", "inline": True},
                {"name": "Stop Loss", "value": f"`{alert.stop_loss:.5f}`", "inline": True},
                {"name": "Take Profit", "value": f"`{alert.take_profit:.5f}`", "inline": True},
                {"name": "R:R Ratio", "value": f"`{rr:.2f}`", "inline": True},
                {"name": "Lot Size", "value": f"`{alert.lot_size}`", "inline": True},
                {"name": "Strategy", "value": alert.strategy, "inline": True},
            ],
            "timestamp": alert.timestamp.isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)

    def send_close_alert(self, alert: CloseAlert) -> bool:
        """Send position close alert."""
        color = 0x00FF00 if alert.profit > 0 else 0xFF0000
        emoji = "✅" if alert.profit > 0 else "❌"

        embed = {
            "title": f"{emoji} TRADE CLOSED: {alert.symbol}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": alert.direction, "inline": True},
                {"name": "Entry", "value": f"`{alert.entry_price:.5f}`", "inline": True},
                {"name": "Close", "value": f"`{alert.close_price:.5f}`", "inline": True},
                {"name": "P&L", "value": f"`${alert.profit:.2f}`", "inline": True},
                {"name": "Pips", "value": f"`{alert.pips:.1f}`", "inline": True},
                {"name": "Duration", "value": alert.duration, "inline": True},
                {"name": "Strategy", "value": alert.strategy, "inline": True},
            ],
            "timestamp": alert.timestamp.isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)

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
        color = 0x00FF00 if total_profit > 0 else 0xFF0000
        emoji = "📈" if total_profit > 0 else "📉"

        embed = {
            "title": f"{emoji} Daily Summary - {date.strftime('%Y-%m-%d')}",
            "color": color,
            "fields": [
                {"name": "Total Trades", "value": str(total_trades), "inline": True},
                {"name": "Winning", "value": str(winning_trades), "inline": True},
                {"name": "Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
                {"name": "Total P&L", "value": f"`${total_profit:.2f}`", "inline": True},
                {"name": "Best Trade", "value": f"`${best_trade:.2f}`", "inline": True},
                {"name": "Worst Trade", "value": f"`${worst_trade:.2f}`", "inline": True},
            ],
            "timestamp": date.isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)

    def send_error_alert(self, error: str, context: str = "") -> bool:
        """Send error notification."""
        embed = {
            "title": "⚠️ Error Alert",
            "color": 0xFF6600,
            "description": f"**Error:** {error}",
            "fields": [
                {"name": "Context", "value": context if context else "N/A", "inline": False},
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)

    def send_startup_message(self, strategies: list) -> bool:
        """Send bot startup notification."""
        strategy_list = "\n".join([f"• {s}" for s in strategies])

        embed = {
            "title": "🚀 Trading Bot Started",
            "color": 0x00FF00,
            "description": f"**Active Strategies:**\n{strategy_list}",
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)

    def send_shutdown_message(self, reason: str = "Manual shutdown") -> bool:
        """Send bot shutdown notification."""
        embed = {
            "title": "🛑 Trading Bot Stopped",
            "color": 0xFF0000,
            "description": f"**Reason:** {reason}",
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Trading Bot"}
        }

        return self.send_message(embed=embed)
