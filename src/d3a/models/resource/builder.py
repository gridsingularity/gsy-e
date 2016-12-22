from d3a.models.resource.appliance import PVAppliance
from d3a.models.resource.properties import ApplianceProfileBuilder
from d3a.models.resource.properties import ApplianceType
from d3a.models.resource.properties import ElectricalProperties
from d3a.models.resource.appliance import EnergyCurve, ApplianceMode
import random


def gen_pv_appliance() -> PVAppliance:
    pv = PVAppliance("PV")
    builder = ApplianceProfileBuilder("PV", "Roof", ApplianceType.UNCONSTRAINED)
    builder.set_contact_url("https://enphase.com/en-us/company/contact-us")
    builder.set_icon_url("https://enphase.com/sites/all/themes/enphase/assets/images/svgs/src/enphase-logo.svg")
    builder.set_manufacturer("Enphase Energy")
    builder.set_model_url("Envoy S")
    builder.set_uuid("SOMERANDOMUUIDBEINGUSEDFORPV")

    voltage_range = (0.0, 300.0)
    variance_range = (-5.0, 5.0)
    electrical = ElectricalProperties(voltage_range, variance_range)

    on_curve = [voltage_range[1] - 15 + random.uniform(-10, 10) for p in range(0, 1000)]
    off_curve = [0, 0]
    curves = EnergyCurve(ApplianceMode.ON, on_curve)
    curves.add_mode_curve(ApplianceMode.OFF, off_curve)

    pv.set_appliance_properties(builder.build())
    pv.set_electrical_properties(electrical)
    pv.set_appliance_energy_curve(curves)

    return pv





