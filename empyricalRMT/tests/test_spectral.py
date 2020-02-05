import numpy as np
from numpy import ndarray
import pandas as pd
import pytest

from pathlib import Path

import empyricalRMT.rmt.unfolder as unfold
import empyricalRMT.rmt.plot
import empyricalRMT.rmt as rmt

from empyricalRMT.rmt.construct import generateGOEMatrix
from empyricalRMT.rmt.observables.rigidity import spectralRigidity
from empyricalRMT.rmt.plot import spectralRigidity as plotSpectral
from empyricalRMT.utils import eprint

CUR_DIR = Path(__file__).parent


def res(path: Path) -> str:
    return str(path.absolute().resolve())


def load_eigs(matsize: int = 10000) -> ndarray:
    eigs = None
    filename = f"test_eigs{matsize}.npy"
    eigs_out = CUR_DIR / filename
    try:
        eigs = np.load(res(eigs_out))
    except IOError as e:
        M = generateGOEMatrix(matsize)
        eprint(e)
        eigs = np.linalg.eigvalsh(M)
        np.save(filename, res(eigs_out))

    return eigs


def generate_eigs(matsize: int) -> ndarray:
    M = generateGOEMatrix(matsize)
    eigs = np.linalg.eigvalsh(M)
    return eigs


@pytest.mark.fast
def test_spectral_rigidity(
    matsize: int = 1000,
    plot_step: bool = False,
    unfold_degree: int = None,
    kind: str = "goe",
) -> None:
    eigs = generate_eigs(matsize)
    unfolded = unfold.Unfolder(eigs).unfold(trim=False)

    if plot_step:
        rmt.plot.stepFunction(
            eigs, mode="block", title="Spectral Rigidity Step Function Test"
        )

    L_vals, delta3 = spectralRigidity(
        unfolded, eigs, c_iters=2000, L_grid_size=100, min_L=0.5, max_L=25
    )
    df = pd.DataFrame({"L": L_vals, "∆3(L)": delta3})
    plotSpectral(
        unfolded,
        df,
        title=f"{kind.upper()} Matrix Spectral Rigidity Plot test",
        mode="block",
    )
