This indicator shows the self-sufficiency and self-consumption percentage of the community.
Self-Sufficiency refers to the amount of a community’s energy demand that is produced locally. It is calculated as follow:

`self_sufficiency(market) = self_consumed_energy / total_energy_demanded`

Self-Consumption refers to the % of energy in kWh that the community consumed from its own production. It is calculated as follow:

`self_consumption(market) = self_consumed_energy / total_energy_produced`

![alt_text](img/self-sufficiency-self-consumption.png)

***Figure 2.22***. *Self-Sufficiency and Self-Consumption Results.*

Here is an example of the self-sufficiency and self-consumption calculation:

![alt_text](img/self-sufficiency-consumption-1.png)

***Figure 2.23***. *Example grid setup showing an energy community consisting of two homes.*


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
