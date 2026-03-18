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
├── config/
│   ├── settings.yaml          # Global settings (MT5, risk, alerts)
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
    ├── logger.py              # Logging setup
    └── helpers.py             # Utility functions
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** MetaTrader5 package only works on Windows. For other platforms, use the backtesting and UI features.

### 2. Configure MT5 Connection

Edit `config/settings.yaml`:

```yaml
mt5:
  login: YOUR_ACCOUNT_NUMBER
  password: YOUR_PASSWORD
  server: YOUR_BROKER_SERVER
```

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

parameters:
  my_param: 10
  another_param: 2.5

risk:
  max_risk_percent: 2.0
  lot_size: 0.01

session:
  start_hour: 8
  end_hour: 18
  trade_friday: false

alerts:
  telegram: true
  discord: false
```

### Step 3: Done!

The bot automatically discovers and loads your strategy. Enable it via the UI or set `enabled: true` in the YAML file.

## Configuration

### Global Settings (`config/settings.yaml`)

```yaml
mt5:
  login: 0
  password: ""
  server: ""
  timeout: 60000

risk:
  max_risk_per_trade: 2.0    # % of balance
  max_daily_loss: 5.0        # % daily loss limit
  max_drawdown: 20.0         # % max drawdown
  max_positions: 5           # Max simultaneous positions

alerts:
  telegram:
    enabled: false
    token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
  discord:
    enabled: false
    webhook_url: "YOUR_WEBHOOK_URL"

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
