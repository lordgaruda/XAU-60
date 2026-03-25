# MT5 Trading Bot Pro v2.0

A professional-grade, modular trading bot for MetaTrader 5 with a modern Streamlit web interface. Features multi-account management, advanced risk controls, and production-ready trading strategies.

## What's New in v2.0

- **Multi-Account Management** - Securely manage multiple MT5 accounts with encrypted credential storage
- **Professional Trading Dashboard** - Real-time candlestick charts, live positions, and manual trading panel
- **Strategy Builder** - Visual strategy creation, deployment, and monitoring
- **Advanced Trade Executor** - Trailing stops, break-even, partial closes, and order retry logic
- **Enhanced Risk Management** - Circuit breaker, correlation exposure limits, and real-time risk monitoring
- **Signal Quality Scoring** - Each strategy rates signals (A+, A, B, C, D) for trade confidence
- **Improved Backtesting** - Strategy comparison, equity curves, and CSV export

## Features

### Core Features
- **Modular Strategy System** - Add new strategies by creating a Python file + YAML config
- **Multi-Symbol Support** - Trade XAUUSD, EURUSD, GBPUSD, and more simultaneously
- **Smart Money Concepts** - Built-in CHoCH, FVG, Order Block detection
- **Backtesting Engine** - Test strategies on historical data with detailed metrics
- **Real-time Alerts** - Telegram and Discord notifications
- **Web UI** - Modern Streamlit dashboard for monitoring and configuration

### Advanced Features (v2.0)
- **Encrypted Account Storage** - Fernet encryption for MT5 credentials
- **Auto-Reconnect** - Health monitoring with automatic reconnection
- **Circuit Breaker** - Pauses trading after consecutive losses
- **Trailing Stops** - Automatic trailing stop management
- **Break-Even** - Move stop loss to entry when in profit
- **Partial Close** - Close portions of positions at targets
- **Correlation Risk** - Limits exposure to correlated pairs

## Project Structure

