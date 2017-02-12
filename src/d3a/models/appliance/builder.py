from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.heatpump import HeatPumpAppliance
from d3a.models.appliance.dumb_load import DumbLoad
from d3a.models.appliance.properties import ApplianceProfileBuilder
from d3a.models.appliance.properties import ApplianceType
from d3a.models.appliance.properties import ElectricalProperties
from d3a.models.appliance.appliance import EnergyCurve, ApplianceMode
from d3a.models.area import DEFAULT_CONFIG
from pendulum.interval import Interval
import random


def get_pv_curves(panel_count: int = 1) -> dict:
    """
    Function to get power production curve for a certain number of panels
    :param panel_count: Number of panels installed
    :return: Dictionary with appliance mode as key and curve as power produced.
    """

    """
    Actual power produced by one PV panel in california during month of April 2016.
    Samples were taken every 5 minutes for 24 hours period, a total of 288 samples.
    Samples are in W and get converted to kW before returning
    """
    one_panel_curve = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.07, 0.14, 0.86, 0.86, 1.64, 2.14, 2.71, 3.29,
                       4.36, 6.14, 9.14, 19.07, 34.21, 40.64, 43.79, 48.0, 52.5, 57.0, 61.43,
                       65.79, 69.86, 73.5, 76.57, 79.71, 83.43, 87.29, 91.14, 95.0, 98.86,
                       102.5, 105.86, 109.36, 112.71, 115.79, 118.64, 121.57, 124.36, 127.14,
                       129.57, 132.0, 134.14, 136.64, 138.93, 141.07, 143.07, 145.0, 146.64,
                       148.21, 149.64, 151.43, 152.5, 153.64, 154.86, 155.79, 156.64, 157.64,
                       158.79, 160.21, 161.14, 161.86, 161.86, 162.57, 161.71, 161.29, 161.14,
                       160.86, 160.5, 160.5, 159.29, 158.57, 157.5, 156.21, 153.71, 144.93,
                       135.21, 130.14, 122.79, 121.0, 105.5, 88.36, 88.71, 88.93, 96.79, 101.43,
                       107.43, 107.57, 117.21, 122.36, 124.43, 120.07, 119.0, 118.0, 114.93,
                       111.07, 88.79, 104.79, 101.86, 96.0, 90.5, 85.86, 82.43, 79.0, 72.07,
                       57.93, 41.79, 27.86, 15.93, 8.21, 4.5, 3.93, 3.5, 2.79, 2.29, 1.79,
                       1.43, 0.79, 0.14, 0.14, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0]

    # FIXME: Arbitrary factor "18" somehow matches data from strategy.
    # FIXME: 12 would make sense since 60 min / 5 min = 12 but...
    mode_curves = {
        ApplianceMode.ON: [(x * panel_count) / 18 / 1000 for x in one_panel_curve],
        ApplianceMode.OFF: [0, 0]
    }

    return mode_curves


def gen_fridge_curves() -> dict:
    """
    Method to generate power consumption curves in watts
    :return: Dictionary with appliance mode as key and curve as power consumed.
    """
    run_cycle_duration = 5 * 60  # Fridge cooling cycle runs for 5 minutes = 300 sec
    avg_power_consumption = 130     # Modern fridge consumes on an avg of 130 W while cooling
    variation = (-30, 30)
    on_curve = []

    for sec in range(0, run_cycle_duration):
        on_curve.append(avg_power_consumption + random.uniform(variation[0], variation[1]))

    off_curve = [0, 0]

    mode_curve = dict()
    mode_curve[ApplianceMode.ON] = on_curve
    mode_curve[ApplianceMode.OFF] = off_curve

    return mode_curve


def gen_heat_pump_curves() -> dict:
    """
    Method to generate power consumption curves in watts
    :return: Dictionary with appliance mode as key and curve as power consumed.
    """
    run_cycle_duration = 5 * 60  # Heating cycle runs for 5 minutes = 300 sec
    avg_power_consumption = 200  # Modern water heater consumes on an avg of 200 W while heating
    variation = (-30, 30)
    on_curve = []

    for sec in range(0, run_cycle_duration):
        on_curve.append(avg_power_consumption + random.uniform(variation[0], variation[1]))

    off_curve = [0, 0]

    mode_curve = dict()
    mode_curve[ApplianceMode.ON] = on_curve
    mode_curve[ApplianceMode.OFF] = off_curve

    return mode_curve


def gen_fridge_appliance() -> FridgeAppliance:
    """
    Method to create a Fridge type appliance object
    :return: A fully constructed FridgeAppliance type object
    """
    fridge = FridgeAppliance("Fridge")
    builder = ApplianceProfileBuilder("GE Profile 22/2 cu Fridge", "Kitchen",
                                      ApplianceType.BUFFER_STORAGE)
    builder.set_contact_url("http://www.geappliances.com/ge/service-and-support/contact.htm")
    builder.set_icon_url("http://products.geappliances.com/" +
                         "MarketingObjectRetrieval/Dispatcher?RequestType=Image&Name=CGI67704.jpg")
    builder.set_manufacturer("GE Appliances")
    builder.set_model_url("http://products.geappliances.com/appliance/gea-specs/PYE22PMKES")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORFRIDGE")

    # Power generation curve
    mode_curves = gen_fridge_curves()
    on_curve = mode_curves[ApplianceMode.ON]
    off_curve = mode_curves[ApplianceMode.OFF]

    # Electrical properties
    power_range = (min(off_curve), max(on_curve))
    variance_range = (0, 0)  # As real data is used, variance may not be needed
    electrical = ElectricalProperties(power_range, variance_range)

    curves = EnergyCurve(ApplianceMode.ON, on_curve,
                         Interval(seconds=1), DEFAULT_CONFIG.tick_length)
    curves.add_mode_curve(ApplianceMode.OFF, off_curve)

    fridge.set_appliance_properties(builder.build())
    fridge.set_electrical_properties(electrical)
    fridge.set_appliance_energy_curve(curves)

    fridge.start_appliance()
    fridge.change_mode_of_operation(ApplianceMode.OFF)

    return fridge


