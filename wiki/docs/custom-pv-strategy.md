Instead of a pre-configured file, the user can also upload their own PV profile in Watts in the backend. The user can do this by uploading a csv file or inputing the profile directly in the grid configuration (setup) file. There are two demonstration setup files to show this feature:

- `user_profile_pv_csv.py`

In this setup file, the csv file is connected to the configuration via a pathway:

```
user_profile_path = os.path.join(d3a_path,"resources/Solar_Curve_W_sunny.csv")
```

Comma or semicolon separated values are allowed. The timestamp can be provided in two formats: `HH:mm`, `YYYY-MM-DDTHH:mm`. For more information on what format is accepted by the D3A, see "[Upload File Formats](upload-file-formats.md)".

- `user_profile_pv_dict.py`

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

Corresponding code: `src/d3a/models/strategy/predefined_pv.py`

How to add a PV device with custom profile to the setup-file:

```
user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")
Area('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                             panel_count=),
              appliance=PVAppliance()),
```