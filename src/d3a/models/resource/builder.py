from d3a.models.resource.appliance import PVAppliance
from d3a.models.resource.properties import ApplianceProfileBuilder
from d3a.models.resource.properties import ApplianceType
from d3a.models.resource.properties import ElectricalProperties
from d3a.models.resource.appliance import EnergyCurve, ApplianceMode
from d3a.models.area import DEFAULT_CONFIG
from pendulum.interval import Interval


def get_pv_curves(panel_count: int = 1) -> dict:
    """
    Function to get power production curve for a certain number of panels
    :param panel_count: Number of panels installed
    :return: Dictionary with appliance mode as key and curve as power produced.
    """

    """
    Actual power produced by one PV panel in california during month of April 2016.
    Samples were taken every 5 mins for 24 hours period, a total of 288 samples.
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

    mode_curves = dict()
    mode_curves[ApplianceMode.ON] = [x * panel_count for x in one_panel_curve]
    mode_curves[ApplianceMode.OFF] = [0, 0]

    return mode_curves


def gen_pv_appliance() -> PVAppliance:
    """
    Method to create a PVAppliance type object
    :return: A fully constructed PVAppliance type object
    """

    # Manufacturer related information
    pv = PVAppliance("PV")
    builder = ApplianceProfileBuilder("PV", "Roof", ApplianceType.UNCONSTRAINED)
    builder.set_contact_url("https://enphase.com/en-us/company/contact-us")
    builder.set_icon_url("https://enphase.com/sites/all/themes/enphase/assets/images/svgs/src/enphase-logo.svg")
    builder.set_manufacturer("Enphase Energy")
    builder.set_model_url("Envoy S")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORPV")

    # Power generation curve
    mode_curves = get_pv_curves(14)
    on_curve = mode_curves[ApplianceMode.ON]

    # Electrical properties
    power_range = (min(on_curve), max(on_curve))
    variance_range = (0, 0)     # As real data is used, variance may not be needed
    electrical = ElectricalProperties(power_range, variance_range)

    curves = EnergyCurve(ApplianceMode.ON, on_curve,
                         Interval(minutes=5), DEFAULT_CONFIG.tick_length)
    curves.add_mode_curve(ApplianceMode.OFF, mode_curves[ApplianceMode.OFF])

    pv.set_appliance_properties(builder.build())
    pv.set_electrical_properties(electrical)
    pv.set_appliance_energy_curve(curves)

    return pv





