These parameters can be set in the backend in the Market class :

```JSON
Market('Market',
       [
           ... "some assets here"
       ],
       grid_fee_constant=2,
       throughput=ThroughputParameters(import_capacity_kVA=2.0, export_capacity_kVA=2.0, baseline_peak_energy_import_kWh=0.4, baseline_peak_energy_export_kWh=0.4))

```
