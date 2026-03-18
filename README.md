# MT5 Trading Bot

A modular, high-performance trading bot for MetaTrader 5 with a Streamlit web interface. Designed for fast strategy development and deployment.

## Features

- **Modular Strategy System** - Add new strategies by creating a Python file + YAML config
- **Multi-Symbol Support** - Trade XAUUSD, EURUSD, GBPUSD, and more simultaneously
- **Smart Money Concepts** - Built-in CHoCH, FVG, Order Block detection
- **Backtesting Engine** - Test strategies on historical data with detailed metrics
- **Risk Management** - Position sizing, daily loss limits, max drawdown protection
- **Real-time Alerts** - Telegram and Discord notifications
- **Web UI** - Streamlit dashboard for monitoring and configuration

## Project Structure

```
├── main.py                     # Entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── LICENSE                    # MIT License
├── config/
│   ├── settings.yaml          # Global settings (non-sensitive)
│   └── strategies/            # Strategy configurations
│       ├── smc_scalper.yaml
│       ├── trend_break_trauma.yaml
│       └── crt_tbs.yaml
├── core/
│   ├── strategy_base.py       # Abstract Strategy class
│   ├── mt5_connector.py       # MT5 API wrapper
│   ├── strategy_loader.py     # Dynamic strategy discovery
│   ├── risk_manager.py        # Risk calculations
│   ├── trade_executor.py      # Order execution
│   └── backtest_engine.py     # Backtesting
├── strategies/
│   ├── smc_scalper.py         # SMC Scalper strategy
│   ├── trend_break_trauma.py  # Trend Break + RSI strategy
│   └── crt_tbs.py             # CRT + TBS strategy
├── indicators/
│   ├── common.py              # RSI, EMA, ATR, etc.
│   ├── smc_utils.py           # CHoCH, FVG, Order Blocks
│   └── trend_utils.py         # Trend line detection
├── alerts/
│   ├── telegram_bot.py        # Telegram notifications
│   └── discord_bot.py         # Discord webhooks
├── ui/
│   ├── app.py                 # Streamlit main app
│   └── pages/                 # UI pages
│       ├── dashboard.py       # Live trading view
│       ├── strategies.py      # Strategy management
│       ├── backtest.py        # Backtesting interface
│       └── settings.py        # Configuration
└── utils/
    ├── config.py              # Environment config loader
    ├── logger.py              # Logging setup
    └── helpers.py             # Utility functions
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** MetaTrader5 package only works on Windows. For other platforms, use the backtesting and UI features.

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# MetaTrader 5
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Demo

# Telegram Alerts (optional)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Discord Alerts (optional)
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=your_webhook_url
```

**Important:** Never commit `.env` to version control!

### 3. Run the Bot

**CLI Mode (Live Trading):**
```bash
python main.py
```

**Web UI Mode:**
```bash
python main.py --ui
# Or directly:
streamlit run ui/app.py
```

**Dry Run (Test Configuration):**
```bash
python main.py --dry-run
```

## Included Strategies

### 1. SMC Scalper
Smart Money Concepts based scalping strategy.

- **Entry:** CHoCH + FVG confluence
- **Target:** Order Block or R:R ratio
- **Timeframe:** M15
- **Best for:** XAUUSD during London/NY session

### 2. Trend Break + Trauma + RSI
Trend line breakout strategy with EMA filter.

- **Entry:** Price above/below Trauma (EMA) + Trend break
- **Exit:** RSI overbought/oversold
- **Timeframe:** H1
- **Best for:** Trending markets

### 3. CRT + TBS (Candle Range Theory + Time-Based Strategy)
Asian session range + killzone liquidity sweep strategy.

- **Range:** Asian Session (00:00-06:00 UTC) defines High/Low
- **Killzones:** London (07:00-09:00) and NY (13:00-15:00)
- **Entry:** Price sweeps beyond range, then closes back inside
- **Exit:** Opposite end of Asian range
- **Timeframe:** M5 entry, H1 range
- **Best for:** XAUUSD during high-volatility sessions

## Adding New Strategies

### Step 1: Create Strategy File

Create `strategies/my_strategy.py`:

```python
from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
import pandas as pd
from typing import Optional, Dict, Any

class MyStrategy(StrategyBase):
    name = "My Strategy"
    version = "1.0.0"
    description = "My custom trading strategy"

    def initialize(self, config: Dict[str, Any]) -> None:
        """Load strategy parameters from config."""
        self.config = config
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M15")
        self.enabled = config.get("enabled", True)

        # Load your custom parameters
        params = config.get("parameters", {})
        self.my_param = params.get("my_param", 10)

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trade signal.

        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            data: OHLCV DataFrame with columns: time, open, high, low, close, volume

        Returns:
            TradeSignal if entry condition met, None otherwise
        """
        # Your entry logic here
        if your_buy_condition:
            return TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=data.iloc[-1]["close"],
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                comment="My Strategy BUY"
            )

        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
        """Check if position should be closed."""
        # Your exit logic here
        return False
```

