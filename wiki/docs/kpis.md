In the last few years, distributed energy resources concept has gained ground in the power utility scope. Strictly speaking in terms of D3A, it is necessary to know a metric that could aid in visualising local resource utilisation in distributed energy trading platform. In order to do so we have planned to implement some KPIs to give us a good figure of effectiveness of localised distributed energy trading.

### Self-Sufficiency

Strictly speaking in terms of formula:

- self_sufficiency(area) = self_consumed_energy / total_energy_demanded

If you have a look at the hierarchical energy grid as shown in figure below, the self_consumed energy would be different from the reference point of whole energy grid. Lets consider **house 1** where,

- `total_house1_pv_production` = 10kWh

- `house1_pv` → `house1_load` = 1kWh

- `house1_pv` → `house1_storage` = 5kWh
- `house1_pv` → `house2_load` = 1kWh
- `house1_storage` → `house1_load` = 2kWh
- `house1_storage` → `house2_load` = 3kWh
- `house1_self_consumer_energy` = (`house1_pv` → `house1_load`) + (`house1_pv` → `house1_storage` → `house1_load`) = 1 + 2 = 3kWh
- `house1_total_energy_demanded` (only includes the demanded energy from house1’s load device) = 4kWh

Then, self-sufficiency of the house is `self_sufficiency(house1) = house1_self_consumer_energy / house1_total_energy_demanded`

- `self_sufficiency(house1)` = 3 / 4 = 0.75

From the reference point of **GRID** where all others areas are its children, self_sufficiency would always be one unless there is an unmatched load from any of the load devices.

![img](img/kpis-1.png)

 