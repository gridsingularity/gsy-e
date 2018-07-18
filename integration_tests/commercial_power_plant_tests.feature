Feature: Commercial Power Plant tests

  Scenario: Finite power plant
     Given we have a scenario named strategy_tests/finite_power_plant
     And d3a is installed
     When we run the d3a simulation with strategy_tests.finite_power_plant [24, 15, 15]
     Then the Finite Commercial Producer always sells energy at the defined energy rate
     And the Finite Commercial Producer never produces more power than its max available power

  Scenario: Finite power plant profile
     Given we have a scenario named strategy_tests/finite_power_plant_profile
     And d3a is installed
     When we run the d3a simulation with strategy_tests.finite_power_plant_profile [24, 15, 15]
     Then the Finite Commercial Producer Profile always sells energy at the defined energy rate
     And the Finite Commercial Producer Profile never produces more power than its max available power

  Scenario: Commercial Producer Market Maker Rate
     Given we have a scenario named strategy_tests/commercial_producer_market_maker_rate
     And d3a is installed
     And we have a profile of market_maker_rate for strategy_tests.commercial_producer_market_maker_rate
     When we run the d3a simulation with config parameters [1, 5] and strategy_tests.commercial_producer_market_maker_rate
     Then we test that config parameters are correctly parsed for strategy_tests.commercial_producer_market_maker_rate [1, 5]
     And the Commercial Energy Producer always sells energy at the defined market maker rate
