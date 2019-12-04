A finite power plant is an energy supplier that offers a configurable amount of power per time slot at a configured energy rate.

- `energy_rate`: the energy rate in cents/kWh.
- `max_available_power_kW` = maximum available power in kW, can also be a power profile.


Corresponding code: `src/3a/models/strategy/finite_power_plant.py`



How to add a finite power plant to the `setup-file`:

```
profile_kW = {
    0: 0.1,
    8: 0.15,
    12: 0.2,
    19: 0.15,
    22: 0.1
}         
Area('Finite Power Plant', strategy=FinitePowerPlant(energy_rate=31.3,
                                                     max_available_power_kW=profile_kW),
                           appliance=SwitchableAppliance()),
```