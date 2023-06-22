The following parameters are part of [Simulation Config](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/config.py#L33){target=_blank} and are initialised before updating any [ConstSettings](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/constants_limits.py){target=_blank}:

*   sim_duration
*   slot_length
*   tick_length
*   cloud_coverage*
*   market_maker_rate*
*   grid_fee_pct*
*   grid_fee_const*
*   pv_user_profile*
*   max_panel_power_W

In order to update some of these parameters (starred in list above), please use `update_config_parameters` method to update the general configuration parameters in the setup file:

```python
def get_setup(config):
    config.update_config_parameters(grid_fee_pct=5,
                                    grid_fee_const=35,
                                    cloud_coverage=2,
                                    pv_user_profile="<path>/<profile_name>",
                                    market_maker_rate=30)
market = Market(
    'Grid',
    [
        Asset('General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                         hrs_per_day=4,
                                                         hrs_of_day=list(range(12, 16)),
                                                         final_buying_rate=35)
              ),
        Asset('PV', strategy=PVStrategy(4, 80)
              ),
    ],
    config=config
)
return market

```

####Simulation launch

Once the entire market architecture is modelled, including energy assets, the user can launch the trading simulation by running a command line including desired setup features:

*   -d, --duration: simulated duration of simulation [default: 1d]
*   -t, --tick-length: simulated duration of a tick [default: 1s]
*   -s, --slot-length: simulated duration of a market slot [default: 15m]
*   -c, --cloud-coverage: Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds. [default: 0]
*   --slot-length-realtime: Desired duration of slot in realtime [default: 0s]

Example simulation call:
```commandline
gsy-e -l ERROR run --duration=1d --tick-length=1s --slot-length=15m --cloud-coverage=0 --setup default_2a
```

Getting help in the command line:

```commandline
gsy-e --help returns:
```

```
Usage: gsy-e [OPTIONS] COMMAND [ARGS]...


Options:

  -l, --log-level [CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG|NOTSET|TRACE]

                                  Log level  [default: INFO]

  --help                          Show this message and exit.

Commands:

  run*

  resume

gsy-e run --help returns:

Usage: gsy-e run [OPTIONS]

Options:

  -d, --duration INTERVAL       Duration of simulation  [default: 1d]

  -t, --tick-length INTERVAL    Length of a tick  [default: 1s]

  -s, --slot-length INTERVAL    Length of a market slot  [default: 15m]

--slot-length-realtime INTERVAL

                                  Desired duration of slot in realtime  [default: 0s]

  -c, --cloud-coverage INTEGER  Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds.  [default: 0]

  --setup TEXT                  Simulation setup module use. Available modules: [1000_houses,

                                market_events.cloud_coverage_event, market_events.disable_interval_event,

                                market_events.disconnect_interval_event, market_events.isolated_connect_event,

                                market_events.isolated_disable_event, market_events.isolated_disconnect_event,

                                market_events.isolated_enable_event, market_events.load_event, market_events.pv_event,

                                market_events.storage_event, balancing_market.default_2a,

                                balancing_market.one_load_one_pv, balancing_market.one_load_one_storage,

                                balancing_market.one_storage_one_pv, balancing_market.test_asset_registry,

                                balancing_market.two_sided_one_load_one_pv, config_parameter_test, default_2,

                                default_2a, default_2b, default_3, default_3_pv_only, default_3a, default_3b,

                                default_4, default_5, default_addcurve, default_addcurve2, default_csv,

                                graphs_testing, jira.d3asim_1024, jira.d3asim_1139, jira.d3asim_638_custom_load,

                                jira.d3asim_639_custom_storage, jira.d3asim_640_custom_pv, jira.d3asim_778,

                                jira.d3asim_780, jira.d3asim_869, jira.d3asim_871, jira.d3asim_895,

                                jira.d3asim_895_pr1, jira.d3asim_895_pr2, jira.d3asim_895_pr3, jira.d3asim_962,

                                jira.default_2off_d3asim_1475, jira.default_595, jira.default_611, jira.default_613,

                                jira.default_623, jira.default_645, jira.default_737, jira.test_strategy_custom_load,

                                jira.test_strategy_custom_pv, jira.test_strategy_custom_storage, json_arg, json_file,

                                non_compounded_grid_fees, redis_communication_default_2a, sam_config,

                                sam_config_const_load, sam_config_small,

                                strategy_tests.commercial_producer_market_maker_rate,

                                strategy_tests.ess_capacity_based_sell_offer,

                                strategy_tests.ess_sell_offer_decrease_based_on_risk_or_rate,

                                strategy_tests.finite_power_plant, strategy_tests.finite_power_plant_profile,

                                strategy_tests.home_cp_ess_load, strategy_tests.home_hybrid_pv_ess_load,

                                strategy_tests.infinite_bus, strategy_tests.predefined_pv_test,

                                strategy_tests.pv_const_price_decrease, strategy_tests.pv_final_selling_rate,

                                strategy_tests.pv_initial_pv_rate_option, strategy_tests.pv_max_panel_output,

                                strategy_tests.pv_max_panel_power_global, strategy_tests.pv_risk_based_price_decrease,

                                strategy_tests.storage_buys_and_offers,

                                strategy_tests.storage_strategy_break_even_hourly,

                                strategy_tests.user_profile_load_csv, strategy_tests.user_profile_load_csv_multiday,

                                strategy_tests.user_profile_load_dict, strategy_tests.user_profile_pv_csv,

                                strategy_tests.user_profile_pv_dict, strategy_tests.user_profile_wind_csv,

                                strategy_tests.user_rate_profile_load_dict, tobalaba.one_producer_load,

                                two_sided_market.default_2a, two_sided_market.infinite_bus,

                                two_sided_market.offer_reposted_at_old_offer_rate, two_sided_market.one_cep_one_load,

                                two_sided_market.one_load_5_pv_partial, two_sided_market.one_load_one_storage,

                                two_sided_market.one_pv_one_load, two_sided_market.one_pv_one_storage,

                                two_sided_market.one_storage_5_pv_partial,

                                two_sided_market.user_min_rate_profile_load_dict,

                                two_sided_market.with_balancing_market, two_sided_pay_as_clear.default_2a,

                                two_sided_pay_as_clear.test_clearing_energy]

  -g, --settings-file TEXT      Settings file path

  --seed TEXT                   Manually specify random seed

  --paused                      Start simulation in paused state  [default: False]

  --pause-at TEXT               Automatically pause at a certain time. Accepted Input formats: (YYYY-MM-DD, HH:mm)

                                [default: disabled]

  --repl / --no-repl            Start REPL after simulation run.  [default: False]

  --no-export                   Skip export of simulation data

  --export-path TEXT            Specify a path for the csv export files (default: ~/d3a-simulation)

  --enable-bc                   Run simulation on Blockchain

  --start-date DATE             Start date of the Simulation (YYYY-MM-DD)  [default: 2019-09-27]

  --help                        Show this message and exit.
```
