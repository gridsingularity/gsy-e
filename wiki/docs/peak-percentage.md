
![alt_text](img/peak-percentage-1.png)

The energy peak imports/exports is the maximum value of the aggregate imports/exports of each asset inside a market. The user has the possibility to set a `baseline_peak_energy_import_kWh` and a `baseline_peak_energy_export_kWh` that they may have gotten from another simulation in order to calculate the energy peak percentage, a tool used to measure how much the peak imports or exports have changed between a defined baseline and the current simulation.

The user may be interested in the Energy Peak Percentage value to assess the impact of applied [grid fees](grid-fee-accounting.md) or different energy [storage](model-storage.md) strategies on the **peak imports** and **exports** of a market.

The Energy Peak Percentage can be calculated as follows :

```
Import_peak_percentage = import_peak_energy_kWh / import_baseline_peak_energy_kWh * 100
Export_peak_percentage = export_peak_energy_kWh / export_baseline_peak_energy_kWh * 100
```

If the energy peak percentage is **below 100%**, the peak was **reduced** vs. the baseline. The energy peak was **increased** if the energy peak percentage value is **above 100%**.
