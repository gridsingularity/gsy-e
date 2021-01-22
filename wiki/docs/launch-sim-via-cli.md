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
Usage: d3a [OPTIONS] COMMAND [ARGS]...

Options:
  -l, --log-level [CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG|NOTSET|TRACE]
                                  Log level  [default: INFO]
  --help                          Show this message and exit.

Commands:
  run*

Usage: d3a run [OPTIONS]

Options:
  -d, --duration INTERVAL         Duration of simulation  [default: 1d]
  -t, --tick-length INTERVAL      Length of a tick  [default: 1s]
  -s, --slot-length INTERVAL      Length of a market slot  [default: 15m]
  --slot-length-realtime INTERVAL
                                  Desired duration of slot in realtime  [default: 0s]
  -c, --cloud-coverage INTEGER    Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds.  [default: 0]
  -m, --market-count INTEGER      Number of tradable market slots into the future  [default: 1]
  --setup TEXT                    Simulation setup module use. Available modules: [1000_houses,
                                  area_events.cloud_coverage_event, area_events.disable_interval_event,
                                  area_events.disconnect_interval_event, area_events.isolated_connect_event,
                                  area_events.isolated_disable_event, area_events.isolated_disconnect_event,
                                  area_events.isolated_enable_event, area_events.load_event,
                                  area_events.predefined_load_event, area_events.predefined_pv_event,
                                  area_events.pv_event, area_events.storage_event, area_events.userprofile_pv_event,
                                  balancing_market.default_2a, balancing_market.one_load_one_pv,
                                  balancing_market.one_load_one_storage, balancing_market.one_storage_one_pv,
                                  balancing_market.test_device_registry, balancing_market.two_sided_one_load_one_pv,
                                  chaos_experiment.chaos_experiment_babysteps,
                                  chaos_experiment.chaos_experiment_training, chaos_experiment.oracle_api_template,
                                  config_parameter_test, default_2, default_2a, default_2b, default_3,
                                  default_3_pv_only, default_3a, default_3b, default_4, default_5, default_csv,
                                  grid_fees.constant_grid_fees, grid_fees.default_2a, grid_fees.no_trades_high_fees,
                                  grid_fees.non_compounded_grid_fees, grid_fees.test_grid_fees,
                                  hackathon_training.HackTrain_01, hackathon_training.HackTrain_01_simple,
                                  hackathon_training.agent_api_template, hackathon_training.grid_api_template,
                                  jira.d3asim_1024, jira.d3asim_1139, jira.d3asim_1525, jira.d3asim_1531,
                                  jira.d3asim_1535, jira.d3asim_1862, jira.d3asim_1896, jira.d3asim_2034,
                                  jira.d3asim_2244, jira.d3asim_2303, jira.d3asim_2420, jira.d3asim_2421,
                                  jira.d3asim_2422, jira.d3asim_2948, jira.d3asim_778, jira.d3asim_780,
                                  jira.d3asim_869, jira.d3asim_871, jira.d3asim_895, jira.d3asim_895_pr1,
                                  jira.d3asim_895_pr2, jira.d3asim_895_pr3, jira.d3asim_962,
                                  jira.default_2off_d3asim_1475, jira.default_595, jira.default_645, jira.default_737,
                                  json_arg, json_file, kpi.d3asim_2103, kpi.d3asim_2103_2_sided_pab,
                                  kpi.d3asim_2103_nopv1, kpi.d3asim_2103_nopv1_2_sided_pab, kpi.d3asim_2262,
                                  kpi.house_fully_self_sufficient, kpi.house_not_self_sufficient,
                                  kpi.house_partially_self_sufficient, kpi.house_self_sufficient_with_ess,
                                  kpi.infinitebus_pv_load, kpi.market_maker_and_load, kpi.penalty_load,
                                  kpi.penalty_pv, kpi.root_area_self_sufficient_with_infinitebus,
                                  odyssey_momentum.assets_api_template, odyssey_momentum.markets_api_template,
                                  odyssey_momentum.odyssey_training, power_flow.baseline_peak_energy,
                                  power_flow.net_energy_flow, power_flow.test_power_flow,
                                  redis_communication_default_2a, sam_config, sam_config_const_load, sam_config_small,
                                  strategy_tests.commercial_producer_market_maker_rate,
                                  strategy_tests.ess_capacity_based_sell_offer,
                                  strategy_tests.ess_sell_offer_decrease_rate, strategy_tests.external_devices,
                                  strategy_tests.external_ess_bids, strategy_tests.external_ess_offers,
                                  strategy_tests.external_market_stats, strategy_tests.finite_power_plant,
                                  strategy_tests.finite_power_plant_profile, strategy_tests.home_cp_ess_load,
                                  strategy_tests.home_hybrid_pv_ess_load, strategy_tests.infinite_bus,
                                  strategy_tests.market_maker_not_grid_connected,
                                  strategy_tests.market_maker_strategy, strategy_tests.predefined_pv_test,
                                  strategy_tests.pv_const_price_decrease, strategy_tests.pv_final_selling_rate,
                                  strategy_tests.pv_max_panel_output, strategy_tests.pv_max_panel_power_global,
                                  strategy_tests.storage_buys_and_offers,
                                  strategy_tests.storage_strategy_break_even_hourly,
                                  strategy_tests.user_profile_load_csv, strategy_tests.user_profile_load_csv_multiday,
                                  strategy_tests.user_profile_load_dict, strategy_tests.user_profile_pv_csv,
                                  strategy_tests.user_profile_pv_dict, strategy_tests.user_profile_wind_csv,
                                  strategy_tests.user_rate_profile_load_dict, tobalaba.one_producer_load,
                                  two_sided_market.default_2a, two_sided_market.default_2a_high_res_graph,
                                  two_sided_market.infinite_bus, two_sided_market.jira_d3asim-1675,
                                  two_sided_market.offer_reposted_at_old_offer_rate,
                                  two_sided_market.one_cep_one_load,
                                  two_sided_market.one_cep_one_load_immediate_match,
                                  two_sided_market.one_load_5_pv_partial, two_sided_market.one_load_one_storage,
                                  two_sided_market.one_pv_one_load, two_sided_market.one_pv_one_storage,
                                  two_sided_market.one_storage_5_pv_partial,
                                  two_sided_market.user_min_rate_profile_load_dict,
                                  two_sided_market.with_balancing_market, two_sided_pay_as_clear.default_2a,
                                  two_sided_pay_as_clear.jira_d3asim_1690,
                                  two_sided_pay_as_clear.multiple_offers_one_bid,
                                  two_sided_pay_as_clear.one_offer_multiple_bids,
                                  two_sided_pay_as_clear.one_offer_one_bid,
                                  two_sided_pay_as_clear.test_clearing_energy]

  -g, --settings-file TEXT        Settings file path
  --seed TEXT                     Manually specify random seed
  --paused                        Start simulation in paused state  [default: False]
  --pause-at TEXT                 Automatically pause at a certain time. Accepted Input formats: (YYYY-MM-DD, HH:mm)
                                  [default: disabled]

  --repl / --no-repl              Start REPL after simulation run.  [default: False]
  --no-export                     Skip export of simulation data
  --export-path TEXT              Specify a path for the csv export files (default: ~/d3a-simulation)
  --enable-bc                     Run simulation on Blockchain
  --compare-alt-pricing           Compare alternative pricing schemes
  --enable-external-connection    External Agents interaction to simulation during runtime
  --start-date DATE               Start date of the Simulation (YYYY-MM-DD)  [default: 2021-01-15]
  --help                          Show this message and exit.
```
