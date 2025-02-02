"""Dataset builder for the futures data frame."""

from datetime import datetime
from pathlib import Path

import polars as pl

from .columns import Cols


class FuturesDataBuilder:
    """Polars DataFrame wrapper that contains wrangling utilities."""

    def __init__(self, df: pl.DataFrame):
        """Wrap data frame in builder."""
        self.df = df

    @classmethod
    def load(cls, path: Path) -> "FuturesDataBuilder":
        """Load csv into builder."""
        return FuturesDataBuilder(pl.read_csv(path, has_header=True))

    def with_datetime_index(self) -> "FuturesDataBuilder":
        """Coerce the date column to a datetime index."""
        df = self.df.with_columns(
            pl.col(Cols.Date).str.strptime(pl.Date, format="%Y-%m-%d %H:%M:%S")
        )
        return FuturesDataBuilder(df)

    def drop_cols(self, columns: list[str]) -> "FuturesDataBuilder":
        """Drop columns in argument list."""
        return FuturesDataBuilder(self.df.drop(columns))

    def drop_nans(self) -> "FuturesDataBuilder":
        """Drop NaN rows."""
        return FuturesDataBuilder(self.df.drop_nans())

    def drop_nulls(self) -> "FuturesDataBuilder":
        """Drop null rows."""
        return FuturesDataBuilder(self.df.drop_nulls())

    def log_returns(self) -> "FuturesDataBuilder":
        """Create log returns column."""
        df = self.df
        for instrument in Cols.all_instruments:
            df = df.with_columns(
                pl.col(instrument.close_returns_5m)
                .add(1)
                .log()
                .alias(instrument.log_returns_5m)
            )
        return FuturesDataBuilder(df)

    def drop_ticks(self) -> "FuturesDataBuilder":
        """Drop ticks columns (they contain many NANs in raw data)."""
        df = self.df
        for instrument in Cols.all_instruments:
            df = (
                df.drop(instrument.ticks_5m)
                if instrument.ticks_5m in df.columns
                else df
            )
        return FuturesDataBuilder(df)

    def drop_incomplete_trading_days(self, min_bars: int) -> "FuturesDataBuilder":
        """Drop all rows from dates taht have fewer than min_bars observations.

        Args:
        ----
            min_bars: minimum number of rows per date (274 is a full trading day)

        """
        count_col = "count"
        valid_dates = (
            self.df.group_by(pl.col(Cols.Date).dt.date())
            .agg(pl.len().alias(count_col))
            .filter(pl.col(count_col) >= min_bars)
            .get_column(Cols.Date)
        )

        return FuturesDataBuilder(
            self.df.filter(pl.col(Cols.Date).dt.date().is_in(valid_dates))
        )

    def slice_after(self, timestamp: datetime) -> "FuturesDataBuilder":
        """Take all rows after timestamp (inclusive)."""
        df = self.df.filter(pl.col(Cols.Date) >= timestamp)
        return FuturesDataBuilder(df)

    def slice_before(self, timestamp: datetime) -> "FuturesDataBuilder":
        """Take all rows before timestamp (inclusive)."""
        df = self.df.filter(pl.col(Cols.Date) <= timestamp)
        return FuturesDataBuilder(df)

    def volume_weighted_close(self) -> "FuturesDataBuilder":
        """Create volume weighted close columns."""
        df = self.df
        for instrument in Cols.all_instruments:
            df = df.with_columns(
                (
                    pl.col(instrument.close_returns_5m) * pl.col(instrument.volume_5m)
                ).alias(instrument.volume_weighted)
            )
        return FuturesDataBuilder(df)

    def volatility(self, window: int = 20) -> "FuturesDataBuilder":
        """Create volatility columns."""
        df = self.df
        for instrument in Cols.all_instruments:
            df = df.with_columns(
                pl.col(instrument.log_returns_5m)
                .rolling_std(window)
                .alias(instrument.volatility)
            )
        return FuturesDataBuilder(df)

    def build(self) -> pl.DataFrame:
        """Unwrap the dataframe from builder."""
        return self.df
