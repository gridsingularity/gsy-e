Command line arguments include: 

- `-d, --duration`: Duration of simulation [default: 24h]
- `-t, --tick-length`: Length of a tick [default: 1s]
- `-s, --slot-length`: Length of a market slot [default: 15m]
- `-c, --cloud-coverage`: Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds. [default: 0]
- `-m, --market-count`: Number of tradable market slots into the future [default: 5]

### Example simulation call:
```
d3a -l ERROR run --duration=24h --tick-length=1s --slot-length=15m --cloud-coverage=0 --market-count=5 --setup default_2a
```
### Getting help in the command line: 
`d3a --help` returns:
```
Usage: d3a [OPTIONS] COMMAND [ARGS]...
 
Options:
  -l, --log-level [CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG|NOTSET|TRACE]
                                  Log level  [default: INFO]
  --help                          Show this message and exit.
 
Commands:
  run*
  resume
```
`d3a run --help` returns:

```
Usage: d3a run [OPTIONS]
 
Options:
  -d, --duration INTERVAL       Duration of simulation  [default: 1d]
  -t, --tick-length INTERVAL    Length of a tick  [default: 1s]
  -s, --slot-length INTERVAL    Length of a market slot  [default: 15m]
  -c, --cloud-coverage INTEGER  Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds.  [default: 0]
  -m, --market-count INTEGER    Number of tradable market slots into the future  [default: 1]
  --setup TEXT                  Simulation setup module use. Available modules: [1000_houses,
                                area_events.cloud_coverage_event, area_events.disable_interval_event,
                                area_events.disconnect_interval_event, area_events.isolated_connect_event,
                                area_events.isolated_disable_event, area_events.isolated_disconnect_event,
                                area_events.isolated_enable_event, area_events.load_event, area_events.pv_event,
                                area_events.storage_event, balancing_market.default_2a,
                                balancing_market.one_load_one_pv, balancing_market.one_load_one_storage,
                                balancing_market.one_storage_one_pv, balancing_market.test_device_registry,
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
  --slowdown INTEGER            Slowdown factor [0 - 10,000]. Where 0 means: no slowdown, ticks are simulated as fast
                                as possible; and 100: ticks are simulated in realtime
  --seed TEXT                   Manually specify random seed
  --paused                      Start simulation in paused state  [default: False]
  --pause-at TEXT               Automatically pause at a certain time. Accepted Input formats: (YYYY-MM-DD, HH:mm)
                                [default: disabled]
  --repl / --no-repl            Start REPL after simulation run.  [default: False]
  --no-export                   Skip export of simulation data
  --export-path TEXT            Specify a path for the csv export files (default: ~/d3a-simulation)
  --enable-bc                   Run simulation on Blockchain
  --compare-alt-pricing         Compare alternative pricing schemes
  --start-date DATE             Start date of the Simulation (YYYY-MM-DD)  [default: 2019-09-27]
  --help                        Show this message and exit.
```