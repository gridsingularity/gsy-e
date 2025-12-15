import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from calibration_data_reader import CalibrationDataReader


class COPModelFitter:
    """class that handles fitting teknikers' COP model"""

    def __init__(self, calibration_data_filename: str):
        self.calibration_data = CalibrationDataReader(calibration_data_filename)
        self.calibration_data_filename = Path(calibration_data_filename)

    def export_model_parameters_to_json(self, export_path):
        """Export the model paramters to JSON file."""
        export_filename = os.path.join(
            export_path,
            f"{os.path.basename(self.calibration_data_filename.stem)}" f"_model_parameters.json",
        )

        model_parameters = self.fit_model_q()
        json_model_parameters = {}
        for name, value in model_parameters.items():
            json_model_parameters[name] = (
                value.tolist() if isinstance(value, np.ndarray) else value
            )
        with open(export_filename, "w", encoding="utf8") as fp:
            json.dump(json_model_parameters, fp)

    def fit_model_q(self):
        """
        Function to calibrate DOE2 heat pump model using fitting technique.
        Inputs:
            data = dictionary with the operating data of the heat pump
        Outputs:
            model = dictionary with the coefficients of the fitted curves
        """

        data_aux = self.calibration_data.data_aux

        n_Tcond = len(data_aux["Tcond_fT"])

        # Initialize arrays
        data_fT = {
            "Tevap": np.zeros(n_Tcond * len(data_aux["Tevap_fT"])),
            "Tcond": np.zeros(n_Tcond * len(data_aux["Tevap_fT"])),
            "Q": np.zeros(n_Tcond * len(data_aux["Tevap_fT"])),
            "P": np.zeros(n_Tcond * len(data_aux["Tevap_fT"])),
        }

        # Fill in data_fT
        for i in range(len(data_aux["Tevap_fT"])):
            for j in range(n_Tcond):
                idx = j + n_Tcond * i
                data_fT["Tevap"][idx] = data_aux["Tevap_fT"][i]
                data_fT["Tcond"][idx] = data_aux["Tcond_fT"][j]
                data_fT["Q"][idx] = data_aux["Q_fT"][i, j]
                data_fT["P"][idx] = data_aux["P_fT"][i, j]

        data_fT_df = pd.DataFrame(data_fT)
        # Remove NaN values
        data_fT_df = data_fT_df.dropna(subset=["Q"])

        data_fPLR = self.calibration_data.data_plf

        # Remove NaN values
        data_fPLR = data_fPLR.dropna(subset=["Q"])
        # Combine temperature and PLR dependent data
        data_fTPLR_df = pd.concat([data_fT_df, data_fPLR])

        # Fit Curves
        # Temperature dependent data
        data_fT_df["x_capft"] = data_fT_df["Q"] / self.calibration_data.q_ref
        data_fT_df["x_heirft"] = data_fT_df["P"] / (
            self.calibration_data.p_ref * data_fT_df["x_capft"]
        )

        # Define the polynomial fit function (2nd order polynomial in 2 variables)
        def poly22(X, a0, a1, a2, a3, a4, a5):
            # pylint: disable=too-many-arguments
            Tevap, Tcond = X  # Unpack the tuple of inputs
            return (
                a0 + a1 * Tevap + a2 * Tcond + a3 * Tevap**2 + a4 * Tevap * Tcond + a5 * Tcond**2
            )

        # Fit for CAPFT
        x_capft_params, _ = curve_fit(
            poly22, np.vstack((data_fT_df["Tevap"], data_fT_df["Tcond"])), data_fT_df["x_capft"]
        )

        # Fit for HEIRFT
        x_heirft_params, _ = curve_fit(
            poly22, np.vstack((data_fT_df["Tevap"], data_fT_df["Tcond"])), data_fT_df["x_heirft"]
        )

        # Temperature and PLR dependent data
        data_fTPLR_df["x_capft"] = poly22(
            np.vstack((data_fTPLR_df["Tevap"], data_fTPLR_df["Tcond"])), *x_capft_params
        )
        data_fTPLR_df["x_heirft"] = poly22(
            np.vstack((data_fTPLR_df["Tevap"], data_fTPLR_df["Tcond"])), *x_heirft_params
        )
        data_fTPLR_df["x_PLR"] = data_fTPLR_df["Q"] / (
            self.calibration_data.q_ref * data_fTPLR_df["x_capft"]
        )
        data_fTPLR_df["x_heirfplr"] = data_fTPLR_df["P"] / (
            self.calibration_data.p_ref * data_fTPLR_df["x_capft"] * data_fTPLR_df["x_heirft"]
        )

        # Fit for HEIRFPLR (2nd order polynomial in 1 variable)
        def poly2(PLR, b0, b1, b2):
            return b0 + b1 * PLR + b2 * PLR**2

        x_heirfplr_params, _ = curve_fit(
            poly2, data_fTPLR_df["x_PLR"], data_fTPLR_df["x_heirfplr"]
        )

        # Save curve coefficients in a dictionary (the equivalent of a MATLAB struct)
        model = {
            "CAPFT": x_capft_params,
            "HEIRFT": x_heirft_params,
            "HEIRFPLR": x_heirfplr_params,
            "Qref": self.calibration_data.q_ref,
            "Pref": self.calibration_data.p_ref,
            "Q_min": data_fT["Q"].min(),
            "Q_max": data_fT["Q"].max(),
            "PLR_min": self.calibration_data.plr_min,
        }
        return model


if __name__ == "__main__":
    for filename in glob.glob(os.path.join(os.path.dirname(__file__), "input_data/*.xlsx")):
        COPModelFitter(filename).export_model_parameters_to_json("model_parameters/")
