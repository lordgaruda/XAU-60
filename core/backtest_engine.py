"""
Backtesting Engine for strategy testing on historical data.
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger

from .mt5_connector import MT5Connector
from .strategy_base import StrategyBase, Signal, TradeSignal, Position


@dataclass
class BacktestTrade:
    """Record of a backtested trade."""
    entry_time: datetime
    exit_time: datetime
    signal: Signal
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    profit: float
    profit_pips: float
    exit_reason: str


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_profit_pips: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    average_trade: float
    average_winner: float
    average_loser: float
    largest_winner: float
    largest_loser: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


class BacktestEngine:
    """
    Backtesting engine for strategy testing.

    Features:
    - Historical data from MT5
    - Realistic trade simulation
    - Performance metrics
    - Equity curve generation
    """

    def __init__(self, mt5: MT5Connector):
        """
        Initialize backtest engine.

        Args:
            mt5: MT5 connector for historical data
        """
        self.mt5 = mt5

    def run_backtest(
        self,
        strategy: StrategyBase,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000.0,
        lot_size: float = 0.1,
        spread_pips: float = 2.0,
        commission: float = 0.0
    ) -> Optional[BacktestResult]:
        """
        Run a backtest on historical data.

        Args:
            strategy: Strategy to test
            symbol: Symbol to test on
            timeframe: Timeframe for bars
            start_date: Start date
            end_date: End date
            initial_balance: Starting balance
            lot_size: Fixed lot size for trades
            spread_pips: Spread in pips to simulate
            commission: Commission per lot

        Returns:
            BacktestResult with all metrics
        """
        logger.info(f"Starting backtest: {strategy.name} on {symbol} {timeframe}")
        logger.info(f"Period: {start_date} to {end_date}")

        # Get historical data
        data = self.mt5.get_historical_data(symbol, timeframe, start_date, end_date)

        if data is None or len(data) == 0:
            logger.error("No historical data available")
            return None

        logger.info(f"Loaded {len(data)} bars")

        # Get symbol info for calculations
        symbol_info = self.mt5.get_symbol_info(symbol)
        point = symbol_info.point if symbol_info else 0.01
        pip_value = 10 * point  # Standard pip
        spread = spread_pips * pip_value

        # Initialize tracking variables
        balance = initial_balance
        equity_curve = [balance]
        trades: List[BacktestTrade] = []
        open_position: Optional[Dict] = None

        # Run through each bar
        for i in range(50, len(data)):  # Start at 50 for indicator warm-up
            current_bar = data.iloc[i]
            historical_data = data.iloc[:i+1].copy()

            # Check exit conditions for open position
            if open_position:
                exit_price, exit_reason = self._check_exit(
                    open_position, current_bar, strategy, historical_data
                )

                if exit_price:
                    # Calculate profit
                    if open_position["signal"] == Signal.BUY:
                        profit_pips = (exit_price - open_position["entry_price"]) / pip_value
                    else:
                        profit_pips = (open_position["entry_price"] - exit_price) / pip_value

                    profit = profit_pips * pip_value * lot_size * 100000 / 10  # Simplified P&L
                    profit -= commission * lot_size  # Subtract commission

                    # Record trade
                    trade = BacktestTrade(
                        entry_time=open_position["entry_time"],
                        exit_time=current_bar["time"],
                        signal=open_position["signal"],
                        entry_price=open_position["entry_price"],
                        exit_price=exit_price,
                        stop_loss=open_position["stop_loss"],
                        take_profit=open_position["take_profit"],
                        lot_size=lot_size,
                        profit=profit,
                        profit_pips=profit_pips,
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)

                    balance += profit
                    open_position = None

            # Check for new entry signal if no position
            if not open_position:
                signal = strategy.analyze(symbol, historical_data)

                if signal and signal.signal != Signal.HOLD:
                    # Apply spread to entry
                    if signal.signal == Signal.BUY:
                        entry_price = current_bar["close"] + spread
                    else:
                        entry_price = current_bar["close"] - spread

                    open_position = {
                        "signal": signal.signal,
                        "entry_price": entry_price,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "entry_time": current_bar["time"],
                    }

            # Track equity
            if open_position:
                # Calculate unrealized P&L
                if open_position["signal"] == Signal.BUY:
                    unrealized = (current_bar["close"] - open_position["entry_price"]) / pip_value
                else:
                    unrealized = (open_position["entry_price"] - current_bar["close"]) / pip_value
                equity = balance + (unrealized * pip_value * lot_size * 100000 / 10)
            else:
                equity = balance

            equity_curve.append(equity)

        # Close any remaining position at end
        if open_position:
            exit_price = data.iloc[-1]["close"]
            if open_position["signal"] == Signal.BUY:
                profit_pips = (exit_price - open_position["entry_price"]) / pip_value
            else:
                profit_pips = (open_position["entry_price"] - exit_price) / pip_value

            profit = profit_pips * pip_value * lot_size * 100000 / 10

            trade = BacktestTrade(
                entry_time=open_position["entry_time"],
                exit_time=data.iloc[-1]["time"],
                signal=open_position["signal"],
                entry_price=open_position["entry_price"],
                exit_price=exit_price,
                stop_loss=open_position["stop_loss"],
                take_profit=open_position["take_profit"],
                lot_size=lot_size,
                profit=profit,
                profit_pips=profit_pips,
                exit_reason="End of backtest",
            )
            trades.append(trade)
            balance += profit

        # Calculate metrics
        result = self._calculate_metrics(
            strategy_name=strategy.name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=balance,
            trades=trades,
            equity_curve=equity_curve,
        )

        logger.info(f"Backtest complete: {result.total_trades} trades, "
                    f"Win rate: {result.win_rate:.1f}%, P&L: {result.total_profit:.2f}")

        return result

    def _check_exit(
        self,
        position: Dict,
        bar: pd.Series,
        strategy: StrategyBase,
        data: pd.DataFrame
    ) -> Tuple[Optional[float], str]:
        """
        Check if position should be exited.

        Returns:
            Tuple of (exit_price, exit_reason) or (None, "")
        """
        high = bar["high"]
        low = bar["low"]

        # Check stop loss
        if position["signal"] == Signal.BUY:
            if low <= position["stop_loss"]:
                return position["stop_loss"], "Stop Loss"
            if high >= position["take_profit"]:
                return position["take_profit"], "Take Profit"
        else:
            if high >= position["stop_loss"]:
                return position["stop_loss"], "Stop Loss"
            if low <= position["take_profit"]:
                return position["take_profit"], "Take Profit"

        # Check strategy exit
        mock_position = Position(
            ticket=1,
            symbol="",
            type=position["signal"],
            volume=0.1,
            open_price=position["entry_price"],
            stop_loss=position["stop_loss"],
            take_profit=position["take_profit"],
            profit=0,
            magic_number=0,
            comment="",
            open_time=position["entry_time"],
        )

        if strategy.should_close(mock_position, data):
            return bar["close"], "Strategy Exit"

        return None, ""

    def _calculate_metrics(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float,
        final_balance: float,
        trades: List[BacktestTrade],
        equity_curve: List[float]
    ) -> BacktestResult:
        """Calculate backtest metrics."""

        if not trades:
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                final_balance=initial_balance,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_profit=0,
                total_profit_pips=0,
                max_drawdown=0,
                max_drawdown_percent=0,
                sharpe_ratio=0,
                profit_factor=0,
                average_trade=0,
                average_winner=0,
                average_loser=0,
                largest_winner=0,
                largest_loser=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                trades=[],
                equity_curve=equity_curve,
            )

        # Basic stats
        profits = [t.profit for t in trades]
        winning = [p for p in profits if p > 0]
        losing = [p for p in profits if p < 0]

        # Drawdown calculation
        peak = equity_curve[0]
        max_dd = 0
        max_dd_pct = 0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        # Consecutive wins/losses
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for p in profits:
            if p > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        # Sharpe ratio (simplified)
        if len(profits) > 1:
            returns = np.array(profits) / initial_balance
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        # Profit factor
        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 0
        pf = gross_profit / gross_loss if gross_loss > 0 else 0

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(trades) * 100,
            total_profit=sum(profits),
            total_profit_pips=sum(t.profit_pips for t in trades),
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_pct,
            sharpe_ratio=sharpe,
            profit_factor=pf,
            average_trade=np.mean(profits),
            average_winner=np.mean(winning) if winning else 0,
            average_loser=np.mean(losing) if losing else 0,
            largest_winner=max(winning) if winning else 0,
            largest_loser=min(losing) if losing else 0,
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            trades=trades,
            equity_curve=equity_curve,
        )

    def generate_report(self, result: BacktestResult) -> str:
        """
        Generate a text report from backtest results.

        Args:
            result: BacktestResult object

        Returns:
            Formatted report string
        """
        report = f"""
{'='*60}
BACKTEST REPORT: {result.strategy_name}
{'='*60}

