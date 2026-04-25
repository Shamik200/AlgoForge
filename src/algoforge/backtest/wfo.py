"""Walk-Forward Optimization (WFO) logic."""

from typing import Iterator

import pandas as pd


def generate_expanding_windows(
    dataframe: pd.DataFrame, 
    train_size_bars: int, 
    test_size_bars: int
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate expanding train/test window boundaries for Walk-Forward Optimization.

    In an expanding window, the training set grows while the test set rolls forward.
    For example:
    Fold 1: Train [0 to 100], Test [100 to 150]
    Fold 2: Train [0 to 150], Test [150 to 200]
    Fold 3: Train [0 to 200], Test [200 to 250]

    Args:
        dataframe: The full chronological price dataframe.
        train_size_bars: The initial number of bars for the first training fold.
        test_size_bars: The number of bars for each test fold.

    Yields:
        Tuples of (train_df, test_df)
    """
    total_len = len(dataframe)
    if total_len <= train_size_bars + test_size_bars:
        # Not enough data for even one fold
        yield dataframe.iloc[:train_size_bars], dataframe.iloc[train_size_bars:]
        return

    current_train_end = train_size_bars

    while current_train_end + test_size_bars <= total_len:
        train_df = dataframe.iloc[0:current_train_end]
        test_df = dataframe.iloc[current_train_end : current_train_end + test_size_bars]
        
        yield train_df, test_df
        
        # Expand the window by adding the test set to the next training set
        current_train_end += test_size_bars

    # Handle any remaining bars that don't fit perfectly into test_size_bars
    if current_train_end < total_len:
        train_df = dataframe.iloc[0:current_train_end]
        test_df = dataframe.iloc[current_train_end:total_len]
        yield train_df, test_df
