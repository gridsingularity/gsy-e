After running a simulation in the backend, the user can export simulation results. This functionality is enabled by default. If you want to disable the export of simulation results, use the --no-export flag for the simulation run. Another useful parameter is: `--export-path`, used to change the output path of the simulation results. The default path is `$HOME/gsy-e-simulation/`.

The simulation results include analytical information about the bids, offers and trades that took place in the course of the simulation. Information about energy characteristics of each asset and market are also included (eg. battery state of charge, energy traded/requested/deficit). A detailed description of these files is available on the [result download page](results-download.md).

In addition to text files, some graphs that display aggregated market information during the course of the simulation are also exposed. These can be found under the `plot/` directory and are very similar to the ones available in the UI:

* **energy_profile_*.html**: Similar plot to energy trade profile
* **average_trade_price_*.html**: Similar plot to energy pricing
* **asset_profile_*.html**: each energy asset within the simulation has its own plot showing its profile (consumption, generation, State of Charge), the actual energy traded and energy rates.