def gen_heat_pump_appliance() -> FridgeAppliance:
    """
    Method to create a Fridge type appliance object
    :return: A fully constructed FridgeAppliance type object
    """
    heat_pump = HeatPumpAppliance("Heat Pump")
    builder = ApplianceProfileBuilder("Stiebel Eltron Water Heater", "Garage",
                                      ApplianceType.BUFFER_STORAGE)
    builder.set_contact_url("http://www.stiebel-eltron-usa.com/contact-us")
    builder.set_icon_url("http://www.stiebel-eltron-usa.com/" +
                         "sites/default/files/main-image-dhc-borderless.png")
    builder.set_manufacturer("Stiebel Eltron")
    builder.set_model_url("http://www.stiebel-eltron-usa.com/" +
                          "products/dhc-point-of-use-tankless-electric-water-heaters")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORHEATPUMP")

    # Power generation curve
    mode_curves = gen_heat_pump_curves()
    on_curve = mode_curves[ApplianceMode.ON]
    off_curve = mode_curves[ApplianceMode.OFF]

    # Electrical properties
    power_range = (min(off_curve), max(on_curve))
    variance_range = (0, 0)  # As real data is used, variance may not be needed
    electrical = ElectricalProperties(power_range, variance_range)

    curves = EnergyCurve(ApplianceMode.ON, on_curve,
                         Interval(seconds=1), DEFAULT_CONFIG.tick_length)
    curves.add_mode_curve(ApplianceMode.OFF, off_curve)

    heat_pump.set_appliance_properties(builder.build())
    heat_pump.set_electrical_properties(electrical)
    heat_pump.set_appliance_energy_curve(curves)

    heat_pump.start_appliance()
    heat_pump.change_mode_of_operation(ApplianceMode.OFF)

    return heat_pump


def gen_bulb_curves() -> dict:
    """
    Method to generate power consumption curve for light bulbs
    :return: A dictionary containing curves for when bulb is ON and OFF
    """
    on_curve = [5.5, 5.5]

    off_curve = [0, 0]

    mode_curve = dict()
    mode_curve[ApplianceMode.ON] = on_curve
    mode_curve[ApplianceMode.OFF] = off_curve

    return mode_curve


def gen_light_bulb() -> DumbLoad:
    """
    Method to create a Dumbload type appliance object for a light bulb
    :return: A fully constructed Bulb type object
    """
    bulb = DumbLoad("LED Bulb")
    builder = ApplianceProfileBuilder("Philips Hue White Ambiance", "Living Room",
                                      ApplianceType.UNCONTROLLED)
    builder.set_contact_url("http://www2.meethue.com/en-us/support/")
    builder.set_icon_url("http://www2.meethue.com/media/3857254/WA-GU10.png")
    builder.set_manufacturer("Philips")
    builder.set_model_url(
        "http://www2.meethue.com/en-us/productdetail/philips-hue-white-ambiance-gu10-single-bulb")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORBULB")

    # Power generation curve
    mode_curves = gen_bulb_curves()
    on_curve = mode_curves[ApplianceMode.ON]
    off_curve = mode_curves[ApplianceMode.OFF]

    # Electrical properties
    power_range = (min(off_curve), max(on_curve))
    variance_range = (0, 0)
    electrical = ElectricalProperties(power_range, variance_range)

    curves = EnergyCurve(ApplianceMode.ON, on_curve,
                         Interval(seconds=1), DEFAULT_CONFIG.tick_length)
    curves.add_mode_curve(ApplianceMode.OFF, off_curve)

    bulb.set_appliance_properties(builder.build())
    bulb.set_electrical_properties(electrical)
    bulb.set_appliance_energy_curve(curves)

    bulb.start_appliance()

    return bulb


def gen_facebook_AP() -> DumbLoad:
    """
    Method to create a Dumbload type appliance object for facebook wireless AP
    :return: A fully constructed FB wireless AP
    """
    facebook_wifi = DumbLoad("Facebook AP")
    builder = ApplianceProfileBuilder("Facebook WiFi", "Living Room",
                                      ApplianceType.UNCONTROLLED)
    builder.set_contact_url("https://www.facebook.com/help/")
    builder.set_icon_url("https://images.seeklogo.net/2016/09/facebook-icon-preview-1.png")
    builder.set_manufacturer("Facebook")
    builder.set_model_url(
        "https://www.facebook.com")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORFBWIFI")

    # Power generation curve
    mode_curves = gen_bulb_curves()
    on_curve = mode_curves[ApplianceMode.ON]
    off_curve = mode_curves[ApplianceMode.OFF]

    # Electrical properties
    power_range = (min(off_curve), max(on_curve))
    variance_range = (0, 0)
    electrical = ElectricalProperties(power_range, variance_range)

    curves = EnergyCurve(ApplianceMode.ON, on_curve,
                         Interval(seconds=1), DEFAULT_CONFIG.tick_length)
    curves.add_mode_curve(ApplianceMode.OFF, off_curve)

    facebook_wifi.set_appliance_properties(builder.build())
    facebook_wifi.set_electrical_properties(electrical)
    facebook_wifi.set_appliance_energy_curve(curves)

    facebook_wifi.start_appliance()

    return facebook_wifi
