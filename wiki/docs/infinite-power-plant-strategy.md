An infinite power plant is coded as a Commercial Energy Producer in the D3A code. The infinite power plant is used to represent the concept of an infinite bus, which has an unchangeable energy supply, unaffected by variations or disturbances caused by connected grids. Similar to its stable energy supply, the selling price of the infinite power plant is also unaffected by competition. This selling price is called the market maker price, as it provides a basis for local markets as other devices to compete against each other and the infinite power plant (or in many cases, the legacy grid).

The market maker price is configured globally for a simulation, unassigned to a specific device. But when configuring an infinite power plant, it usually makes sense to assign its energy rate to the market maker price. (The market maker price can be a constant value, a CSV file, or an array of changing values over time, similar to the PV and Load custom profile options). Rate settings include:

- `energy_rate`: the energy rate in cents/kWh (can be configured to the market maker price)



Corresponding code: `src/3a/models/strategy/commercial_producer.py`