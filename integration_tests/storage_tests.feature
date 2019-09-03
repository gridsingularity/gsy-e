Feature: Storage tests

  Scenario: Storage sell offers decrease
     Given we have a scenario named strategy_tests/ess_sell_offer_decrease_based_on_risk_or_rate
     And d3a is installed
     When we run the d3a simulation with strategy_tests.ess_sell_offer_decrease_based_on_risk_or_rate [24, 60, 60]
     Then the storage devices sell energy respecting the break even prices

  Scenario: Storage capacity dependant sell price
   Given we have a scenario named strategy_tests/ess_capacity_based_sell_offer
   And d3a is installed
   When we run the d3a simulation with strategy_tests.ess_capacity_based_sell_offer [24, 60, 60]
   Then the storage devices sell offer rate is based on it SOC

  Scenario: Custom storage works as expected
   Given we have a scenario named jira/d3asim_639_custom_storage
   And d3a is installed
   When we run the d3a simulation with jira.d3asim_639_custom_storage [24, 15, 30]
   Then the storage offers and buys energy as expected at expected prices

  Scenario: Storage buys and offers energy in the same market slot
   Given we have a scenario named strategy_tests/storage_buys_and_offers
   And d3a is installed
   When we run the d3a simulation with strategy_tests.storage_buys_and_offers [24, 60, 60]
   Then the SOC reaches 100% within the first 2 market slots


