To send live data streams through the Exchange SDK, please follow these steps:

1. Install the SDK Client by following the steps described [here](configure-trading-strategies-walkthrough.md). Since the client is written in Python, the data stream pipeline needs to be written in Python as well.
2. Add the following command in the [Grid Singularity Asset SDK Script](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_template.py){target=_blank} to set the energy consumption and generation for Load and PV assets for the next market slot:

```
asset_client.set_energy_forecast(<energy_forecast_Wh>)
```

An example of how sending forecasts through the SDK Client could be added into the Asset API script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/test_sending_energy_forecast.py){target=_blank}.
