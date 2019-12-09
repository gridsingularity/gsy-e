Instead of configuring the demand behaviour of a load through through `avg_power_W`, `hrs_of_day` and `hrs_per_day` (as described in "[Load Strategy](load-strategy.md)"), the user can also upload their own load profile in Watts in the backend. The user can do this by uploading a .csv file or inputing the profile directly in the grid configuration (setup) file. There are two demonstration setup files to show this feature:

- `user_profile_load_csv.py`

In this setup file, the csv file is connected to the configuration via a pathway :

```
user_profile_path = os.path.join(d3a_path,"resources/LOAD_DATA_1.csv")
```

Comma or semicolon separated values are allowed. The timestamp can be provided in two formats: `HH:mm`, `YYYY-MM-DDTHH:mm`. For more information on what format is accepted by the D3A, see "[Upload File Formats](upload-file-formats.md)".

- `user_profile_load_dict.py`

In this setup file, the user profile is inserted directly into the configuration:

```
user_profile = {
      8: 100,
      9: 200,
      10: 50,
      11: 80,
      12: 120,
      13: 20,
      14: 70,
      15: 15,
      16: 45,
      17: 100
}
```



Corresponding code: `/src/3a/models/strategy/predefined_load.py`



How to add a load device with custom profile to the setup-file:

```
user_profile = {
        8: 100,
        9: 200,
        10: 50,
        11: 80,
        12: 120,
        13: 20,
        14: 70,
        15: 15,
        16: 45,
        17: 100
    }
Area('DefinedLoad', strategy=DefinedLoadStrategy(daily_load_profile=user_profile,
                                                 max_energy_rate=35),
                    appliance=SwitchableAppliance()),
```