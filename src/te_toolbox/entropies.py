"""Contains all the entropy and derived measures."""

from functools import lru_cache
from typing import overload

import numpy as np
import numpy.typing as npt

MATRIX_DIMS = 2
VECTOR_DIMS = 1


@lru_cache(maxsize=1024)
def _discretize_1d_data(
    data: tuple[np.float64], bins: int | tuple[float, ...]
) -> tuple[npt.NDArray[np.int64], int]:
    """Convert dataset into discrete classes.

    Note: Values equal to outer bin edges handling:
    - Values equal to leftmost edge go into first bin
    - Values equal to rightmost edge go into last bin
    """
    data_array = np.array(data)
    if isinstance(bins, int):
        edges = np.linspace(data_array.min(), data_array.max(), bins + 1)
    else:
        if data_array.min() < bins[0] or data_array.max() > bins[-1]:
            raise ValueError("Data contains values outside of specified bin range")
        edges = bins

    # Subtract 1 as digitize is 1 indexed
    indices = np.digitize(data_array, edges, right=False) - 1

    n_bins = len(edges) - 1

    # Make rightmost bin edge inclusive
    indices = np.where(indices == n_bins, n_bins - 1, indices)
    return indices, len(edges) - 1


@lru_cache(maxsize=1024)
def _discretize_nd_data(
    data_tuple: tuple[tuple[float, ...], ...],
    bins_tuple: tuple[int | tuple[float, ...], ...],
) -> tuple[tuple[npt.NDArray[np.int64], int], ...]:
    """Convert multiple variables into discrete classes.

    Args:
        data_tuple: Tuple of data arrays, one per variable
        bins_tuple: Tuple of bin specifications, one per variable

    Returns:
        Tuple of (indices, n_bins) pairs, one per variable

    """
    return tuple(
        _discretize_1d_data(d, b) for d, b in zip(data_tuple, bins_tuple, strict=True)
    )


def _discrete_univariate_entropy(
    data: npt.NDArray[np.int64], n_classes: list[int], at: int
) -> np.float64:
    n_steps = data.shape[0]
    p = np.bincount(data[:, at], minlength=n_classes[at]) / n_steps
    nonzero = p > 0
    return -np.sum(p[nonzero] * np.log(p[nonzero]))


@overload
def discrete_entropy(
    data: npt.NDArray[np.int64], n_classes: int | list[int], at: int
) -> np.float64: ...


@overload
def discrete_entropy(
    data: npt.NDArray[np.int64], n_classes: int | list[int], at: None
) -> npt.NDArray[np.float64]: ...


def discrete_entropy(
    data: npt.NDArray[np.int64], n_classes: int | list[int], at: int | None = None
) -> npt.NDArray[np.float64] | np.float64:
    """Calculate the discrete entropy from class assignments."""
    data = data.reshape(-1, 1) if data.ndim == 1 else data
    _, n_vars = data.shape

    if isinstance(n_classes, int):
        n_classes = [n_classes] * n_vars

    if at is not None:
        return _discrete_univariate_entropy(data, n_classes, at)
    else:
        probs = np.empty(n_vars)
        for i in range(n_vars):
            probs[i] = _discrete_univariate_entropy(data, n_classes, i)

        return probs


@overload
def entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: int,
) -> np.float64: ...


@overload
def entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: None,
) -> npt.NDArray[np.float64]: ...


def entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: int | None = None,
) -> npt.NDArray[np.float64] | np.float64:
    """Calculate the entropy of one or more datasets.

    Args:
    ----
        data: Input data array. Can be 1D or 2D [timesteps x variables].
        bins: Number of bins for histogram or list of bin edges.
        at: index if only univariate entropy should be computed.

    Returns:
    -------
        float: Entropy value for 1D input
        ndarray: Array of entropy values for 2D input, one per variable

    Raises:
    ------
        ValueError: If data dimensions are invalid

    """
    if data.size == 0:
        raise ValueError("Cannot compute entropy of empty array")
    if data.ndim > MATRIX_DIMS or data.ndim < VECTOR_DIMS:
        raise ValueError(
            "Wrong data format."
            "Data must be of dimension [timesteps] or [timesteps x variables]"
        )

    data = data.reshape(-1, 1) if data.ndim == 1 else data
    n_vars = data.shape[1]

    if isinstance(bins, int | np.ndarray):
        bins = [bins] * n_vars

    data_tuple = tuple(tuple(data[:, i]) for i in range(n_vars))
    bins_tuple = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuple, bins_tuple)
    indices = np.column_stack([d[0] for d in discretized])
    n_classes = [d[1] for d in discretized]

    return discrete_entropy(indices, n_classes, at)


