"""Purged Walk-Forward Cross-Validation.

From Marcos López de Prado's 'Advances in Financial Machine Learning'.
Standard k-fold is ILLEGAL in time series — it leaks future information.
Purged walk-forward adds a gap between train and test to prevent label leakage.
"""

from typing import Iterator


def purged_walk_forward_split(
    n_samples: int,
    train_size: int,
    test_size: int,
    purge_gap: int = 5,
) -> Iterator[tuple[tuple[int, int], tuple[int, int]]]:
    """Generate purged walk-forward train/test split boundaries.

    The purge gap eliminates samples between train and test sets where
    the label calculation window could overlap, preventing information leakage.

    Example with purge_gap=5:
    Fold 1: Train [0, 200], PURGE [200, 205], Test [205, 255]
    Fold 2: Train [0, 255], PURGE [255, 260], Test [260, 310]

    Args:
        n_samples: Total number of samples.
        train_size: Initial training set size.
        test_size: Size of each test set.
        purge_gap: Number of samples to purge between train and test.
                   Should equal the forward return horizon.

    Yields:
        Tuples of ((train_start, train_end), (test_start, test_end)).
    """
    current_train_end = train_size

    while current_train_end + purge_gap + test_size <= n_samples:
        train_bounds = (0, current_train_end)
        test_start = current_train_end + purge_gap
        test_end = test_start + test_size
        test_bounds = (test_start, test_end)

        yield train_bounds, test_bounds

        # Expand training set to include the previous test set
        current_train_end = test_end

    # Handle remaining data
    if current_train_end + purge_gap < n_samples:
        train_bounds = (0, current_train_end)
        test_start = current_train_end + purge_gap
        test_bounds = (test_start, n_samples)
        yield train_bounds, test_bounds
