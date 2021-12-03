from math import isclose

from behave import then
from gsy_framework.constants_limits import DATE_TIME_FORMAT
from gsy_framework.read_user_profile import _str_to_datetime
from gsy_framework.utils import scenario_representation_traversal

from gsy_e.models.strategy.load_hours import LoadHoursStrategy


# PS, this step is temporary, I will create better steps once I find a fix for the bug
@then("the future strategy correctly posted orders and made trades")
def step_impl(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    for time_slot, core_stats in context.raw_sim_data.items():
        slot = _str_to_datetime(time_slot, DATE_TIME_FORMAT)
        for child, parent in scenario_representation_traversal(context.simulation.area):
            if isinstance(child.strategy, LoadHoursStrategy):
                assert isclose(child.strategy.state.get_energy_requirement_Wh(slot), 0.0,
                               rel_tol=1e8)