def _discrete_bivariate_joint_entropy(
    data: npt.NDArray[np.int64], n_classes: list[int], at: tuple[int, int]
) -> np.float64:
    i, j = at
    n_steps, _ = data.shape
    hist = np.zeros((n_classes[i], n_classes[j]))
    np.add.at(hist, (data[:, i], data[:, j]), 1)
    p_xy = hist / n_steps
    nonzero_mask = p_xy > 0
    return -np.sum(p_xy[nonzero_mask] * np.log(p_xy[nonzero_mask]))


@overload
def discrete_joint_entropy(
    data: npt.NDArray[np.int64],
    n_classes: list | list[int],
    at: None,
) -> npt.NDArray[np.float64]: ...


@overload
def discrete_joint_entropy(
    data: npt.NDArray[np.int64],
    n_classes: list | list[int],
    at: tuple[int, int],
) -> np.float64: ...


def discrete_joint_entropy(
    data: npt.NDArray[np.int64],
    n_classes: list | list[int],
    at: tuple[int, int] | None = None,
) -> npt.NDArray[np.float64] | np.float64:
    """Calculate the pairwise discrete joint entropy from class assignments."""
    if data.ndim != MATRIX_DIMS:
        raise ValueError(
            "Need 2 dimensional array [timesteps x variables] "
            "to calculate pairwise discrete joint entropy."
        )
    _, n_vars = data.shape
    if isinstance(n_classes, int):
        n_classes = [n_classes] * n_vars

    if at is not None:
        return _discrete_bivariate_joint_entropy(data, n_classes, at)

    jent = np.zeros((n_vars, n_vars))
    for i in range(n_vars):
        for j in range(i, n_vars):
            jent[i, j] = jent[j, i] = _discrete_bivariate_joint_entropy(
                data, n_classes, (i, j)
            )
    return jent


@overload
def joint_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: tuple[int, int],
) -> np.float64: ...


@overload
def joint_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: None,
) -> npt.NDArray[np.float64]: ...


def joint_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: tuple[int, int] | None = None,
) -> npt.NDArray[np.float64] | np.float64:
    """Calculate pairwise joint entropy between all variables in the dataset.

    Args:
    ----
        data: Input data array of shape [timesteps x variables].
        bins: Number of bins or bin edges. Can be:
            - int: Same number of bins for all variables
            - [int, int]: Different number of bins for each variable
            - array: Bin edges for all variables
            - [array, array]: Different bin edges for each variable
        at: Tuple of index pair if only that index should be computed.

    Returns:
    -------
        ndarray: Matrix of shape [n_variables, n_variables] containing joint entropies.
            Entry [i,j] is the joint entropy H(X_i, X_j).
        float: If at parameter is set

    Raises:
    ------
        ValueError: If data has invalid dimensions or single variable.

    """
    if data.ndim != MATRIX_DIMS:
        raise ValueError("Data must be 2-dimensional [timesteps x variables]")
    _, n_vars = data.shape

    if isinstance(bins, int | np.ndarray):
        bins = [bins] * n_vars

    # Convert to tuples for hashing
    data_tuple = tuple(tuple(data[:, i]) for i in range(n_vars))
    bins_tuple = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuple, bins_tuple)
    indices = np.column_stack([d[0] for d in discretized])
    n_classes = [d[1] for d in discretized]
    return discrete_joint_entropy(indices, n_classes, at)


