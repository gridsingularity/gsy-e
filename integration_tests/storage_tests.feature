Feature: Storage tests

  Scenario: Storage break even range profile
     Given we have a scenario named strategy_tests/storage_strategy_break_even_range
     And d3a is installed
     When we run the d3a simulation with strategy_tests.storage_strategy_break_even_range [24, 15, 15]
     Then the storage devices buy and sell energy respecting the break even prices

  Scenario: Storage sell offers decrease
     Given we have a scenario named strategy_tests/ess_sell_offer_decrease_based_on_risk_or_rate
     And d3a is installed
     When we run the d3a simulation with strategy_tests.ess_sell_offer_decrease_based_on_risk_or_rate [24, 15, 15]
     Then the storage devices sell energy respecting the break even prices

  Scenario: Storage break even hourly profile
     Given we have a scenario named strategy_tests/storage_strategy_break_even_hourly
     And d3a is installed
     When we run the d3a simulation with strategy_tests.storage_strategy_break_even_hourly [24, 15, 15]
     Then the storage devices buy and sell energy respecting the hourly break even prices

  Scenario: Storage capacity dependant sell price
   Given we have a scenario named strategy_tests/ess_capacity_based_sell_offer
   And d3a is installed
   When we run the d3a simulation with strategy_tests.ess_capacity_based_sell_offer [24, 15, 15]
   Then the storage devices sell offer rate is based on it SOC

  Scenario: Custom storage works as expected
   Given we have a scenario named jira/d3asim_639_custom_storage
   And d3a is installed
   When we run the d3a simulation with jira.d3asim_639_custom_storage [24, 15, 30]
   Then the storage offers and buys energy as expected at expected prices

