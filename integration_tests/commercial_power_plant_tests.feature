Feature: Commercial Power Plant tests

  Scenario: Finite power plant
     Given we have a scenario named strategy_tests/finite_power_plant
     And d3a is installed
     When we run the simulation with setup file strategy_tests.finite_power_plant and parameters [24, 60, 60, 1]
     Then the Finite Commercial Producer always sells energy at the defined energy rate
     And the Finite Commercial Producer never produces more power than its max available power

  Scenario: Finite power plant profile
     Given we have a scenario named strategy_tests/finite_power_plant_profile
     And d3a is installed
     When we run the simulation with setup file strategy_tests.finite_power_plant_profile and parameters [24, 60, 60, 1]
     Then the Finite Commercial Producer Profile always sells energy at the defined energy rate
     And the Finite Commercial Producer Profile never produces more power than its max available power

  Scenario: Commercial Producer Market Maker Rate
     Given we have a scenario named strategy_tests/commercial_producer_market_maker_rate
     And d3a is installed
     And we have a profile of market_maker_rate for strategy_tests.commercial_producer_market_maker_rate
     When we run the d3a simulation with cloud_coverage [1] and strategy_tests.commercial_producer_market_maker_rate
     Then we test that cloud coverage [1] and market_maker_rate are parsed correctly
     And the Commercial Energy Producer always sells energy at the defined market maker rate

  Scenario: Market Maker strategy sets the simulation market maker rate
     Given we have a scenario named strategy_tests/market_maker_strategy
     And d3a is installed
     When we run the simulation with setup file strategy_tests.market_maker_strategy and parameters [24, 60, 60, 1]
     Then all trades are using the market maker rate from the strategy (18.7)
     And the simulation market maker rate is the same as the strategy (18.7)

  Scenario: Market Maker strategy adheres to the grid connected flag
     Given we have a scenario named strategy_tests/market_maker_not_grid_connected
     And d3a is installed
     When we run the simulation with setup file strategy_tests.market_maker_not_grid_connected and parameters [24, 60, 60, 1]
     Then no trades are performed
     And the simulation market maker rate is the same as the strategy (18.7)