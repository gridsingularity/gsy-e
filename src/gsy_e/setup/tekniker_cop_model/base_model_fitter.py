import numpy as np


class BaseModelFitter:
    """Collection of methods that are used in all model fitters"""

    @staticmethod
    def pack_model_into_dict(
        capft: list,
        heirft: list,
        heirfplr: list,
        q_ref: float,
        p_ref: float,
        Q: list,
        cop: np.ndarray,
    ):
        # pylint: disable=too-many-positional-arguments, too-many-arguments
        """Return model parameters."""

        return {
            "CAPFT": capft,
            "HEIRFT": heirft,
            "HEIRFPLR": heirfplr,
            "Qref": q_ref,
            "Pref": p_ref,
            "Q_min": min(Q),
            "Q_max": max(Q),
            "COP_min": np.nanmin(cop),
            "COP_max": np.nanmax(cop),
            "COP_med": np.nanmedian(cop),
        }
