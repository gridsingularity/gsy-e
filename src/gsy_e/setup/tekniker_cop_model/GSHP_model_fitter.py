import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from gsy_e.setup.tekniker_cop_model.base_model_fitter import BaseModelFitter

MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(MODULE_PATH, "input_data")
EXPORT_PATH = os.path.join(MODULE_PATH, "model_parameters")


class GshpModelFitter(BaseModelFitter):
    """Fitter for the GSHP model"""

    def __init__(self, filename: str, ref_evap_temp: int = 7, ref_cond_temp: int = 35):
        assert filename.endswith(".csv")
        self.calibration_data_filename = filename
        self.raw_data = pd.read_csv(os.path.join(INPUT_PATH, filename))
        self.ref_evap_temp = ref_evap_temp
        self.ref_cond_temp = ref_cond_temp

    def fit_end_export_data(self):
        """Fit and export model data"""
        export_filename = os.path.join(
            EXPORT_PATH,
            f"{self.calibration_data_filename.split('.')[0]}" f"_model_parameters.json",
        )

        model_parameters = self._fit_model()
        json_model_parameters = {}
        for name, value in model_parameters.items():
            json_model_parameters[name] = (
                value.tolist() if isinstance(value, np.ndarray) else value
            )
        with open(export_filename, "w") as fp:
            json.dump(json_model_parameters, fp)

    @staticmethod
    def _poly22(X, a, b, c, d, e, f):
        """
        Biquadratic polynomial self._poly22(Tevap, Tcond):

            f(Tev, Tco) = a + b*Tev + c*Tco + d*Tev^2 + e*Tev*Tco + f*Tco^2
        """
        Tev, Tco = X
        return a + b * Tev + c * Tco + d * Tev**2 + e * Tev * Tco + f * Tco**2

    @staticmethod
    def _poly2(PLR, a, b, c):
        """Quadratic polynomial: a*PLR^2 + b*PLR + c."""
        return a * PLR**2 + b * PLR + c

    def _eer_fplr(self, plr):
        return 4.1922 + 2.6988 * plr - 4.0581 * plr**2

    def _fit_model(self):
        df = self.raw_data.copy()

        # --------------------------------------------------------------
        # 1) Clean data and define reference point
        # --------------------------------------------------------------
        df = df[df["Q"] != 0]  # remove zero-capacity rows if any

        # Reference conditions for NXP:
        df_ref = df[(df["Tevap"] == self.ref_evap_temp) & (df["Tcond"] == self.ref_cond_temp)]
        if df_ref.empty:
            raise ValueError(
                f"Reference point (Tevap={self.ref_evap_temp}, Tcond={self.ref_cond_temp}) "
                f"not found in dataset."
            )

        Qref = float(df_ref["Q"].iloc[0])
        Pref = float(df_ref["P"].iloc[0])

        # --------------------------------------------------------------
        # 2) Compute CAPFT and EIRFT for full-load data
        # --------------------------------------------------------------
        df["CAPFT"] = df["Q"] / Qref
        df["EIRFT"] = df["P"] / (Pref * df["CAPFT"])

        # Fit CAPFT(T, T) biquadratic
        popt_capft, _ = curve_fit(
            self._poly22,
            (df["Tevap"].values, df["Tcond"].values),
            df["CAPFT"].values,
        )

        # Fit EIRFT(T, T) biquadratic
        popt_eirft, _ = curve_fit(
            self._poly22,
            (df["Tevap"].values, df["Tcond"].values),
            df["EIRFT"].values,
        )

        # Evaluate CAPFT/EIRFT with fitted surfaces
        df["CAPFT_eval"] = self._poly22(
            (df["Tevap"].values, df["Tcond"].values),
            *popt_capft,
        )
        df["EIRFT_eval"] = self._poly22(
            (df["Tevap"].values, df["Tcond"].values),
            *popt_eirft,
        )

        # Compute PLR and EIRFPLR for these full-load points
        df["PLR"] = df["Q"] / (Qref * df["CAPFT_eval"])
        df["EIRFPLR"] = df["P"] / (Pref * df["CAPFT_eval"] * df["EIRFT_eval"])

        # --------------------------------------------------------------
        # 3) Generate synthetic part-load points
        # --------------------------------------------------------------
        plr_targets = [0.75, 0.50, 0.25]

        tev_ref = float(df_ref["Tevap"].iloc[0])
        tco_ref = float(df_ref["Tcond"].iloc[0])

        capft_ref = self._poly22((tev_ref, tco_ref), *popt_capft)
        eirft_ref = self._poly22((tev_ref, tco_ref), *popt_eirft)

        synthetic_rows = []
        for plr in plr_targets:
            Q_syn = Qref * capft_ref * plr
            EER_syn = self._eer_fplr(plr)
            P_syn = Q_syn / EER_syn
            EIR_syn = P_syn / (Pref * capft_ref * eirft_ref)

            synthetic_rows.append(
                {
                    "Tevap": tev_ref,
                    "Tcond": tco_ref,
                    "Q": Q_syn,
                    "P": P_syn,
                    "CAPFT_eval": capft_ref,
                    "EIRFT_eval": eirft_ref,
                    "PLR": plr,
                    "EIRFPLR": EIR_syn,
                }
            )

        df_syn = pd.DataFrame(synthetic_rows)
        df_plrfit = pd.concat([df, df_syn], ignore_index=True)

        # Use only reference-temperature rows for the PLR fit
        df_ref_plr = df_plrfit[(df_plrfit["Tevap"] == tev_ref) & (df_plrfit["Tcond"] == tco_ref)]

        PLR_fit = df_ref_plr["PLR"].values
        EIRFPLR_fit = df_ref_plr["EIRFPLR"].values

        # --------------------------------------------------------------
        # 4) Fit quadratic EIRFPLR(PLR) and inverse the order to fit to gsy-e implementation
        # --------------------------------------------------------------
        popt_eirfplr, _ = curve_fit(self._poly2, PLR_fit, EIRFPLR_fit)
        # --------------------------------------------------------------
        # 5) Pack output model dictionary
        # --------------------------------------------------------------
        model = {
            "CAPFT": popt_capft,
            "HEIRFT": popt_eirft,
            "HEIRFPLR": popt_eirfplr[::-1],
            "Qref": Qref,
            "Pref": Pref,
            "Q_min": df["Q"].min(),
            "Q_max": df["Q"].max(),
            "PLR_min": PLR_fit.min(),
            "COP_min": df["EER"].min(),
            "COP_max": df["EER"].max(),
            "COP_med": df["EER"].median(),
        }

        return model


if __name__ == "__main__":
    GshpModelFitter("AERMEC_NXP_0600_4L_COOL.csv").fit_end_export_data()
    GshpModelFitter("AERMEC_NXP_0600_4L_HEAT.csv", ref_evap_temp=8).fit_end_export_data()
