import pendulum

from gsy_e.models.strategy.energy_parameters.energy_params_eb import ProfileScaler


class TestProfileScaler:
    """Tests for the ProfileScaler class."""

    PROFILE = {
        pendulum.DateTime(2022, 1, 1): 10,
        pendulum.DateTime(2022, 1, 2): 20,
        pendulum.DateTime(2022, 1, 3): 30,
        pendulum.DateTime(2022, 1, 4): 40,
    }

    def test_scale_by_peak(self):
        """The profile values are correctly scaled by fitting the old values to the new peak."""
        scaler = ProfileScaler(self.PROFILE)
        scaled_profile = scaler.scale_by_peak(peak_kWh=50)

        assert scaled_profile == {
            pendulum.DateTime(2022, 1, 1): 12.5,
            pendulum.DateTime(2022, 1, 2): 25,
            pendulum.DateTime(2022, 1, 3): 37.5,
            pendulum.DateTime(2022, 1, 4): 50
        }

        # If we rescale the profile using the original peak, we should obtain the original profile
        assert ProfileScaler(scaled_profile).scale_by_peak(peak_kWh=40) == self.PROFILE
