from behave import then


@then("the device registry is not empty in market class")
def check_device_registry(context):
    from d3a.setup.balancing_market.test_device_registry import device_registry_dict
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    for slot, market in house.past_markets.items():
        assert market.device_registry == device_registry_dict
