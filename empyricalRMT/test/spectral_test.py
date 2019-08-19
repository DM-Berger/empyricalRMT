import numpy as np
import pandas as pd

from pathlib import Path

import empyricalRMT.rmt.unfold as unfold
import empyricalRMT.rmt.plot
import empyricalRMT.rmt as rmt

from ..rmt.construct import generateGOEMatrix
from ..rmt.eigenvalues import getEigs, trim_iteratively
from ..rmt.observables.rigidity import spectralRigidity
from ..rmt.plot import spectralRigidity as plotSpectral
from ..utils import eprint

CUR_DIR = Path(__file__).parent


def res(path) -> str:
    return str(path.absolute().resolve())


def load_eigs(matsize=10000):
    eigs = None
    filename = f"test_eigs{matsize}.npy"
    eigs_out = CUR_DIR / filename
    try:
        eigs = np.load(res(eigs_out))
    except IOError as e:
        M = generateGOEMatrix(matsize)
        eprint(e)
        eigs = getEigs(M)
        np.save(filename, res(eigs_out))

    return eigs


def newEigs(matsize):
    M = generateGOEMatrix(matsize)
    eigs = getEigs(M)
    return eigs


def test_spectral_rigidity(
    matsize=1000,
    neweigs=True,
    eigs=None,
    plot_step=False,
    unfold_degree=None,
    kind="goe",
):
    unfolded = None
    if eigs is not None:
        pass
        unfolded = unfold.polynomial(eigs, 11)
    else:
        eigs = newEigs(matsize) if neweigs else load_eigs(matsize)
        unfolded = unfold.polynomial(eigs, 11)

    if plot_step:
        rmt.plot.stepFunction(eigs, trim=False, block=True)

    L_vals, delta3 = spectralRigidity(
        unfolded, eigs, c_iters=2000, L_grid_size=100, min_L=0.5, max_L=25
    )
    df = pd.DataFrame({"L": L_vals, "∆3(L)": delta3})
    plotSpectral(unfolded, df, f"{kind.upper()} Matrix", mode="block")
