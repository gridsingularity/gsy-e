from behave import then
from d3a.models.strategy.read_user_profile import _readCSV
from d3a import PENDULUM_TIME_FORMAT


@then('the UserProfileWind follows the Wind profile of csv')
def check_wind_csv_profile(context):
    wind = list(filter(lambda x: x.name == "Wind Turbine", context.simulation.area.children))[0]
    from d3a.setup.strategy_tests.user_profile_wind_csv import user_profile_path
    profile_data = _readCSV(user_profile_path)
    for timepoint, energy in wind.strategy.energy_production_forecast_kWh.items():

        time = str(timepoint.format(PENDULUM_TIME_FORMAT))
        accumulated_energy = 0
        for time_str in profile_data.keys():
            if int(time_str[:2]) == int(timepoint.hour):
                accumulated_energy += (profile_data[time_str] * 0.25)
        if time in profile_data.keys():
            actual_energy = accumulated_energy / 1000.0
            assert energy == actual_energy
        else:
            assert energy == 0
