Users who would like to model a local energy market (an energy community participating in peer-to-peer trading) in the Grid Singularity Exchange using their own data instead of the template (synthetic) data need to collect the following information, usually for at least one-month or one-week period in at least two seasons:

* **Grid topology**: a diagram or a brief description of the location of community members and their energy assets and/or any other available assets for community supply like wind turbines and community PV
* **Energy assets specifications**: Disaggregated data (not net metre) is recommended to efficiently connect and measure performance, provided ideally at 15-minute interval, as csv files (upload format described below) for each of the assets (if not available, home/building metre data can be provided) together with complementary information, as follows:
    * **Consumption (Load Profile)**
        * Name (can be anonymous, e.g. Load1) and location
        * Energy consumed per time interval by each asset/home in kWh
    * **PV (Solar panel)**
        * Name (can be anonymous, e.g. PV1) and location
        * Energy produced per time interval by each PV in kWh and/or
        * PV capacity in kW, including tilt and azimuth
    * **Wind**
        * Name (can be anonymous, e.g. Wind1) and location
        * Energy produced per time interval by each wind turbine in kWh
    * **Storage (Battery)**
        * Name (can be anonymous, e.g. Battery1) and location
        * Capacity in kWh
        * Charge / discharge power in kW
        * Maximum charge/discharge power in kW
        * Minimum SOC in % and/or actual SOC in timeseries (optional)
    * **Heat Pumps**
        * Name (can be anonymous, e.g. HP1) and location
        * Maximum power rating (based on nameplate)
        * Volume of thermal storage tank if applicable (based on nameplate)
        * Minimum and maximum comfort temperature
        * Heat demand of the homes/building in kWh per time interval
        * Heat pump water tank temperature (time series profile)
        * Ambient temperature profile to configure the heat pump performance
* **Grid Market Pricing Information**
    * Feed-in-tariff
    * Conventional (utility) energy price (profile) per community member
    * Grid tariffs (fixed value or profile)
- **Market Mechanism Data:** User, simulating the role of community manager, selects preferred buying and selling prices (default setting to buy at the best available price between utility and fee-in-tariff rate) based on a [pay-as-bid mechanism](market-types.md#two-sided-pay-as-bid-market) (other mechanisms in development).

For the upload format, Grid Singularity Exchange currently only supports Comma Separated Values files (.csv).

##Comma Separated Values (.csv)

The separation can be done by comma `,` or semicolon `;`.

Two time formats are supported, see below. All entered csv data values need to be positive

###hh:mm

**Example:**

```
INTERVAL;ENERGY(kWh):
00:00;10
00:15;10
00:30;10
00:45;10
01:00;10
```

###YYYY-MM-DDThh:mm

**Example:**

```
INTERVAL,ENERGY(kWh)
2019-01-01T00:00,10.0
2019-01-01T00:15,10.0
2019-01-01T00:30,10.0
2019-01-01T00:45,10.0
2019-01-01T01:00,10.0
```
