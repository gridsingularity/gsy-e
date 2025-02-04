import numpy as np
import pandas as pd


class CalibrationDataReaderBase:
    """Base class for calibration data reader handlers"""

    def __init__(self, filename: str):
        self.filename = filename
        self.data_aux = {}
        self.data_plf = pd.DataFrame({})
        self.q_ref = 0.0
        self.p_ref = 0.0
        self.plr_min = 0.0


class CalibrationDataReader(CalibrationDataReaderBase):
    """Class that handles reading calibration data from .xslx files"""

    def __init__(self, filename: str):
        assert filename.endswith(".xlsx")
        super().__init__(filename)

        self.data_aux = self._get_data_aux()
        self.data_plf = self._read_plr()
        self._get_p_q_ref()

    def _get_p_q_ref(self):
        self.p_ref = np.nanmax(self.data_aux["P_fT"])
        max_index = np.unravel_index(
            np.nanargmax(self.data_aux["P_fT"]), self.data_aux["P_fT"].shape
        )
        self.q_ref = self.data_aux["Q_fT"][max_index]

    def _read_plr(self):
        df = pd.read_excel(self.filename, sheet_name="PLR", na_values=[""])
        pl_percent = df.iloc[0:, 0].to_numpy()
        self.plr_min = np.nanmin(pl_percent) / 100.0
        t_cond = df.iloc[0:, 1].to_numpy()
        t_evap = df.iloc[0:, 2].to_numpy()
        q = df.iloc[0:, 3].to_numpy()
        p = df.iloc[0:, 4].to_numpy()
        return pd.DataFrame({"Tcond": t_cond, "Tevap": t_evap, "Q": q, "P": p})

    def _get_data_aux(self):
        q_ft, qt_cond, qt_evap = self._get_fts("Q_fT")
        p_ft, pt_cond, pt_evap = self._get_fts("P_fT")
        assert np.array_equal(qt_cond, pt_cond)
        assert np.array_equal(qt_evap, pt_evap)
        assert p_ft.shape == q_ft.shape
        return {"Tcond_fT": qt_cond, "Tevap_fT": qt_evap, "Q_fT": q_ft, "P_fT": p_ft}

    def _get_fts(self, sheet_name: str) -> tuple[np.array, np.array, np.array]:
        df = pd.read_excel(self.filename, sheet_name=sheet_name, na_values=[""], index_col=[0])
        t_cond = np.array([c for c in df.columns if c != ""])
        t_evap = np.array(df.index.tolist())
        ft = df.to_numpy()
        return ft, t_cond, t_evap
