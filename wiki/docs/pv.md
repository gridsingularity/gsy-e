The following parameters can be configured in the PV Strategy:

- **Name:** Must be unique. When number of duplicates greater than 1, a number is appended to the individual names.

- **Panel count:** How many PV panels should be attached, each panel creates a power of 250W.

- **Solar Profile:** The user can choose between multiple solar profiles (*sunny, partially cloudy* or *cloudy*). If the user wants to use a different power output per panel, they can create a *Gaussian curve* or *upload* their own generation profile.

- **Initial selling rate:** Initial energy rate that the PV offers at the beginning of each market slot. The initial selling rate is defined and frozen by the marker maker rate.

- **Final selling rate:** Final energy rate that the PV offers at the end of each market slot.

- **Rate decrease:** Explicit rate decrease increment.
- **Fit to limits:** Derive bidding behavior from a linear fitted curve of a selling rate between *initial_selling_rate* and **final_selling_rate** within the bidding interval. If activated, `energy_rate_decrease_per_update = (initial_selling_rate - final_selling_rate) / max(int((slot_length / update_interval) -1), 1)`

- **Update interval:** The frequency at which the rate is updated. 

For further general information about this strategy, follow the backend [PV Strategy](pv-strategy.md) manual.

The configuration interface is shown below:

![img](img\pv-1.png)