def discrete_multivar_joint_entropy(
    classes: list[npt.NDArray[np.int64]],
    n_classes: list[int],
) -> np.float64:
    """Calculate joint entropy from discrete classes for multiple variables."""
    n_steps = classes[0].shape
    hist = np.zeros(n_classes)

    idx = tuple(c for c in classes)
    np.add.at(hist, idx, 1)

    p = hist / n_steps
    nonzero_mask = p > 0
    return -np.sum(p[nonzero_mask] * np.log(p[nonzero_mask]))


def multivar_joint_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
) -> np.float64:
    """Calculate joint entropy for n variables.

    Args:
    ----
        data: Input array of shape [timesteps x variables].
        bins: Number of bins for all, for each, or list of bin edges for histogram.

    Returns:
    -------
        float: Joint entropy value H(X1,...,Xn).

    """
    if isinstance(bins, int | np.ndarray):
        bins = [bins] * data.shape[1]

    # Convert data and bins to hashable tuples for caching
    data_tuples = tuple(tuple(col) for col in data.T)
    bins_tuples = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuples, bins_tuples)
    classes = [d[0] for d in discretized]
    n_classes = [d[1] for d in discretized]

    return discrete_multivar_joint_entropy(classes, n_classes)


@overload
def conditional_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: tuple[int, int],
) -> np.float64: ...


@overload
def conditional_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: None,
) -> npt.NDArray[np.float64]: ...


def conditional_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    at: tuple[int, int] | None = None,
) -> npt.NDArray[np.float64] | np.float64:
    """Calculate conditional entropy between all pairs of variables.

    Uses the chain rule: H(Y|X) = H(X,Y) - H(X)

    Args:
    ----
        data: Input data array or DataFrame of shape [timesteps x variables].
        bins: Number of bins or bin edges (same formats as joint_entropy).
        at: Tuple of index pair if only that combination should be computed.

    Returns:
    -------
        ndarray: Matrix of shape [n_variables, n_variables] containing
            conditional entropies. Entry [i,j] is the conditional entropy H(X_i|X_j).
        float: if at is set.

    Raises:
    ------
        ValueError: If data has invalid dimensions or single variable.

    """
    if data.ndim < MATRIX_DIMS:
        raise ValueError(
            "Need more than 2 time series to calculate conditional entropy"
        )
    if at is not None:
        h_xy = joint_entropy(data, bins, at)
        h_x = entropy(data, bins, at=at[1])

        return h_xy - h_x
    else:
        h_xy = joint_entropy(data, bins)
        h_x = entropy(data, bins)
        return h_xy - h_x.reshape(1, -1)


def mutual_information(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    norm: bool = True,
) -> npt.NDArray[np.float64]:
    """Calculate mutual information of time series.

    Args:
    ----
        data: Input data array of shape [timesteps x variables].
        bins: Number of bins or bin edges for histogram approximation of PDF.
        norm: Whether to normalize result between 0 and 1 using I(X,Y)/sqrt(H(X)*H(Y)).

    Returns:
    -------
        ndarray: Matrix of shape [n_variables, n_variables] containing
            mutual information values. Entry [i,j] is I(X_i,X_j).

    Raises:
    ------
        ValueError: If data has invalid dimensions or single variable.

    """
    if data.ndim == 1:
        raise ValueError("Cannot compute mutual information with single variable.")

    dim = data.shape[1]
    h_xy = joint_entropy(data, bins)
    h_x = entropy(data, bins)

    i, j = np.meshgrid(range(dim), range(dim))

    mi = h_x[i] + h_x[j] - h_xy[i, j]
    if norm:
        mi = np.divide(mi, np.sqrt(np.multiply(h_x[i], h_x[j])))

    return mi


def prepare_te_data(
    data: npt.NDArray[np.float64],
    lag: int,
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
) -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    list[int | npt.NDArray[np.float64]],
]:
    """Prepare data arrays and bins for transfer entropy calculation.

    Args:
    ----
        data: Input data array of shape [timesteps x variables].
        lag: Time lag for analysis.
        bins: Number of bins (int), bin edges, or list of per variable bin
              edges for histogram.

    Returns:
    -------
        tuple: (current data, lagged data, bin list)

    Raises:
    ------
        ValueError: If data dimensions are invalid.

    """
    if data.ndim != MATRIX_DIMS:
        raise ValueError("Data must be 2-dimensional [timesteps x variables]")
    if isinstance(bins, list) and len(bins) != data.shape[1]:
        raise ValueError(
            f"Bin specifications ({len(bins)}) must match variables ({data.shape[1]}). "
            "Provide either: a single integer for uniform bins, "
            "a list of integers for variable-specific bin counts, "
            "or a list of arrays defining bin edges for each variable."
        )

    dim = data.shape[1]
    bins = [bins] * dim if isinstance(bins, int) else bins
    return data[lag:], data[:-lag], bins


