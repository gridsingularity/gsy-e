from behave import then
from pendulum.interval import Interval
from d3a.setup.strategy_tests import user_profile_load_csv, user_profile_load_dict # NOQA


@then('the DefinedLoadStrategy follows the Load profile provided as csv')
def check_load_profile_csv(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "H1 DefinedLoad", house1.children))[0]
    input_profile = load.strategy._readCSV(user_profile_load_csv.profile_path)

    desired_energy = {f'{k.hour:02}:{k.minute:02}': v
                      for k, v in load.strategy.state.desired_energy.items()
                      }

    for timepoint, energy in desired_energy.items():
        if timepoint in input_profile:
            assert energy == input_profile[timepoint] / \
                   (Interval(hours=1) / load.config.slot_length)
        else:
            assert False
    assert False


@then('load only accepted offers lower than acceptable_energy_rate')
def check_traded_energy_rate(context):
    house = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: "H1 DefinedLoad" in x.name, house.children))[0]

    for slot, market in house.past_markets.items():
        for trade in market.trades:
            if trade.buyer == load.name:
                assert (trade.offer.price / trade.offer.energy) <=\
                       load.strategy.acceptable_energy_rate.m
