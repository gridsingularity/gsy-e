The following parameters can be set in the Market Maker.

- **Name:** The name of the Market Maker.

- **Role:** The user has two options:
    - Infinite power plant, grid connected: In this mode, it has the ability to meet the infinite energy demands of consumers at the most expansive rate that could exist in that grid.
    - Pricer setter, islanded microgrid: In this mode, it won’t fulfill the energy demands of any consumer but would only be used as a reference point of highest possible `energy_rate` that could exist in that grid.

- **Market maker rate type:** The user can choose either *User Input* to define a fixed rate defined by the *Market maker rate* or to upload their own Market Maker profile.

- **Market maker rate:** The fixed rate the Market Maker will enforce, if *User Input* is chosen for the *Market maker rate type*.

For further general information about this strategy, follow the backend [Market Maker Strategy](market-maker-strategy.md) manual.

The configuration interface is shown below: 

![img](img/market-maker-1.png)