def discrete_transfer_entropy(
    classes: npt.NDArray[np.int64], n_classes: int | list[int], lag: int
) -> npt.NDArray[np.float64]:
    """Calculate transfer entropy between all pairs of discrete variables.

    Args:
        classes: Array of discrete state indices [timesteps x variables]
        n_classes: Number of bins for each variable
        lag: Time lag for analysis

    Returns:
        Matrix containing transfer entropy values. Entry [i,j] is TE from X_j to X_i.

    """
    if isinstance(n_classes, int):
        n_classes = [n_classes] * classes.shape[1]

    current = classes[lag:]
    lagged = classes[:-lag]

    dim = current.shape[1]
    tent = np.zeros((dim, dim))

    h_xy_lag = discrete_joint_entropy(lagged, n_classes)
    h_x_lag = discrete_entropy(lagged, n_classes)

    for i in range(dim):
        at = (0, 1)
        h_y_ylag = discrete_joint_entropy(
            np.column_stack([current[:, i], lagged[:, i]]),
            [n_classes[i], n_classes[i]],
            at=at,
        )
        for j in range(dim):
            h_y_ylag_xlag = discrete_multivar_joint_entropy(
                [current[:, i], lagged[:, i], lagged[:, j]],
                [n_classes[i], n_classes[i], n_classes[j]],
            )
            tent[i, j] = h_y_ylag + h_xy_lag[i, j] - h_y_ylag_xlag - h_x_lag[i]
    return tent


def transfer_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    lag: int,
) -> npt.NDArray[np.float64]:
    """Calculate transfer entropy between all pairs of variables.

    Args:
    ----
        data: Input array of shape [timesteps x variables].
        bins: Number of bins or bin edges for histogram.
        lag: Time lag for analysis.

    Returns:
    -------
        ndarray: Matrix of shape [n_variables, n_variables] containing transfer
            entropy values. Entry [i,j] is the transfer entropy from X_j to X_i.

    """
    n_vars = data.shape[1]

    if isinstance(bins, int | np.ndarray):
        bins = [bins] * n_vars

    data_tuple = tuple(tuple(data[:, i]) for i in range(n_vars))
    bins_tuple = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuple, bins_tuple)
    indices = np.column_stack([d[0] for d in discretized])
    n_classes = [d[1] for d in discretized]

    return discrete_transfer_entropy(indices, n_classes, lag)


def normalized_transfer_entropy(
    data: npt.NDArray[np.float64],
    bins: int | list[int | npt.NDArray[np.float64]] | npt.NDArray[np.float64],
    lag: int,
) -> npt.NDArray[np.float64]:
    """Calculate normalized transfer entropy between variables.

    Normalized as: 1 - H(Y_t | Y_t_lag, X_t_lag) / H(Y_t | Y_t_lag)
    where H(Y_t | Y_t_lag, X_t_lag) = H(Y_t, Y_t_lag, X_t_lag) - H(Y_t_lag, X_t_lag)
    and H(Y_t | Y_t_lag) = H(Y_t, Y_t_lag) - H(Y_t_lag).

    Args:
    ----
        data: Input array of shape [timesteps x variables].
        bins: Number of bins or bin edges for histogram.
        lag: Time lag for analysis.

    Returns:
    -------
        ndarray: Matrix of shape [n_variables, n_variables] containing normalized
            transfer entropy values. Entry [i,j] is between 0 and 1.

    Raises:
    ------
        ValueError: If data dimensions are invalid.

    """
    n_steps, n_vars = data.shape
    if isinstance(bins, int | np.ndarray):
        bins = [bins] * n_vars

    data_tuple = tuple(tuple(data[:, i]) for i in range(n_vars))
    bins_tuple = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuple, bins_tuple)
    indices = np.column_stack([d[0] for d in discretized])
    n_classes = [d[1] for d in discretized]

    return discrete_normalized_transfer_entropy(indices, n_classes, lag)


