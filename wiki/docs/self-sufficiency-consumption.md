
**Self-sufficiency**: % of energy needs covered by local generation
**Self-consumption**: % of local energy generation consumed locally
```
self_sufficiency(market) = self_consumed_energy / total_energy_demanded
self_consumption(market) = self_consumed_energy / total_energy_produced
```
The example provided in the figure below has the following grid architecture: 

*   `total_house1_pv_production` = 10kWh
*   `house1_pv` → `house1_load` = 1kWh
*   `house1_pv` → `house1_storage` = 5kWh
*   `house1_pv` → `house2_load` = 4kWh
*   `house1_storage` → `house1_load` = 2kWh
*   `house1_storage` → `house2_load` = 3kWh
*   `house1_self_consumer_energy` = (`house1_pv` → `house1_load`) + (`house1_pv` → `house1_storage` → `house1_load`) = 1 + 2 = 3kWh
*   `house1_total_energy_demanded` (only includes the demanded energy from house1’s load asset) = 3kWh

In this example, self-sufficiency of the house 1 is `self_sufficiency(house1)` = `house1_self_consumer_energy` / `house1_total_energy_demanded`

*   `self_sufficiency(house1)` = 3 / 3 = 1 → 100%

Self-consumption of the house 1 is `self_consumption(house1)` = `house1_self_consumer_energy` / `house1_total_energy_produced`

*   `self_consumption(house1)` = 3 / 10 = 0.3 → 30%

In the **Grid**, the highest level of the hierarchy :

*   **self_sufficiency** = 10 / 10 = 1 → 100%
*   **self_consumption** = 10 / 10 = 1 → 100%

![alt_text](images/image1.png "image_tooltip")

