import numpy as np
import pandas as pd

from numba import jit
from numpy import ndarray
from pandas import DataFrame
from typing import Any, List

from empyricalRMT._validate import make_1d_array


class Compare:
    def __init__(
        self,
        curves: List[ndarray],
        labels: List[str],
        base_curve: ndarray = None,
        base_label: str = None,
    ):
        """Construct a Compare object for accessing various comparison methods.

        Parameters
        ----------
        curves: List[ndarray]
            A list of unidimensional numpy arrays of values to compare. For most
            comparison methods besides some piecewise / quantile comparison methods, the
            curves must have identical lengths.
        labels: List[str]
            A list of strings identifying each curve. Must be the same length as curves,
            and labels[i] must be the label for curves[i], for all valid values of i.
        base_curve: ndarray
            The base curve against which each curve of `curves` will be compared, if the
            desire is to compare multiple curves only to one single curve.
        base_label: str
            The label for identifying the base_curve.
        """
        self.curves = [make_1d_array(curve) for curve in curves]
        self.labels = labels.copy()
        self.base_curve = make_1d_array(base_curve) if base_curve is not None else None
        self.base_label = base_label  # don't need to copy strings in Python
        self.__validate_curve_lengths()
        self.dict = dict(zip(self.labels, self.curves))

    def correlate(self) -> DataFrame:
        """Return the grid of correlations across curves. """
        self.__validate_curve_lengths(
            message="Comparing via correlation requires all curves have identical lengths",
            check_all_equal=True,
        )
        if self.base_curve is not None:
            # index with [0, 1:], since [0, :] give first row of correlations, and since
            # [0, 0] is just the correlation of the base_curve with itself
            data = np.corrcoef(self.base_curve, self.curves)[0, 1:]
            return pd.DataFrame(data=data, index=self.labels, columns=[self.base_label])
        data = np.corrcoef(self.curves)
        return pd.DataFrame(data=data, index=self.labels, columns=self.labels)

    def mean_sq_difference(self) -> DataFrame:
        """Return the grid of mean square differences across curves."""
        self.__validate_curve_lengths(
            message="Comparing via mean squared differences requires all curves have identical lengths",
            check_all_equal=True,
        )
        curves = np.array(self.curves)
        if self.base_curve is not None:
            diffs = np.empty(curves.shape[0])
            for i in range(len(diffs)):
                diffs[i] = np.mean((self.base_curve - curves[i]) ** 2)
                return pd.DataFrame(
                    data=diffs, index=self.labels, columns=[self.base_label]
                )
        data = self.__fast_msqd(curves)
        return pd.DataFrame(data=data, index=self.labels, columns=self.labels)

    def mean_abs_difference(self) -> DataFrame:
        """Return the grid of mean absolute differences across curves."""
        self.__validate_curve_lengths(
            message="Comparing via mean absolute differences requires all curves have identical lengths",
            check_all_equal=True,
        )
        curves = np.array(self.curves)
        if self.base_curve is not None:
            diffs = np.empty(curves.shape[0])
            for i in range(len(diffs)):
                diffs[i] = np.mean(np.abs(self.base_curve - curves[i]))
                return pd.DataFrame(
                    data=diffs, index=self.labels, columns=[self.base_label]
                )
        data = self.__fast_mad(curves)
        return pd.DataFrame(data=data, index=self.labels, columns=self.labels)

    def _test_validate(self, **kwargs: Any) -> None:
        self.__validate_curve_lengths(**kwargs)

    @staticmethod
    @jit(nopython=True, fastmath=True)
    def __fast_msqd(curves: ndarray) -> ndarray:
        n = curves.shape[0]
        data = np.empty((n, n), dtype=np.float64)
        for j in range(n):
            for i in range(n):
                data[i, j] = np.mean((curves[i] - curves[j]) ** 2)
        return data

    @staticmethod
    @jit(nopython=True, fastmath=True)
    def __fast_mad(curves: ndarray) -> ndarray:
        n = curves.shape[0]
        data = np.empty((n, n), dtype=np.float64)
        for j in range(n):
            for i in range(n):
                data[i, j] = np.mean(np.abs(curves[i] - curves[j]))
        return data

    def __validate_curve_lengths(
        self, message: str = None, check_all_equal: bool = False
    ) -> None:
        curves = self.curves
        labels = self.labels

        if len(curves) <= 1:
            raise ValueError("There must be more than one curve to compare.")
        if len(self.curves) != len(labels):
            raise ValueError("`labels` must have the same length as `curves`.")

        all_equal = np.all([len(curve) == len(curves[0]) for curve in curves])
        if check_all_equal:
            if self.base_curve is not None and self.base_label is not None:
                if len(curves[0]) != len(self.base_curve):
                    raise ValueError(message)
            if not all_equal:
                raise ValueError(message)