Symbol:          {result.symbol}
Timeframe:       {result.timeframe}
Period:          {result.start_date.date()} to {result.end_date.date()}

{'='*60}
PERFORMANCE SUMMARY
{'='*60}

Initial Balance: ${result.initial_balance:,.2f}
Final Balance:   ${result.final_balance:,.2f}
Total Profit:    ${result.total_profit:,.2f} ({(result.total_profit/result.initial_balance)*100:.2f}%)
Total Pips:      {result.total_profit_pips:.1f}

{'='*60}
TRADE STATISTICS
{'='*60}

Total Trades:    {result.total_trades}
Winning Trades:  {result.winning_trades} ({result.win_rate:.1f}%)
Losing Trades:   {result.losing_trades}

Average Trade:   ${result.average_trade:,.2f}
Average Winner:  ${result.average_winner:,.2f}
Average Loser:   ${result.average_loser:,.2f}

Largest Winner:  ${result.largest_winner:,.2f}
Largest Loser:   ${result.largest_loser:,.2f}

{'='*60}
RISK METRICS
{'='*60}

Max Drawdown:    ${result.max_drawdown:,.2f} ({result.max_drawdown_percent:.2f}%)
Profit Factor:   {result.profit_factor:.2f}
Sharpe Ratio:    {result.sharpe_ratio:.2f}

Consecutive Wins:   {result.max_consecutive_wins}
Consecutive Losses: {result.max_consecutive_losses}

{'='*60}
"""
        return report