```
├── main.py                     # Entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── config/
│   ├── settings.yaml          # Global settings
│   └── strategies/            # Strategy configurations
├── core/
│   ├── strategy_base.py       # Abstract Strategy class
│   ├── mt5_connector.py       # MT5 API wrapper with multi-account
│   ├── account_manager.py     # Encrypted account management
│   ├── trade_executor.py      # Advanced order execution
│   ├── risk_manager.py        # Comprehensive risk controls
│   ├── strategy_loader.py     # Dynamic strategy discovery
│   └── backtest_engine.py     # Backtesting
├── strategies/
│   ├── __init__.py            # Strategy registry
│   ├── smc_scalper.py         # SMC Scalper strategy
│   ├── trend_break_trauma.py  # Trend Break + RSI strategy
│   └── crt_tbs.py             # CRT + TBS strategy
├── indicators/
│   ├── common.py              # RSI, EMA, ATR, MACD, etc.
│   ├── smc_utils.py           # CHoCH, FVG, Order Blocks
│   └── trend_utils.py         # Trend line detection
├── alerts/
│   ├── telegram_bot.py        # Telegram notifications
│   └── discord_bot.py         # Discord webhooks
├── ui/
│   ├── app.py                 # Streamlit main app
│   └── pages/
│       ├── dashboard.py       # Live trading dashboard
│       ├── strategies.py      # Strategy management
│       ├── strategy_builder.py # Visual strategy builder
│       ├── backtest.py        # Backtesting interface
│       ├── accounts.py        # Multi-account management
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

**Note:** MetaTrader5 package only works on Windows. For macOS/Linux, use the mock MT5 module for development and backtesting.

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# MetaTrader 5 (Primary Account)
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Demo

# Optional: Encryption key for account storage
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# Risk Management
MAX_RISK_PER_TRADE=2.0
MAX_DAILY_LOSS=5.0
MAX_DRAWDOWN=20.0
CIRCUIT_BREAKER_CONSECUTIVE_LOSSES=3

# Alerts (optional)
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Important:** Never commit `.env` to version control!

### 3. Run the Bot

**Web UI Mode (Recommended):**
```bash
streamlit run ui/app.py
```

**CLI Mode (Live Trading):**
```bash
python main.py
```

**Dry Run (Test Configuration):**
```bash
python main.py --dry-run
```

## Included Strategies

All strategies include signal quality scoring (A+, A, B, C, D) based on multiple confirmation factors.

### 1. SMC Scalper v2.1
Smart Money Concepts based scalping strategy with confidence scoring.

| Feature | Details |
|---------|---------|
| **Entry** | CHoCH + FVG confluence + Order Block target |
| **Confirmations** | MTF trend, ADX strength, RSI momentum, session timing |
| **Exit** | Order Block target, opposing CHoCH, or R:R ratio |
| **Timeframe** | M15 |
| **Best for** | XAUUSD during London/NY session |

**Quality Scoring Factors:**
- CHoCH detected (2 pts)
- FVG detected (2 pts)
- Order Block valid (1 pt)
- Trend aligned (2 pts)
- Price in FVG zone (1 pt)
- Session optimal (1 pt)
- ADX filter passed (1 pt)
- RSI filter passed (1 pt)
- Spread acceptable (1 pt)

### 2. Trend Break + Trauma + RSI v2.1
Trend line breakout strategy with EMA filter and momentum confirmation.

| Feature | Details |
|---------|---------|
| **Entry** | Price above/below Trauma (EMA21) + Trend break + Displacement |
| **Confirmations** | EMA stack (8/21/50), MACD alignment, ADX strength, volume spike |
| **Exit** | RSI overbought/oversold or divergence detection |
| **Timeframe** | H1 |
| **Best for** | Trending markets |

**Quality Scoring Factors:**
- Trendline break (2 pts)
- Price above Trauma (2 pts)
- Breakout displacement (2 pts)
- EMA stack aligned (1 pt)
- MACD aligned (1 pt)
- ADX strong trend (1 pt)
- RSI momentum aligned (1 pt)
- Session optimal (1 pt)

### 3. CRT + TBS v2.1 (Candle Range Theory + Time-Based Strategy)
Asian session range + killzone liquidity sweep strategy with manipulation quality scoring.

| Feature | Details |
|---------|---------|
| **Range** | Asian Session (00:00-06:00 UTC) defines High/Low |
| **Killzones** | London (07:00-09:00), NY (13:00-15:00), London Close (optional) |
| **Entry** | Price sweeps beyond range, closes back inside with confirmation |
| **Exit** | Opposite end of Asian range or time-based exit |
| **Timeframe** | M5 entry, H1 range |
| **Best for** | XAUUSD during high-volatility sessions |

**Sweep Quality Levels:**
- **Perfect** - Textbook manipulation with strong rejection
- **Strong** - Clear sweep with displacement
- **Moderate** - Decent sweep with momentum
- **Weak** - Small sweep, quick return

## UI Pages

### Dashboard
- Real-time account metrics (balance, equity, profit)
- Interactive candlestick chart with EMA overlays
- Live positions table with close buttons
- Manual trading panel (Buy/Sell with SL/TP)

### Strategy Builder
- Visual strategy list with enable/disable toggles
- Live parameter editing
- Deploy/undeploy strategies
- Strategy performance monitoring

### Backtest
- Single strategy backtesting
- Strategy comparison mode
- Equity curve visualization
- Drawdown analysis
- Trade distribution charts
- CSV export

### Accounts
- Add/remove MT5 accounts
- Encrypted credential storage
- Quick account switching
- Connection health monitoring

### Settings
- Risk parameters configuration
- Alert settings
- UI preferences

## Multi-Account Management

Add multiple MT5 accounts with encrypted storage:

```python
from core.account_manager import get_account_manager

manager = get_account_manager()

# Add account (credentials are encrypted)
manager.add_account(
    name="My Demo Account",
    login=12345678,
    password="secure_password",
    server="Broker-Demo"
)

# Switch between accounts
accounts = manager.list_accounts()
manager.switch_account(accounts[0].id)

# Connect to active account
manager.connect()
```

Or use the **Accounts** page in the UI for a visual interface.

## Advanced Risk Management

### Position Sizing
```python
# Formula: lot = (balance * risk%) / (sl_pips * pip_value)
lot_size = risk_manager.calculate_lot_size(
    symbol="XAUUSD",
    stop_loss_pips=50,
    risk_percent=2.0
)
```

### Circuit Breaker
Automatically pauses trading after consecutive losses:
```bash
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_CONSECUTIVE_LOSSES=3
CIRCUIT_BREAKER_COOLDOWN_MINUTES=60
```

### Risk Limits
```python
from core.risk_manager import RiskLimits

limits = RiskLimits(
    max_risk_per_trade=2.0,
    max_daily_loss=5.0,
    max_drawdown=20.0,
    max_positions=5,
    max_lot_size=1.0,
    max_correlated_exposure=3.0,
    circuit_breaker_losses=3
)
```

## Trade Execution Features

### Trailing Stop
```python
from core.trade_executor import get_trade_executor, TrailingStopConfig

executor = get_trade_executor()
executor.enable_trailing_stop(
    ticket=12345,
    config=TrailingStopConfig(
        activation_pips=30,
        trailing_distance_pips=20,
        step_pips=5
    )
)
```

### Break-Even
```python
from core.trade_executor import BreakEvenConfig

