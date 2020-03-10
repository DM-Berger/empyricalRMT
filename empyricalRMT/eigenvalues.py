import numpy as np
import scipy.sparse as sparse

from numpy import ndarray
from scipy.integrate import quad
from typing import Any, List, Optional, Sized, Tuple, TypeVar, Type, Union
from typing_extensions import Literal
from warnings import warn

from empyricalRMT._constants import (
    DEFAULT_POLY_DEGREE,
    DEFAULT_SPLINE_SMOOTH,
    DEFAULT_POLY_DEGREES,
)
from empyricalRMT._eigvals import EigVals
from empyricalRMT.correlater import correlate_fast
from empyricalRMT.detrend import emd_detrend
from empyricalRMT.smoother import Smoother, SmoothMethod
from empyricalRMT.trim import Trimmed, TrimReport
from empyricalRMT.unfold import Unfolded


_WARNED_SMALL = False

# see https://stackoverflow.com/a/44644576, for class methods
Eigens = TypeVar("Eigens", bound="Eigenvalues")


class Eigenvalues(EigVals):
    """Basic class providing access to various items of interest in RMT. """

    def __init__(self, eigenvalues: Sized):
        """Construct an Eigenvalues object.

        Parameters
        ----------
        eigs: Sized
            An object for which np.array(eigs) will return a sensible, one-dimensional
            array of floats which are the computed eigenvalues of some matrix.
        """
        global _WARNED_SMALL
        if eigenvalues is None:
            raise ValueError("`eigenvalues` must be an array_like.")
        try:
            length = len(eigenvalues)
            if length < 50 and not _WARNED_SMALL:
                warn(
                    "You have less than 50 eigenvalues, and the assumptions of Random "
                    "Matrix Theory are almost certainly not justified. Any results "
                    "obtained should be interpreted with caution",
                    category=UserWarning,
                )
                _WARNED_SMALL = True  # don't warn more than once per execution
        except TypeError:
            raise ValueError(
                "The `eigs` passed to unfolded must be an object with a defined length via `len()`."
            )

        super().__init__(eigenvalues)
        self._series_T: Optional[int] = None
        self._series_N: Optional[int] = None
        # get some Marchenko-Pastur endpoints
        self._marchenko: Optional[Tuple[float, float]] = None
        self._marchenko_shifted: Optional[Tuple[float, float]] = None

    @classmethod
    def from_correlations(
        cls: Type[Eigens],
        data: ndarray,
        atol: float = 1e3 * np.finfo(np.float).eps,
        lower: bool = True,
    ) -> Eigens:
        """Use positive semi-definiteness to identify likely zero-valued eigenvalues
        due to floating point imprecision.

        Parameters
        ----------
        data: ndarray
            Either a 2-dimensional symmetric correlation matrix, or the
            1-dimensional computed eigenvalues from such a matrix.

        atol: float
            Absolute tolerance. Eigenvalues with absolute value less than _atol_
            will be considered equal to zero.

        lower: bool
            If _lower_ is True (default), use only the lower triangle to compute
            the eigenvalues. Otherwise, use the upper triangle.


        Returns
        -------
        eigenvalues: Eigenvalues
            The Eigenvalues object, with values close to zero pre-trimmed away.
        """
        if len(data.shape) > 2:
            raise ValueError(
                "`data` must be either flat, 1-dimensional, or 2-dimensional."
            )
        if len(data.shape) == 2 and np.min(data.shape) > 1:
            eigs = np.linalg.eigvalsh(data, "L" if lower else "U")
        eigs = data.reshape(-1)  # equivalent to ravel but less likely to copy
        return cls(eigs[np.abs(eigs) < atol])

    # TODO: see if we can represent the full eigenvalue problem and solve that,
    # instead of going through the covariance matrix
    @classmethod
    def from_time_series(
        cls: Type[Eigens],
        data: ndarray,
        trim_zeros: bool = True,
        zeros: Union[float, Literal["heuristic"], Literal["negative"]] = "heuristic",
        time_axis: int = 1,
        ddof: int = 0,
        use_sparse: bool = False,
        **sp_args: Any,
    ) -> Eigens:
        """Use Marchenko-Pastur and positive semi-definiteness to identify likely noise
        values and zero-valued eigenvalues due to floating point imprecision

        Parameters
        ----------
        data: ndarray
            A 2-dimensional matrix of time-series data.

        trim_zeros: bool
            If True (default) only return eigenvalues greater than `zeros`
            (e.g. remove values that are likely unstable or actually zero due
            to floating point precision limitations).

        zeros: float
            - If a float, The smallest acceptable value for an eigenvalue not to
              be considered zero.
            - If "heuristic", trim according to:
                1. find the magnitude of the largest *negative* eigenvalue (these
                   values are impossible, since correlation matrices are positive
                   definite), and call this `e_min`
                2. If there are no negative eigenvalues, set `e_min = 100*eps`, where
                   `eps` is machine epsilon, i.e. `np.finfo(float).eps`
                3. only return eigenvalues greater than 10 times `e_min`

        time_axis: int
            If 0, assumes the data.shape == (n, T), where n is the number of
            features / variables, and T is the length (number of points) in each
            time series.

        use_sparse: bool
            Convert the interim correlation matrix to a sparse triangular
            matrix, and use `scipy.sparse.linalg.eigsh` to solve for the
            eigenvalues. This currently does not save memory (since we still
            compute an interim dense covariance matrix) but gives more control
            over what eigenvalues are returned.

        sp_args:
            Keyword arguments to pass to scipy.sparse.linalg.eigsh.


        Returns
        -------
        eigenvalues: Eigenvalues
            The Eigenvalues object, with extra time-series relevant data:
            - Eigenvalues.marcenko_endpoints: (float, float)
        """
        if len(data.shape) != 2:
            raise ValueError("Input `data` array must have dimension of 2.")
        if time_axis not in [0, 1]:
            raise ValueError("Invalid `time_axis`. Must be either 0 or 1.")
        if time_axis == 0:
            data = data.T

        corrs = correlate_fast(data, ddof=ddof)
        if use_sparse:
            corrs = sparse.tril(corrs)
            if sp_args.get("return_eigenvectors") is True:
                raise ValueError(
                    "This function is intended only as a helper to extract eigenvalues from time-series."
                )

            eigs = sparse.linalg.eigsh(corrs, **sp_args)
        eigs = np.linalg.eigvalsh(corrs)

        if trim_zeros:
            if zeros == "heuristic":
                e_min = eigs.min()
                if e_min > 0:
                    e_min = np.finfo(float).eps * 100
                e_min = np.abs(e_min)
                eigs = eigs[eigs > (10 * e_min)]
            elif zeros == "negative":
                eigs = eigs[eigs > 0]
            else:
                try:
                    zeros = float(zeros)
                except ValueError as e:
                    raise ValueError(
                        "`zeros` must be a either a float, 'heuristic' or 'negative'"
                    ) from e
                eigs = eigs[eigs > zeros]

        eigs = cls(eigs)
        N, T = data.shape
        eigs._series_T = T
        eigs._series_N = N
        # get some Marchenko-Pastur endpoints
        shift = 1 - eigs.max() / N
        r = np.sqrt(N / T)
        eigs._marchenko = ((1 - r) ** 2, (1 + r) ** 2)
        eigs._marchenko_shifted = (shift * (1 + r) ** 2, shift * (1 - r) ** 2)
        return eigs  # type: ignore

    @property
    def values(self) -> ndarray:
        """Return the stored eigenvalues."""
        return self._vals

    @property
    def vals(self) -> ndarray:
        """Return the stored eigenvalues. Alternate for Eigenvalues.values"""
        return self._vals

    @property
    def eigenvalues(self) -> ndarray:
        """Return the stored eigenvalues. Alternate for Eigenvalues.values"""
        return self._vals

    @property
    def eigs(self) -> ndarray:
        """Return the stored eigenvalues. Alternate for Eigenvalues.values"""
        return self._vals

    def trim_report(
        self,
        max_trim: float = 0.5,
        max_iters: int = 7,
        poly_degrees: List[int] = DEFAULT_POLY_DEGREES,
        spline_smooths: List[float] = [],
        spline_degrees: List[int] = [],
        gompertz: bool = True,
        detrend: bool = False,
        outlier_tol: float = 0.1,
        show_progress: bool = False,
    ) -> TrimReport:
        """Compute multiple trim regions iteratively via histogram-based outlier
        detection, perform unfolding for each trim region, and summarize the
        resultant spacings and trimmings.


        Parameters
        ----------
        max_trim: float
            Float in (0, 1). The maximum allowable portion of eigenvalues to be trimmed.
            E.g. `max_trim=0.8` means to allow up to 80% of the original eigenvalues to
            be trimmed away.

        max_iters: int
            The maximum allowable number of iterations of outlier detection to run.
            Setting `max_iters=0` will not allow any trimming / outlier detection, and so
            will simply evaluate unfolding for different smoothers on the original raw
            eigenvalues. Typically, you would want this to be >= 4, to allow for trimming
            both some of the most extreme positive and negative eigenvalues.

        poly_degrees: List[int]
            the polynomial degrees for which to compute fits. Default [3, 4, 5,
            6, 7, 8, 9, 10, 11]

        spline_smooths: List[float]
            the smoothing factors passed into scipy.interpolate.UnivariateSpline fits.
            Default np.linspace(1, 2, num=11)

        spline_degrees: List[int]
            A list of ints determining the degrees of scipy.interpolate.UnivariateSpline
            fits. Default [3]

        gompertz: bool
            Whether or not to use a gompertz curve as one of the smoothers.

        detrend: bool
            Whether or not to perform EMD detrending before returning the
            unfolded eigenvalues.

        outlier_tol: float
            A float between 0 and 1, and which is passed as the tolerance paramater for
            [HBOS](https://pyod.readthedocs.io/en/latest/pyod.models.html#module-pyod.models.hbos)
            histogram-based outlier detection


        Returns
        -------
        trimmed: TrimReport
            A TrimReport object, which contains various information and functions
            for evaluating the different possible trim regions.
        """
        print("Trimming to central eigenvalues.")

        eigs = self.vals
        return TrimReport(
            eigenvalues=eigs,
            max_trim=max_trim,
            max_iters=max_iters,
            poly_degrees=poly_degrees,
            spline_smooths=spline_smooths,
            spline_degrees=spline_degrees,
            gompertz=gompertz,
            detrend=detrend,
            outlier_tol=outlier_tol,
            show_progress=show_progress,
        )

    def get_best_trimmed(
        self,
        smoother: SmoothMethod = "poly",
        degree: int = DEFAULT_POLY_DEGREE,
        spline_smooth: float = DEFAULT_SPLINE_SMOOTH,
        max_iters: int = 7,
        max_trim: float = 0.5,
        detrend: bool = False,
        outlier_tol: float = 0.1,
    ) -> Trimmed:
        """For the given smoother and smmothing and trim options, compute
        a up to `max_iters` different trim regions, and select the region
        which has an unfolding that is most GOE-like in terms of its local
        spacings.


        Parameters
        ----------
        max_trim: float
            Float in (0, 1). The maximum allowable portion of eigenvalues to be trimmed.
            E.g. `max_trim=0.8` means to allow up to 80% of the original eigenvalues to
            be trimmed away.

        max_iters: int
            The maximum allowable number of iterations of outlier detection to run.
            Setting `max_iters=0` will not allow any trimming / outlier detection, and so
            will simply evaluate unfolding for different smoothers on the original raw
            eigenvalues. Typically, you would want this to be >= 4, to allow for trimming
            both some of the most extreme positive and negative eigenvalues.

        smoother: "poly" | "spline" | "gompertz" | lambda
            the type of smoothing function used to fit the step function

        degree: int
            the degree of the polynomial or spline

        spline_smooth: float
            the smoothing factors passed into scipy.interpolate.UnivariateSpline

        outlier_tol: float
            A float between 0 and 1, and which is passed as the tolerance paramater for
            [HBOS](https://pyod.readthedocs.io/en/latest/pyod.models.html#module-pyod.models.hbos)
            histogram-based outlier detection


        Returns
        -------
        best_indices: Tuple[int, int]
            The indices (start, end) such that eigenvalues[start:end] is the trimmed
            region that is "most GOE" in terms of its nearest-neighbour level spacings.
        """
        report = None
        if smoother == "poly":
            report = TrimReport(
                eigenvalues=self.vals,
                max_trim=max_trim,
                max_iters=max_iters,
                poly_degrees=[degree],
                spline_smooths=[],
                spline_degrees=[],
                gompertz=False,
                detrend=detrend,
                outlier_tol=outlier_tol,
            )
        elif smoother == "spline":
            report = TrimReport(
                eigenvalues=self.vals,
                max_trim=max_trim,
                max_iters=max_iters,
                poly_degrees=[],
                spline_smooths=[spline_smooth],
                spline_degrees=[degree],
                gompertz=False,
                detrend=detrend,
                outlier_tol=outlier_tol,
            )
        elif smoother == "gompertz":
            report = TrimReport(
                eigenvalues=self.vals,
                max_trim=max_trim,
                max_iters=max_iters,
                poly_degrees=[],
                spline_smooths=[],
                spline_degrees=[],
                gompertz=True,
                detrend=detrend,
                outlier_tol=outlier_tol,
            )
        else:
            raise ValueError("Unknown smoother.")

        _, _, best_indices, _ = report.best_overall()
        start, end = best_indices[0][0], best_indices[0][1]
        return self.trim_manually(start, end)

    def trim_marcenko_pastur(
        self,
        series_length: int = None,
        n_series: int = None,
        largest: bool = True,
        use_shifted: bool = True,
    ) -> Trimmed:
        """Trim to noise eigenvalues under assumption that eigenvalues come from
        correlation matrix.

        Paramaters
        ----------
        series_length: int
            The length of the time series (e.g. number of time points per
            series). If None, check self for saved values and use those.

        n_series: int
            The number of time series of length `series_length`. If None,
            check self for saved values and use those.

        largest: bool
            If False, return the central (e.g. noise) eigenvalues. If True,
            return only the largest eigenvalues as determined by the cutpoints.

        use_shifted: bool
            If True, use the shifted distribution (see references below) which
            accounts for common nonstationary trends. Else, use classic
            Marcenko-Pastur cutpoints.

        Returns
        -------
        trimmed: Trimmed
            A Trimmed object containing the eigenvalues trimmed according to


        References
        ----------
        Almog, A., Buijink, M. R., Roethler, O., Michel, S., Meijer, J. H.,
        Rohling, J. H. T., & Garlaschelli, D. (2019). Uncovering functional
        signature in neural systems via random matrix theory. PLOS Computational
        Biology, 15(5), e1006934. doi:10.1371/journal.pcbi.1006934
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6513117/#sec008title,

        'A second and related improvement takes into account the effects of
        common (nonstationary) trends for a system with N cells, and in
        particular the largest eigenvalue eig_max. We realize that the effects
        of noise are inseparably coupled to those of the global trend [51], as
        the presence of the latter modifies and left-shifts the density of
        eigenvalues that we would otherwise observe in presence of noise only.
        So we do not simply superimpose the two effects as in [15]; on the
        contrary, we calculate the modification of the random bulk exactly,
        given the system’s empirical eig_max. In particular, we calculate the
        shifted value of an original Wishart matrix [15] to find

        eig_+- = (1 − eig_max/N)(1 +- 1/(sqrt(Q)))**2

        where Q = T/N is the ratio between the number of time steps in the data
        T and the number of cells N. Fig 2 shows both the modified and
        unmodified spectral densities. It also shows that taking the left-shift
        of the random bulk into account is very important, as it unveils
        informative empirical eigenvalues that would otherwise be classified as
        consistent with the random spectrum and hence discarded.'

        See also
        https://en.wikipedia.org/w/index.php?title=Marchenko%E2%80%93Pastur_distribution&oldid=939377392
        for a simple example of how the unshifted form of this trimming is done.
        """

        N = self._series_N if n_series is None else n_series
        T = self._series_T if series_length is None else series_length
        if N is None or T is None:
            raise ValueError(
                "Cannot determine either time series length or number of time series "
                "corresponding to eigenvalues. Consider extracting your eigenvalues "
                "from your data matrix via `Eigenvalues.from_time_series` or be sure "
                "to pass correct values to `n_series` and `series_length`."
            )
        eig_max = self.vals.max()
        if use_shifted:
            shift = 1 - eig_max / N
            trim_max, trim_min = shift * (1 + np.sqrt(N / T)) ** 2
            trim_min = shift * (1 - np.sqrt(N / T)) ** 2
        else:
            trim_min, trim_max = (1 - np.sqrt(N / T)) ** 2, (1 + np.sqrt(N / T)) ** 2

        if largest:
            return Trimmed(self.vals[self.vals > trim_max])
        else:
            return Trimmed(self.vals[(self.vals > trim_min) & (self.vals < trim_max)])

    def trim_manually(self, start: int, end: int) -> Trimmed:
        """trim sorted eigenvalues to [start:end), e.g. [eigs[start], ..., eigs[end-1]]"""
        trimmed_eigs = self.vals[start:end]
        return Trimmed(trimmed_eigs)

    def trim_interactively(self) -> None:
        raise NotImplementedError("This feature will be in a later release.")

    def trim_unfold_auto(
        self,
        max_trim: float = 0.5,
        max_iters: int = 7,
        poly_degrees: List[int] = DEFAULT_POLY_DEGREES,
        spline_smooths: List[float] = [],
        spline_degrees: List[int] = [],
        gompertz: bool = True,
        prioritize_smoother: bool = True,
        outlier_tol: float = 0.1,
    ) -> Unfolded:
        """Exhaustively compare mutliple trim regions and smoothers based on their "GOE score"
        and unfold the eigenvalues, using the trim region and smoothing parameters
        determined to be "most GOE" based on the exhaustive process.

        Exhaustively trim and unfold for various smoothers, and select the "best" overall trim
        percent and smoother according to GOE score.


        Parameters
        ----------
        max_trim: float
            Float in (0, 1). The maximum allowable portion of eigenvalues to be trimmed.
            E.g. `max_trim=0.8` means to allow up to 80% of the original eigenvalues to
            be trimmed away.

        max_iters: int
            The maximum allowable number of iterations of outlier detection to run.
            Setting `max_iters=0` will not allow any trimming / outlier detection, and so
            will simply evaluate unfolding for different smoothers on the original raw
            eigenvalues. Typically, you would want this to be >= 4, to allow for trimming
            both some of the most extreme positive and negative eigenvalues.

        poly_degrees: List[int]
            the polynomial degrees for which to compute fits. Default [3, 4, 5,
            6, 7, 8, 9, 10, 11]

        spline_smooths: List[float]
            the smoothing factors passed into scipy.interpolate.UnivariateSpline fits.
            Default np.linspace(1, 2, num=11)

        spline_degrees: List[int]
            A list of ints determining the degrees of scipy.interpolate.UnivariateSpline
            fits. Default [3]

        gompertz: bool
            Whether or not to use a gompertz curve as one of the smoothers.

        prioritize_smoother: bool
            Whether or not to select the optimal smoother before selecting the optimal
            trim region. See notes. Default: True.

        outlier_tol: float
            A float between 0 and 1, and which is passed as the tolerance paramater for
            [HBOS](https://pyod.readthedocs.io/en/latest/pyod.models.html#module-pyod.models.hbos)
            histogram-based outlier detection


        Notes
        -----
        Summary of the automatic trim-unfold process:

        1. Compute multiple "natural" trim regions via histogram-based outlier detection,
           halting when trimming would reach `max_trim` and/or `max_iters`. Visually,
           histogram-based outlier detection on the sorted eigenvalues will tend to find
           regions where there is a sudden change in the spacings between adjacent
           eigenvalues.

        2. For each trim region, fit all possible smoothers (i.e., smoother family +
           smoother parameters) specified in the arguments, and generate a set of unfolded
           eigenvalues for each.

        3. For each set of unfolded eigenvalues, compute the *GOE score*. The GOE score
           indexes how much the mean and variance of the spacings of the unfolded values
           differ from the expected spacing variance and mean for the unfolding of a GOE
           matrix.

        4. Assume that the choice of smoother should determine the optimal trim region,
           and not the converse. That is, since the combination of smoothers and trim
           regions yields a grid of scores:
              - for each trim region, there is a GOE score per smoother
              - for each smoother, there is a GOE score per trim region

           then we might:
                a. first choose the best trim, on average, across smoothers, and then, for
                   that trim, choose the smoother that results in the best GOE score, OR
                b. first choose the best smoother, on average, across trims, and then, for
                   that smoother, choose the trim that results in the best GOE score

            Choosing (a) might make sense, but in practice, the more eigenvalues that
            are trimmed, the more clustered or "smooth" the remaining values. That is,
            the more you trim, the more you can alter the nearest-neighbors' spacing distribution
            simply by varying the flexibility of your smoother. Since the GOE score is
            calculated based on the NNSD, this means can achieve more variable spacings by
            increasing the smoother flexibility, and vice-versa. Presumably, with increased
            flexibility, we also increase the number level variance, and decrease the spectral
            rigidity. In short, it is not clear exactly *what* we are doing if we make a
            particular trimming look most locally-GOE. It is also poorly motivated, since
            the reason we trim in the first place is to remove anchor points that have
            strong effects on the smoothing procedure.

            However, choosing (b) amounts to something like "choose the best approximation
            of the functional form of the eigenvalues, regardless of scale / outliers, and
            then account for bad fits due to outliers". Here, the danger is that outliers
            prior to trimming will badly effect flexible smoothers, making a naive summary
            statistic, like the average score across trims, bad for determining what
            smoother is overall. So instead, we use a trimmed mean.

        5. Assume that the best smoother is the one which results in the most GOE-like
           spacing distribution across all trims and all smoothers
        """
        trimmed = TrimReport(
            self.values,
            max_trim=max_trim,
            max_iters=max_iters,
            poly_degrees=poly_degrees,
            spline_smooths=spline_smooths,
            spline_degrees=spline_degrees,
            gompertz=gompertz,
            outlier_tol=outlier_tol,
        )
        orig_trimmed, unfolded = trimmed._get_autounfold_vals()
        percent = np.round(100 * len(orig_trimmed) / len(self.values), 1)
        print(f"Trimmed to {percent}% of original eigenvalues.")
        return Unfolded(orig_trimmed, unfolded)

    def unfold(
        self,
        smoother: SmoothMethod = "poly",
        degree: int = DEFAULT_POLY_DEGREE,
        spline_smooth: float = DEFAULT_SPLINE_SMOOTH,
        detrend: bool = False,
    ) -> Unfolded:
        """Unfold the eigenvalues with the specified smoothers.

        Parameters
        ----------
        eigs: ndarray
            sorted eigenvalues

        smoother: "poly" | "spline" | "gompertz" | "goe" | lambda
            The type of smoothing function used to fit the step function.
            - "poly": perform polynomial unfolding.
            - "spline": use fit a univarate spline.
            - "gompertz": fit a Gompertz exponential curve.
            - "goe": perform a "smooth" unfolding via the semicircle law
            - lambda: not implemented.

        degree: int
            The degree of the polynomial or spline.

        spline_smooth: float
            The smoothing factors passed into scipy.interpolate.UnivariateSpline

        emd_detrend: bool
            Whether to apply a final Empirical Mode Decomposition detrending
            (Morales et al.) before returning the final unfolded values.


        Returns
        -------
        unfolded: ndarray
            the unfolded eigenvalues

        steps: ndarray
            the step-function values
        """

        if smoother == "goe":
            return self.unfold_goe()

        eigs = self.eigs
        unfolded, _, closure = Smoother(eigs).fit(
            smoother=smoother,
            degree=degree,
            spline_smooth=spline_smooth,
            detrend=detrend,
            return_callable=True,
        )
        if detrend:
            unfolded = emd_detrend(unfolded)
        return Unfolded(originals=eigs, unfolded=np.sort(unfolded), smoother=closure)

    def unfold_goe(self) -> Unfolded:
        """Unfold via Wigner's semicircle law. """

        eigs = self.eigenvalues
        N = len(eigs)
        end = np.sqrt(2 * N)

        def __R1(x: float) -> np.float64:
            """The level density R_1(x), as per p.152, Eq. 7.2.33 of Mehta (2004) """
            if np.abs(x) < end:
                return np.float64((1 / np.pi) * np.sqrt(2 * N - x * x))
            return 0.0

        MAX = quad(__R1, -end, end)[0]

        def smooth_goe(x: float) -> np.float64:
            if x > end:
                return MAX
            return quad(__R1, -end, x)[0]

        unfolded = np.sort(np.vectorize(smooth_goe)(eigs))
        return Unfolded(originals=eigs, unfolded=unfolded)
