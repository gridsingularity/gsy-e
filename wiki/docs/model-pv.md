A photovoltaic (PV) is an energy asset that converts solar irradiation into electricity. In our software, each PV component can represent a single panel, array of panels or an entire PV park.

##User Interface Configuration

The following parameters can be configured:

*   **Name**: Must be unique
*   **Panel count**: Number of PV panels, each with a power of 250W.
*   **Solar Profile**: The user can choose among multiple template solar profiles (sunny, partially cloudy or cloudy). The usery can also create a custom Gaussian curve or upload their own generation profile.
*   **Initial selling rate**: Initial (and maximum) energy rate that the PV offers at the beginning of each market slot in cents/kWh.
*   **Final selling rate**: Final energy rate that the PV offers at the end of each market slot in cents/kWh.
*   **Rate decrease**: Explicit rate decrease increment in cents/kWh.
*   **Fit to limits**: Derive bidding behavior from a linear fitted curve of a selling rate ranging from initial_selling_rate to final_selling_rate within the bidding interval. If activated, energy_rate_decrease_per_update = (initial_selling_rate - final_selling_rate) / max(int((slot_length / update_interval) -1), 1)
*   **Update interval**: The frequency at which the rate is updated.

The PV configuration interface is shown in the figure below:

![alt_text](images/image1.png "image_tooltip")


##Backend Configuration

There are two options to implement a PV in a backend: 

[Solar Profile](https://github.com/gridsingularity/d3a/blob/c2976cb4f0c8c2823ee755fa33c3efd611498ea0/src/d3a/models/strategy/pv.py) (for template generation profile)


```python
Market ('H2 PV', strategy=PVStrategy(panel_count=4, initial_selling_rate=30, final_selling_rate=5, fit_to_limit=True, update_interval=duration(minutes=5)))
```

[User Profile](https://github.com/gridsingularity/d3a/blob/c2976cb4f0c8c2823ee755fa33c3efd611498ea0/src/d3a/models/strategy/predefined_pv.py#L131-L178) (for uploaded generation profile)


```python
user_profile_path = os.path.join(d3a_path, "assets/Solar_Curve_W_sunny.csv")
Market ('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                             panel_count=))
```