executor.set_break_even(
    ticket=12345,
    config=BreakEvenConfig(
        trigger_pips=20,
        offset_pips=2
    )
)
```

### Partial Close
```python
executor.partial_close(ticket=12345, percent=50)
```

## Adding New Strategies

### Step 1: Create Strategy File

Create `strategies/my_strategy.py`:

```python
from core.strategy_base import StrategyBase, Signal, TradeSignal, Position
import pandas as pd
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class MyConfirmation:
    """Track confirmations for signal quality."""
    condition_1: bool = False
    condition_2: bool = False

    @property
    def score(self) -> int:
        return sum([self.condition_1 * 2, self.condition_2 * 1])

    @property
    def quality(self) -> str:
        if self.score >= 3: return "A"
        elif self.score >= 2: return "B"
        else: return "C"

class MyStrategy(StrategyBase):
    name = "My Strategy"
    version = "1.0.0"
    description = "My custom trading strategy"

    def initialize(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.symbols = config.get("symbols", ["XAUUSD"])
        self.timeframe = config.get("timeframe", "M15")
        self.enabled = config.get("enabled", True)
        self.min_quality = config.get("filters", {}).get("min_quality", "B")

    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        confirmation = MyConfirmation()

        # Your entry logic
        confirmation.condition_1 = your_check_1(data)
        confirmation.condition_2 = your_check_2(data)

        # Check minimum quality
        quality_order = {"A": 3, "B": 2, "C": 1}
        if quality_order.get(confirmation.quality, 0) < quality_order.get(self.min_quality, 2):
            return None

        if confirmation.condition_1:
            return TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=data.iloc[-1]["close"],
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                comment=f"MyStrategy_BUY_{confirmation.quality}"
            )
        return None

    def should_close(self, position: Position, data: pd.DataFrame) -> bool:
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

filters:
  min_quality: "B"
  use_adx: true
  adx_threshold: 20

risk:
  max_risk_percent: 2.0
  lot_size: 0.01

session:
  start_hour: 8
  end_hour: 18
  trade_friday: false
```

### Step 3: Register Strategy

Add to `strategies/__init__.py`:

```python
from .my_strategy import MyStrategy

STRATEGY_REGISTRY = {
    # ... existing strategies
    "My Strategy": MyStrategy,
}
```

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `MT5_LOGIN` | MT5 account number | - |
| `MT5_PASSWORD` | MT5 password | - |
| `MT5_SERVER` | MT5 broker server | - |
| `ENCRYPTION_KEY` | Fernet key for credential encryption | Auto-generated |
| `MAX_RISK_PER_TRADE` | Max risk per trade (%) | 2.0 |
| `MAX_DAILY_LOSS` | Max daily loss (%) | 5.0 |
| `MAX_DRAWDOWN` | Max drawdown (%) | 20.0 |
| `CIRCUIT_BREAKER_CONSECUTIVE_LOSSES` | Losses before pause | 3 |
| `CIRCUIT_BREAKER_COOLDOWN_MINUTES` | Cooldown duration | 60 |
| `TRAILING_STOP_ENABLED` | Enable trailing stops | true |
| `BREAKEVEN_ENABLED` | Enable break-even | true |
| `TELEGRAM_ENABLED` | Enable Telegram alerts | false |
| `DISCORD_ENABLED` | Enable Discord alerts | false |

## Requirements

- Python 3.9+
- MetaTrader 5 terminal (Windows only for live trading)
- MT5 account with broker

## Dependencies

- MetaTrader5 (Windows)
- pandas, numpy
- streamlit, plotly
- cryptography (Fernet encryption)
- pyyaml, python-dotenv
- python-telegram-bot
- requests
- ta (technical analysis)
- loguru
- pytz

## Risk Warning

Trading involves significant risk of loss. This software is for educational purposes. Always:

- Test on demo accounts first
- Use conservative risk settings (1-2% per trade)
- Never risk more than you can afford to lose
- Past performance doesn't guarantee future results

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Disclaimer:** Trading involves significant risk. Use at your own risk.

## Support

For issues and feature requests, create an issue on GitHub.

## Changelog

### v2.0.0
- Added multi-account management with encrypted storage
- New professional trading dashboard with live charts
- Strategy builder page for visual strategy creation
- Advanced trade executor (trailing stops, break-even, partial close)
- Enhanced risk manager (circuit breaker, correlation limits)
- Signal quality scoring for all strategies
- Strategy comparison in backtesting
- Cross-platform support (mock MT5 for macOS/Linux development)
