Markets contain submarkets and energy assets. Energy assets can post bids and offers in their market. Markets are interconnected by [inter-area agents](inter-area-agent.md) in a hierarchical network, which pass bids and offers between markets until they are matched, following a select [market clearing mechanism](clearing-purpose.md). 

##Modelling in the User Interface

The following market parameters can be set: 

*   **Name**: Must be unique
*   **Grid fee**: If set to _yes_ and with a _non-None_ value, a fee will be applied to each trade that passes through or is cleared in this market. The grid fee is either constant, expressed in cents/kWh, or variable, expressed as a share of total price in percentage terms (%) depending on the parameters set in the simulation general settings. For more, see grid fee accounting page.
*   **Transformers capacity**: Import and export limits of the transformer in kVA. In the current implementation these limits are purely visual indicators and do not limit actual import/export of the market.
*   **Baseline import/export**: Allows the user to compare the current simulation imports/exports to a baseline, set in kWh. These values are used in the calculation of the Peak Percentage KPI.

The simulation configuration interface is shown below:

![alt_text](images/image1.png "image_tooltip")


##Modelling in the Backend

These parameters can be set in the backend in the Area / Market class : 

```python
Area('Market',
                         [
... "some assets here"                             
                         ], 
grid_fee_constant=2, 
throughput=ThroughputParameters(import_capacity_kVA=2.0, export_capacity_kVA=2.0, baseline_peak_energy_import_kWh=0.4, baseline_peak_energy_export_kWh=0.4))
```
