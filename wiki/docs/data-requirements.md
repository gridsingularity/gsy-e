Users who would like to create an energy community in Grid Singularity Exchange using their own data instead of the template data need to collect the following information:

1. **Grid topology**: a description of the location of energy assets and groups of the assets.

2. **Energy assets specifications**: Disaggregated data (not net meter) is recommended to efficiently connect and measure performance, provided as csv files in the following upload format for each of the assets:
    - **Consumption (Load Profile)**
        - Name (can be anonymous) and location
        - energy consumed over the last 15 minutes by each house in kWh
        - and/or if houses have more granularity and have data for specific loads within a house, it is possible to either aggregate them or simulate different assets inside the house using their average power (kW) and the number of hours of use per day.
    - **PV (Solar panel)**
        - Name (can be anonymous) and location
        - energy produced over the last 15 minutes by each PV plant in kWh and/or
        - peak production of PV panels in Wh in order for the software to generate the Gaussian profile automatically and/or
        - capacity in kW, including tilt and azimuth of the PV
    - **Wind**
        - Name (can be anonymous) and location
        - Energy produced over the last 15 minutes by each wind turbine in kWh
    - **Storage (Battery)**
        - Name (can be anonymous) and location
        - capacity in kWh
        - power delivery in kW
        - Minimum SOC in % and/or
        - actual SOC (sent each 15 minutes) (optional) and
        - actual charge/discharge rate (sent each 15 minutes) (optional)
3. **Grid pricing information**
    - Feed-in structures
    - Conventional (utility) energy price (profile)
    - Grid tariffs (fixed value or profile)

To use a custom data profile into energy assets, users can upload their own file as long as they follow the requirements.

Grid Singularity Exchange currently only supports Comma Separated Values files (.csv). The separation can be done by comma `,` or semicolon `;`. Two time formats are supported, see below. All entered csv data values need to be positive.

##Comma Separated Values (.csv)

The separation can be done by comma `,` or semicolon `;`. Two time formats are supported, see below. All entered csv data values need to be positive

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

Note: If you upload csv files with date information, the **start-date** of the simulation should be identical in the csv files and simulation settings.
