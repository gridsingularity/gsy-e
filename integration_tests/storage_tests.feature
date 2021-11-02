Feature: Storage tests

  Scenario: Storage sell offers decrease
     Given we have a scenario named strategy_tests/ess_sell_offer_decrease_rate
     And gsy_e is installed
     When we run the simulation with setup file strategy_tests.ess_sell_offer_decrease_rate and parameters [24, 60, 60]
     Then the storage devices sell energy respecting the break even prices

  Scenario: Storage break even hourly profile
     Given we have a scenario named strategy_tests/storage_strategy_break_even_hourly
     And gsy_e is installed
     When we run the simulation with setup file strategy_tests.storage_strategy_break_even_hourly and parameters [24, 60, 60]
     Then the storage devices buy and sell energy respecting the hourly break even prices

  Scenario: Storage capacity dependant sell price
   Given we have a scenario named strategy_tests/ess_capacity_based_sell_offer
   And gsy_e is installed
   When we run the simulation with setup file strategy_tests.ess_capacity_based_sell_offer and parameters [24, 60, 60]
   Then the storage devices sell offer rate is based on it SOC

  Scenario: Storage buys and offers energy in the same market slot
   Given we have a scenario named strategy_tests/storage_buys_and_offers
   And gsy_e is installed
   When we run the simulation with setup file strategy_tests.storage_buys_and_offers and parameters [24, 60, 60]
   Then the SOC reaches 100% within the first 2 market slots