### Step 2: Create Config File

Create `config/strategies/my_strategy.yaml`:

```yaml
name: "My Strategy"
enabled: true
description: "My custom trading strategy"

symbols:
  - XAUUSD

timeframe: M15
magic_number: 123456

# Strategy-specific parameters (non-sensitive)
parameters:
  my_param: 10
  another_param: 2.5

# Risk settings for this strategy
risk:
  max_risk_percent: 2.0
  lot_size: 0.01

# Trading session (hours in UTC)
session:
  start_hour: 8
  end_hour: 18
  trade_friday: false

# Enable/disable alerts for this strategy
# (Credentials are in .env file, not here!)
alerts:
  telegram: true
  discord: false
```

**Note:** Strategy YAML files contain only non-sensitive parameters. All credentials (MT5 login, Telegram tokens, Discord webhooks) must be configured in the `.env` file.

### Step 3: Done!

The bot automatically discovers and loads your strategy. Enable it via the UI or set `enabled: true` in the YAML file.

## Configuration

Configuration uses environment variables (`.env` file) for sensitive data and YAML files for non-sensitive settings.

### Environment Variables (`.env`)

Copy `.env.example` to `.env` and configure:

```bash
# MetaTrader 5 Connection
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Demo
MT5_PATH=                          # Optional: path to terminal

# Risk Management
MAX_RISK_PER_TRADE=2.0
MAX_DAILY_LOSS=5.0
MAX_DRAWDOWN=20.0
MAX_POSITIONS=5

# Telegram Alerts
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Discord Alerts
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=your_webhook_url

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
```

### YAML Settings (`config/settings.yaml`)

Non-sensitive settings (environment variables take precedence):

```yaml
# Risk Management (can override via env vars)
risk:
  max_risk_per_trade: 2.0
  max_daily_loss: 5.0
  max_drawdown: 20.0
  max_positions: 5

# Trading Settings
trading:
  default_lot_size: 0.01
  default_magic_number: 123456
  slippage: 10
  check_interval: 1

# Logging
logging:
  level: INFO
  file: logs/trading_bot.log
```

## Backtesting

Run backtests via the Web UI:

1. Launch UI: `streamlit run ui/app.py`
2. Go to "Backtest" page
3. Select strategy, symbol, date range
4. Click "Run Backtest"

Or programmatically:

```python
from core.mt5_connector import MT5Connector
from core.backtest_engine import BacktestEngine
from strategies.smc_scalper import SMCScalper
from datetime import datetime, timedelta

mt5 = MT5Connector()
mt5.connect()

engine = BacktestEngine(mt5)
strategy = SMCScalper()
strategy.initialize({"symbols": ["XAUUSD"], "timeframe": "M15", "enabled": True})

result = engine.run_backtest(
    strategy=strategy,
    symbol="XAUUSD",
    timeframe="M15",
    start_date=datetime.now() - timedelta(days=90),
    end_date=datetime.now(),
    initial_balance=10000
)

print(engine.generate_report(result))
```

## Alerts Setup

### Telegram

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `config/settings.yaml`:
   ```yaml
   alerts:
     telegram:
       enabled: true
       token: "YOUR_BOT_TOKEN"
       chat_id: "YOUR_CHAT_ID"
   ```

### Discord

1. Create a webhook in your Discord server (Server Settings > Integrations > Webhooks)
2. Add to `config/settings.yaml`:
   ```yaml
   alerts:
     discord:
       enabled: true
       webhook_url: "YOUR_WEBHOOK_URL"
   ```

## Risk Warning

Trading involves significant risk of loss. This software is for educational purposes. Always:

- Test on demo accounts first
- Use conservative risk settings (1-2% per trade)
- Never risk more than you can afford to lose
- Past performance doesn't guarantee future results

## Requirements

- Python 3.9+
- MetaTrader 5 terminal (Windows only for live trading)
- MT5 account with broker

## Dependencies

- MetaTrader5
- pandas, numpy
- streamlit, plotly
- pyyaml
- python-telegram-bot
- requests
- ta (technical analysis)
- loguru

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Disclaimer:** Trading involves significant risk. Use at your own risk.

## Support

For issues and feature requests, create an issue on GitHub.
