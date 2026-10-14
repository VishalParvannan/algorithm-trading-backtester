from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Strategy(ABC):
    """
    Base class for all trading strategies.
    """

    @abstractmethod
    def generate_signals(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate trading signals.

        Returns a DataFrame containing at least:
        - signal
        """

        raise NotImplementedError


class MovingAverageStrategy(Strategy):
    """
    Long-only moving average crossover strategy.

    If the fast moving average is above the slow
    moving average, the strategy holds the asset.

    Otherwise, it holds cash.
    """

    def __init__(
        self,
        fast: int = 20,
        slow: int = 50,
    ):
        if fast <= 0 or slow <= 0:
            raise ValueError("Moving average periods must be positive.")

        if fast >= slow:
            raise ValueError(
                "Fast moving average must be smaller than slow."
            )

        self.fast = fast
        self.slow = slow

    def generate_signals(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        signals = data.copy()

        signals["fast_ma"] = (
            signals["Close"]
            .rolling(window=self.fast)
            .mean()
        )

        signals["slow_ma"] = (
            signals["Close"]
            .rolling(window=self.slow)
            .mean()
        )

        signals["signal"] = 0

        signals.loc[
            signals["fast_ma"] > signals["slow_ma"],
            "signal",
        ] = 1

        return signals


class MomentumStrategy(Strategy):
    """
    Momentum strategy.

    If the asset's return over the lookback period
    is positive, hold the asset.

    Otherwise, hold cash.
    """

    def __init__(self, lookback: int = 252):
        if lookback <= 0:
            raise ValueError("Lookback must be positive.")

        self.lookback = lookback

    def generate_signals(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        signals = data.copy()

        signals["momentum"] = (
            signals["Close"]
            .pct_change(self.lookback)
        )

        signals["signal"] = 0

        signals.loc[
            signals["momentum"] > 0,
            "signal",
        ] = 1

        return signals


class RSIStrategy(Strategy):
    """
    Long-only RSI mean-reversion strategy.

    Buy when RSI falls below oversold.
    Exit when RSI rises above overbought.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70,
    ):
        if period <= 0:
            raise ValueError("RSI period must be positive.")

        if not 0 < oversold < 100:
            raise ValueError("Oversold must be between 0 and 100.")

        if not 0 < overbought < 100:
            raise ValueError("Overbought must be between 0 and 100.")

        if oversold >= overbought:
            raise ValueError(
                "Oversold must be lower than overbought."
            )

        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        signals = data.copy()

        delta = signals["Close"].diff()

        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)

        average_gain = (
            gains
            .rolling(self.period)
            .mean()
        )

        average_loss = (
            losses
            .rolling(self.period)
            .mean()
        )

        rs = average_gain / average_loss

        signals["rsi"] = (
            100 - (100 / (1 + rs))
        )

        # NaN means hold the previous position; zero is an explicit exit.
        signals["signal"] = np.nan

        # Long when oversold
        signals.loc[
            signals["rsi"] < self.oversold,
            "signal",
        ] = 1

        # Exit when overbought
        signals.loc[
            signals["rsi"] > self.overbought,
            "signal",
        ] = 0

        # Carry forward previous position
        signals["signal"] = (
            signals["signal"]
            .ffill()
            .fillna(0)
            .astype(int)
        )

        return signals


class EMACrossoverStrategy(MovingAverageStrategy):
    """Long when the fast exponential average exceeds the slow average."""

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        signals["fast_ema"] = data.Close.ewm(span=self.fast, adjust=False, min_periods=self.fast).mean()
        signals["slow_ema"] = data.Close.ewm(span=self.slow, adjust=False, min_periods=self.slow).mean()
        signals["signal"] = (signals.fast_ema > signals.slow_ema).astype(int)
        return signals


class MACDStrategy(MovingAverageStrategy):
    """Long when MACD exceeds its signal line after the warm-up period."""

    def __init__(self, fast=12, slow=26, signal_period=9):
        super().__init__(fast, slow)
        if signal_period <= 0:
            raise ValueError("MACD signal period must be positive.")
        self.signal_period = signal_period

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        fast = data.Close.ewm(span=self.fast, adjust=False, min_periods=self.fast).mean()
        slow = data.Close.ewm(span=self.slow, adjust=False, min_periods=self.slow).mean()
        signals["macd"] = fast - slow
        signals["macd_signal"] = signals.macd.ewm(span=self.signal_period, adjust=False, min_periods=self.signal_period).mean()
        signals["signal"] = (signals.macd > signals.macd_signal).astype(int)
        return signals


class BollingerBandsStrategy(Strategy):
    """Enter below the lower band; exit at the rolling mean."""

    def __init__(self, period=20, std_dev=2.0):
        if period < 2 or not np.isfinite(std_dev) or std_dev <= 0:
            raise ValueError("Bollinger period must be at least 2 and deviation must be positive.")
        self.period, self.std_dev = period, std_dev

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        signals["middle_band"] = data.Close.rolling(self.period).mean()
        deviation = data.Close.rolling(self.period).std() * self.std_dev
        signals["lower_band"] = signals.middle_band - deviation
        signals["upper_band"] = signals.middle_band + deviation
        events = pd.Series(np.nan, index=data.index)
        events.loc[data.Close < signals.lower_band] = 1
        events.loc[data.Close >= signals.middle_band] = 0
        signals["signal"] = events.ffill().fillna(0).astype(int)
        return signals


class DonchianBreakoutStrategy(Strategy):
    """Close-based breakout using prior bars, with a shorter exit channel."""

    def __init__(self, entry_period=20, exit_period=10):
        if not 0 < exit_period < entry_period:
            raise ValueError("Breakout entry period must exceed the positive exit period.")
        self.entry_period, self.exit_period = entry_period, exit_period

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        signals["upper_channel"] = data.Close.rolling(self.entry_period).max().shift(1)
        signals["lower_channel"] = data.Close.rolling(self.exit_period).min().shift(1)
        events = pd.Series(np.nan, index=data.index)
        events.loc[data.Close > signals.upper_channel] = 1
        events.loc[data.Close < signals.lower_channel] = 0
        signals["signal"] = events.ffill().fillna(0).astype(int)
        return signals


class BuyAndHoldStrategy(Strategy):
    """Enter once on the first executable bar and remain invested."""

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        signals["signal"] = 1
        return signals
