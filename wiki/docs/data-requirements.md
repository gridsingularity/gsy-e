If you wish to base your digital twin simulation of an energy community using your own data rather than the provided templates, you need to collect the following: 

1. **Grid topology**: a description of the location of energy assets and their grouping.
2. **Energy assets specifications: Disaggregated data** (not net meter) is recommended to efficiently connect and measure performance, provided as csv files in the following [upload format](upload-file-formats.md) for each of the assets:
   
    **Load**
  
    * Name (anonymised) and geolocation
    * Energy consumed over the last 15 minutes by each house in kWh, and/or:
    * If houses have more granularity and have data for specific loads within a house, it is possible to either aggregate them or simulate different assets inside the house using their average power (kW) and the number of hours of use per day.

    **PV**
  
    * Name (anonymised) and geolocation
    * Energy produced over the last 15 minutes by each PV plant and/or
    * Peak production of PV panel in kW in order for the software to generate the Gaussian profile automatically.

    **Storage**
  
    * Name (anonymised) and geolocation
    * Capacity in kWh
    * Power delivery in kW
    * Minimum SOC in % and/or
    * Actual SOC (sent each 15 minutes)
    * Actual charge/discharge rate (sent each 15 minutes).

3. **Grid pricing information**
   
      a. Feed-in structures
   
      b. Conventional (utility) energy price (profile)
   
      c. Grid tariffs (profile).

For the Canary Test Network Implementation, a **live data stream of energy assets** should be reported through our API following the similar format logic as explained above. If you are interested to connect your community to a canary test network please [contact us](mailto:contact@gridsingularity.com).
    
   


