import pathlib
import unittest

from gsy_framework.constants_limits import GlobalConfig, PROFILE_EXPANSION_DAYS, ConstSettings
from gsy_framework.read_user_profile import _copy_profile_to_multiple_days, \
    _read_from_different_sources_todict, _hour_time_str

from gsy_e.gsy_e_core.util import gsye_root_path


class TestReadUserProfile(unittest.TestCase):

    def tearDown(self):
        GlobalConfig.IS_CANARY_NETWORK = False

    @staticmethod
    def test_copy_profile_to_multiple_days_correctly_expands_for_CNs():
        GlobalConfig.IS_CANARY_NETWORK = True
        profile_path = pathlib.Path(gsye_root_path + "/resources/Solar_Curve_W_cloudy.csv")
        in_profile = _read_from_different_sources_todict(profile_path)
        out_profile = _copy_profile_to_multiple_days(in_profile)
        daytime_dict = dict((_hour_time_str(time.hour, time.minute), time)
                            for time in in_profile.keys())

        assert ((len(in_profile) * PROFILE_EXPANSION_DAYS +
                ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS * 4) ==
                len(out_profile))
        for time, out_value in out_profile.items():
            assert out_value == in_profile[daytime_dict[_hour_time_str(time.hour, time.minute)]]
