The following parameters can be set in the Load Strategy: 



- **Name:** Must be unique. When number of duplicates greater than 1, a number is appended to the individual names.
- **Load profile**: The user can choose between two options:
    - User configured profile (in which case a load profile can be uploaded that is compliant with [Upload File Formats](upload-file-formats.md)) 
    - User Upload Profile (in which case the user has to provide the Average Power of the load)
- **Average power:** Average power consumed by the load. 
- **Hours per day:** The number of hours the Load operates per day. 
- **Hours of day:** The time range in which the load operates. 
- **Initial buying rate:** Initial energy buying rate at the beginning of each market slot.
- **Final buying rate:** Final energy buying rate at the end of each market slot.
- **Rate increase:** Explicit rate increase increment
- **Fit to limits:** Derive bidding behavior from a linear fitted curve of a buying rate between `initial_buying_rate` and `final_buying_rate` within the bidding interval. If activated, `energy rate_increase = (final_buying_rate - initial_buying_rate) / max(int((slot_length / update_interval) -1), 1)` 
- **Update interval:** The frequency at which the rate is updated.

For further general information about this strategy follow the backend [Load Strategy](load-strategy.md) manual.

The configuration interface is shown below:

![img](img/load-1.png)