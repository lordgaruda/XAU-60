"""
Dynamic Strategy Loader.
Auto-discovers and loads strategies from the strategies folder.
"""
import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Type, Optional, Any
import yaml
from loguru import logger

from .strategy_base import StrategyBase


class StrategyLoader:
    """
    Dynamically discovers and loads trading strategies.

    Strategies are auto-discovered from the strategies/ folder.
    Each strategy must:
    1. Inherit from StrategyBase
    2. Have a corresponding YAML config in config/strategies/
    """

    def __init__(self, strategies_dir: str = None, config_dir: str = None):
        """
        Initialize strategy loader.

        Args:
            strategies_dir: Path to strategies folder
            config_dir: Path to strategy configs folder
        """
        base_dir = Path(__file__).parent.parent
        self.strategies_dir = Path(strategies_dir) if strategies_dir else base_dir / "strategies"
        self.config_dir = Path(config_dir) if config_dir else base_dir / "config" / "strategies"

        self._strategies: Dict[str, StrategyBase] = {}
        self._strategy_classes: Dict[str, Type[StrategyBase]] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

    def discover_strategies(self) -> List[str]:
        """
        Discover all strategy modules in strategies folder.

        Returns:
            List of discovered strategy names
        """
        discovered = []

        if not self.strategies_dir.exists():
            logger.warning(f"Strategies directory not found: {self.strategies_dir}")
            return discovered

        # Add strategies dir to path for imports
        strategies_parent = str(self.strategies_dir.parent)
        if strategies_parent not in sys.path:
            sys.path.insert(0, strategies_parent)

        for file in self.strategies_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue

            module_name = file.stem

            try:
                # Import the module
                spec = importlib.util.spec_from_file_location(
                    f"strategies.{module_name}",
                    file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find strategy classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, StrategyBase) and
                        attr is not StrategyBase):

                        strategy_name = attr.name if hasattr(attr, 'name') else module_name
                        self._strategy_classes[strategy_name] = attr
                        discovered.append(strategy_name)
                        logger.info(f"Discovered strategy: {strategy_name}")

            except Exception as e:
                logger.error(f"Failed to load strategy module {module_name}: {e}")

        return discovered

    def load_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Load YAML configuration for a strategy.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Configuration dictionary or None
        """
        # Try different naming conventions
        possible_names = [
            strategy_name.lower().replace(" ", "_"),
            strategy_name.lower().replace(" ", "-"),
            strategy_name,
        ]

        for name in possible_names:
            config_file = self.config_dir / f"{name}.yaml"
            if config_file.exists():
                try:
                    with open(config_file, "r") as f:
                        config = yaml.safe_load(f)
                        self._configs[strategy_name] = config
                        logger.info(f"Loaded config for {strategy_name}")
                        return config
                except Exception as e:
                    logger.error(f"Failed to load config {config_file}: {e}")

        logger.warning(f"No config found for strategy: {strategy_name}")
        return None

    def load_strategy(self, strategy_name: str) -> Optional[StrategyBase]:
        """
        Load and initialize a single strategy.

        Args:
            strategy_name: Name of the strategy to load

        Returns:
            Initialized strategy instance or None
        """
        if strategy_name not in self._strategy_classes:
            logger.error(f"Strategy not found: {strategy_name}")
            return None

        strategy_class = self._strategy_classes[strategy_name]
        config = self.load_config(strategy_name)

        if config is None:
            # Use default config
            config = {
                "name": strategy_name,
                "enabled": True,
                "symbols": ["XAUUSD"],
                "timeframe": "M15",
                "parameters": {},
            }

        try:
            strategy = strategy_class()
            strategy.validate_config(config)
            strategy.initialize(config)
            strategy._initialized = True

            self._strategies[strategy_name] = strategy
            logger.info(f"Loaded strategy: {strategy}")
            return strategy

        except Exception as e:
            logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
            return None

    def load_all_strategies(self) -> Dict[str, StrategyBase]:
        """
        Discover and load all strategies.

        Returns:
            Dictionary of loaded strategies
        """
        self.discover_strategies()

        for strategy_name in self._strategy_classes:
            self.load_strategy(strategy_name)

        return self._strategies

    def get_strategy(self, name: str) -> Optional[StrategyBase]:
        """Get a loaded strategy by name."""
        return self._strategies.get(name)

    def get_all_strategies(self) -> Dict[str, StrategyBase]:
        """Get all loaded strategies."""
        return self._strategies.copy()

    def get_enabled_strategies(self) -> Dict[str, StrategyBase]:
        """Get all enabled strategies."""
        return {
            name: strategy
            for name, strategy in self._strategies.items()
            if strategy.enabled
        }

    def reload_strategy(self, strategy_name: str) -> Optional[StrategyBase]:
        """
        Reload a strategy (for hot-reload functionality).

        Args:
            strategy_name: Name of strategy to reload

        Returns:
            Reloaded strategy instance
        """
        # Remove existing strategy
        if strategy_name in self._strategies:
            del self._strategies[strategy_name]
        if strategy_name in self._strategy_classes:
            del self._strategy_classes[strategy_name]
        if strategy_name in self._configs:
            del self._configs[strategy_name]

        # Re-discover and reload
        self.discover_strategies()
        return self.load_strategy(strategy_name)

    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get the configuration for a strategy."""
        return self._configs.get(strategy_name)

    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Update and save strategy configuration.

        Args:
            strategy_name: Strategy to update
            config: New configuration

        Returns:
            True if successful
        """
        config_file = self.config_dir / f"{strategy_name.lower().replace(' ', '_')}.yaml"

        try:
            with open(config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            self._configs[strategy_name] = config

            # Reload strategy with new config
            if strategy_name in self._strategies:
                self._strategies[strategy_name].initialize(config)

            logger.info(f"Updated config for {strategy_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False

    def list_available_strategies(self) -> List[Dict[str, Any]]:
        """
        List all available strategies with their status.

        Returns:
            List of strategy info dictionaries
        """
        result = []
        for name, strategy in self._strategies.items():
            result.append({
                "name": name,
                "version": strategy.version,
                "description": strategy.description,
                "author": strategy.author,
                "enabled": strategy.enabled,
                "symbols": strategy.symbols,
                "timeframe": strategy.timeframe,
                "initialized": strategy._initialized,
            })
        return result
