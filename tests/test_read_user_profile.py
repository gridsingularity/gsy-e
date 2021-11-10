import pathlib
import unittest

from gsy_framework.constants_limits import GlobalConfig, PROFILE_EXPANSION_DAYS
from gsy_framework.read_user_profile import copy_profile_to_multiple_days, \
    _read_from_different_sources_todict, time_str

from d3a.gsy_e_core.util import d3a_path


class TestReadUserProfile(unittest.TestCase):

    def tearDown(self):
        GlobalConfig.IS_CANARY_NETWORK = False

    def test_copy_profile_to_multiple_days_correctly_expands_for_CNs(self):
        GlobalConfig.IS_CANARY_NETWORK = True
        profile_path = pathlib.Path(d3a_path + "/resources/Solar_Curve_W_cloudy.csv")
        in_profile = _read_from_different_sources_todict(profile_path)
        out_profile = copy_profile_to_multiple_days(in_profile)
        daytime_dict = dict((time_str(time.hour, time.minute), time) for time in in_profile.keys())

        assert len(in_profile) * PROFILE_EXPANSION_DAYS == len(out_profile)
        for time, out_value in out_profile.items():
            assert out_value == in_profile[daytime_dict[time_str(time.hour, time.minute)]]