def discrete_normalized_transfer_entropy(
    classes: npt.NDArray[np.int64], n_classes: int | list[int], lag: int
) -> npt.NDArray[np.float64]:
    """Calculate H-normalized transfer entropy between discrete variables.

    Normalized as: 1 - H(Y_t | Y_t_lag, X_t_lag) / H(Y_t | Y_t_lag)

    Args:
        classes: Array of discrete state indices [timesteps x variables]
        n_classes: Number of bins for each variable
        lag: Time lag for analysis

    Returns:
        Matrix containing normalized transfer entropy values.
        Entry [i,j] is normalized TE from X_j to X_i.

    """
    n_steps, n_vars = classes.shape

    if isinstance(n_classes, int):
        n_classes = [n_classes] * n_vars

    current = classes[lag:]
    lagged = classes[:-lag]

    ntent = np.zeros((n_vars, n_vars))

    h_xy_lag = discrete_joint_entropy(lagged, n_classes)
    h_x_lag = discrete_entropy(lagged, n_classes)

    for i in range(n_vars):
        at = (0, 1)
        h_y_ylag = discrete_joint_entropy(
            np.column_stack([current[:, i], lagged[:, i]]),
            [n_classes[i], n_classes[i]],
            at=at,
        )
        for j in range(n_vars):
            h_y_ylag_xlag = discrete_multivar_joint_entropy(
                [current[:, i], lagged[:, i], lagged[:, j]],
                [n_classes[i], n_classes[i], n_classes[j]],
            )
            h_y_given_ylag_xlag = h_y_ylag_xlag - h_xy_lag[i, j]
            h_y_given_ylag = h_y_ylag - h_x_lag[i]
            ntent[i, j] = (
                1 - h_y_given_ylag_xlag / h_y_given_ylag if h_y_given_ylag != 0 else 0
            )
    return ntent


def discrete_logn_normalized_transfer_entropy(
    classes: npt.NDArray[np.int64], n_classes: int | list[int], lag: int
) -> npt.NDArray[np.float64]:
    """Calculate transfer entropy normalized by log(N) between discrete variables.

    Args:
        classes: Array of discrete state indices [timesteps x variables]
        n_classes: Number of bins for each variable
        lag: Time lag for analysis

    Returns:
        Matrix containing logN-normalized transfer entropy values.
        Entry [i,j] is normalized TE from X_j to X_i.

    """
    te = discrete_transfer_entropy(classes, n_classes, lag)

    if isinstance(n_classes, int):
        te /= np.log(n_classes)
    else:
        for i in range(te.shape[0]):
            te[i] /= np.log(n_classes[i])

    return te


def logn_normalized_transfer_entropy(
    data: npt.NDArray[np.float64],
    bins: int | npt.NDArray[np.float64] | list[int | npt.NDArray[np.float64]],
    lag: int,
) -> npt.NDArray[np.float64]:
    """Calculate transfer entropy normalized by log(N) where N is number of bins.

    Args:
        data: Input array of shape [timesteps x variables]
        bins: Number of bins or bin edges for histogram
        lag: Time lag for analysis

    Returns:
        Matrix containing logN-normalized transfer entropy values.
        Entry [i,j] represents normalized TE from X_j to X_i.

    """
    n_vars = data.shape[1]

    if isinstance(bins, int | np.ndarray):
        bins = [bins] * n_vars

    # Convert to tuples for caching
    data_tuple = tuple(tuple(data[:, i]) for i in range(n_vars))
    bins_tuple = tuple(b if isinstance(b, int) else tuple(b) for b in bins)

    discretized = _discretize_nd_data(data_tuple, bins_tuple)
    indices = np.column_stack([d[0] for d in discretized])
    n_classes = [d[1] for d in discretized]

    return discrete_logn_normalized_transfer_entropy(indices, n_classes, lag)
