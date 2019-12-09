In each strategy, the bid or offer is changed according to its energy rate increase or decrease rate per update.

# Offers

Related settings:

- `initial_selling_rate`
- `final_selling_rate`
- `update_interval`
- `energy_rate_decrease_per_update`
- `fit_to_limit`

The following plot shows the energy rate in the frame of on spot market slot (`slot_length = 15mins`) for different combinations of the above mentioned parameters. If `fit_to_limit` is set to `True`, `energy_rate_decrease_per_update` is ignored and a rate decrease per time is calculated that starts at `initial_selling_rate` and ends at `final_selling_rate` while updating the rate every `update_interval` minutes.

![img](img\how-strategies-adjust-prices-1.png)

 

## Bids

Related settings:

- `initial_buying_rate`
- `final_buying_rate`
- `update_interval`
- `energy_rate_increase_per_update`
- `fit_to_limit`

The following plot shows the energy rate in the frame of on spot market slot (`slot_length = 15mins`) for different combinations of the above mentioned parameters. If `fit_to_limit` is set to `True`, `energy_rate_increase_per_update` is ignored and a rate increase per time is calculated that starts at `initial_buying_rate` and ends at `final_buying_rate` while updating the rate every `update_interval` minutes.

![img](img\how-strategies-adjust-prices-2.png)