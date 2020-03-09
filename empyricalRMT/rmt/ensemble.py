import numpy as np

from abc import ABC, abstractmethod
from numpy import ndarray
from scipy.special import gamma

from typing import Tuple, Union
from warnings import warn


class _Ensemble(ABC):
    """Base class for various ensembles."""

    @staticmethod
    @abstractmethod
    def nnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        pass

    @staticmethod
    @abstractmethod
    def nnnsd(
        spacings_range: Tuple[float, float] = (0.0, 4.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        pass

    @staticmethod
    @abstractmethod
    def spectral_rigidity(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        pass

    @staticmethod
    @abstractmethod
    def level_variance(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        pass


class Poisson(_Ensemble):
    """Class for Poisson "Gaussian Diagonal" matrices. """

    @staticmethod
    def nnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the nearest neighbour spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.
        """
        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[1], n_points)
        )
        return np.exp(-s)

    @staticmethod
    def nnnsd(
        spacings_range: Tuple[float, float] = (0.0, 4.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the next-nearest neighbour
        spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected next-nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.


        Notes
        -----
        I am not aware of the *actual* expected spacing distribution here, but
        from my simulations, the Brody distribution below appears to be close.
        """

        def brody_dist(s: ndarray, beta: float) -> ndarray:
            """See Eq. 8 of
            Dettmann, C. P., Georgiou, O., & Knight, G. (2017).
            Spectral statistics of random geometric graphs.
            EPL (Europhysics Letters), 118(1), 18003.
            """
            b1 = beta + 1
            alpha = gamma((beta + 2) / b1) ** b1
            return b1 * alpha * s ** beta * np.exp(-alpha * s ** b1)

        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[1], n_points)
        )
        warn(
            "The expected values returned from Poisson.nnnsd() are provided "
            "merely as a heuristic approximation. Take them with a grain of salt."
        )
        return brody_dist(s, 0.6)

    @staticmethod
    def spectral_rigidity(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the spectral rigidity.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the rigidity.

        max_L: float
            The largest L-value for which to compute the rigidity.

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the rigidity.

        L: ndarray
            The array of L values for which to compute the rigidity. Overrides
            other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        return L / 15 / 2

    @staticmethod
    def level_variance(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the level variance.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the level variance

        max_L: float
            The largest L-value for which to compute the level variance

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the level variance

        L: ndarray
            The array of L values for which to compute the level variance.
            Overrides other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        return s / 2


class GOE(_Ensemble):
    @staticmethod
    def nnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the nearest neighbour spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.
        """
        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[1], n_points)
        )
        p = np.pi
        return ((p * s) / 2) * np.exp(-(p / 4) * s * s)

    @staticmethod
    def nnnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the next-nearest neighbour
        spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected next-nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.

        Notes
        -----
        See Dettmann, C. P., Georgiou, O., & Knight, G. (2017). Spectral
        statistics of random geometric graphs. EPL (Europhysics Letters),
        118(1), 18003. doi:10.1209/0295-5075/118/18003, pp10, Equation. 11
        """
        # remember, we need to scale by the mean spacing, which in the case of
        # the *next* NNSD, is 2, and not 1. So divide by two below
        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[1], n_points) / 2
        )
        p = np.pi
        # fmt: off
        goe = (2**18 / (3**6 * p**3)) * (s**4) * np.exp(-((64 / (9 * p)) * (s * s)))
        # fmt: on
        return goe

    @staticmethod
    def spectral_rigidity(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the spectral rigidity.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the rigidity.

        max_L: float
            The largest L-value for which to compute the rigidity.

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the rigidity.

        L: ndarray
            The array of L values for which to compute the rigidity. Overrides
            other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        p, y = np.pi, np.euler_gamma
        return (1 / (p ** 2)) * (np.log(2 * p * s) + y - 5 / 4 - (p ** 2) / 8)

    @staticmethod
    def level_variance(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the level variance.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the level variance

        max_L: float
            The largest L-value for which to compute the level variance

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the level variance

        L: ndarray
            The array of L values for which to compute the level variance.
            Overrides other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        p = np.pi
        return (2 / (p ** 2)) * (np.log(2 * p * s) + np.euler_gamma + 1 - (p ** 2) / 8)


class GUE(_Ensemble):
    @staticmethod
    def nnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the nearest neighbour spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.
        """
        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[1], 10000)
        )
        p = np.pi
        return (32 / p ** 2) * (s * s) * np.exp(-(4 * s * s) / p)

    @staticmethod
    def nnnsd(
        spacings_range: Tuple[float, float] = (0.0, 4.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the next-nearest neighbour
        spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected next-nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.

        Notes
        -----
        See Dettmann, C. P., Georgiou, O., & Knight, G. (2017). Spectral
        statistics of random geometric graphs. EPL (Europhysics Letters),
        118(1), 18003. doi:10.1209/0295-5075/118/18003, pp10, Equation. 11
        """
        raise NotImplementedError()

    @staticmethod
    def spectral_rigidity(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the spectral rigidity.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the rigidity.

        max_L: float
            The largest L-value for which to compute the rigidity.

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the rigidity.

        L: ndarray
            The array of L values for which to compute the rigidity. Overrides
            other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        p = np.pi
        return (1 / (2 * (p ** 2))) * (np.log(2 * p * s) + np.euler_gamma - 5 / 4)

    @staticmethod
    def level_variance(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the level variance.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the level variance

        max_L: float
            The largest L-value for which to compute the level variance

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the level variance

        L: ndarray
            The array of L values for which to compute the level variance.
            Overrides other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        p = np.pi
        return (1 / (p ** 2)) * (np.log(2 * p * s) + np.euler_gamma + 1)


class GSE:
    @staticmethod
    def nnsd(
        spacings_range: Tuple[float, float] = (0.0, 3.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the nearest neighbour spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.
        """
        s = (
            spacings
            if spacings is not None
            else np.linspace(spacings_range[0], spacings_range[0], 10000)
        )
        p = np.pi
        # fmt: off
        return (262144 / (729*p**3)) * (s**4) * np.exp(-((64 / (9*p)) * (s*s)))
        # fmt: on

    @staticmethod
    def nnnsd(
        spacings_range: Tuple[float, float] = (0.0, 4.0),
        n_points: int = 1000,
        spacings: ndarray = None,
    ) -> ndarray:
        """Compute and return the expected values of the next-nearest neighbour
        spacing distribution / density.

        Parameters
        ----------
        spacings_range: (float, float)
            The max and min values.

        n_points: int
            The number of points in `spacings_range`.

        spacings: ndarray
            The values for which to return the expected next-nnsd density.
            Overrides the values in `spacings_range` and `n_points`, if provided.

        Notes
        -----
        See Dettmann, C. P., Georgiou, O., & Knight, G. (2017). Spectral
        statistics of random geometric graphs. EPL (Europhysics Letters),
        118(1), 18003. doi:10.1209/0295-5075/118/18003, pp10, Equation. 11
        """
        raise NotImplementedError()

    @staticmethod
    def spectral_rigidity(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the spectral rigidity.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the rigidity.

        max_L: float
            The largest L-value for which to compute the rigidity.

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the rigidity.

        L: ndarray
            The array of L values for which to compute the rigidity. Overrides
            other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        # s = L / np.mean(spacings)
        s = L
        p, y = np.pi, np.euler_gamma
        return (1 / (4 * (p ** 2))) * (np.log(4 * p * s) + y - 5 / 4 + (p ** 2) / 8)

    @staticmethod
    def level_variance(
        min_L: float = 0.5, max_L: float = 20, L_grid_size: int = 50, L: ndarray = None
    ) -> ndarray:
        """Compute and return the expected values of the level variance.

        Parameters
        ----------
        min_L: float
            The smallest L-value for which to compute the level variance

        max_L: float
            The largest L-value for which to compute the level variance

        L_grid_size: int
            The number of values in [min_L, max_L] to compute the level variance

        L: ndarray
            The array of L values for which to compute the level variance.
            Overrides other parameters if provided.
        """
        L = L if L is not None else np.linspace(min_L, max_L, L_grid_size)
        s = L
        p, y = np.pi, np.euler_gamma
        return (1 / (2 * (p ** 2))) * (np.log(4 * p * s) + y + 1 + (p ** 2) / 8)


GDE = Poisson
Ensemble = Union[GOE, GDE, Poisson, GUE, GSE]
