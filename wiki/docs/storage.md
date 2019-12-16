The following parameters can be set in the Energy Storage Strategy (ESS):

- **Name:** Must be unique. When number of duplicates greater than 1, a number is appended to the individual names.

- **Battery capacity:** Total energy capacity.

- **Initial capacity:** Can be set in two ways:
    - Initial state of charge (in %)
    - Initial Energy (in kWh)
- **Minimum state of charge:** Minimum energy to leave in the storage.

- **Max power rating for battery:** Power limit for each market slot for sold and bought energy.

- **Initial selling rate:** Initial energy rate for selling energy at the beginning of each market slot.

- **Final selling rate:** Final energy rate for selling energy at the end of each market slot.

- **Rate decrease:** Explicit rate decrease increment.

- **Initial buying rate:** Initial energy rate for buying energy at the beginning of each market slot.

- **Final buying rate:** Final energy rate for buying energy at the end of each market slot.

- **Rate increase:** Explicit rate increase increment.

- **Fit to limits:** Derive bidding behavior from a linear fitted curve of a buying rate between `initial_buying_rate` and `final_buying_rate` and a selling rate between `initial_selling_rate` and `final_selling_rate` within the bidding interval. If activated: 
    - `energy_rate_increase = (final_buying_rate - initial_buying_rate) / max(int((slot_length / update_interval) -1), 1)`
    - `energy_rate_decrease_per_update = (initial_selling_rate - final_selling_rate) / max(int((slot_length / update_interval) -1), 1)`

- **Update interval:** The frequency at which the rate is updated. 
- **Capacity based method:** The ESS can trade energy based on a capacity dependent sell price.

For further general information about this strategy, follow the backend [Energy Storage System (ESS) Strategy](ess-strategy.md) manual.

The configuration interface is shown below:

![img](img/storage-1.png)

![img](img/storage-2.png)