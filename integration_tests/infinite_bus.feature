Feature: Infinite Bus tests

  Scenario: Infinite Bus one-sided market behaviour
    Given we have a scenario named strategy_tests/infinite_bus
    And d3a is installed
    When we run the d3a simulation with strategy_tests.infinite_bus [24, 60, 60]
    Then Infinite Bus buys energy that is not needed from the PV

  Scenario: Infinite Bus two-sided PAB market behaviour
    Given we have a scenario named two_sided_market/infinite_bus
    And d3a is installed
    When we run the d3a simulation with two_sided_market.infinite_bus [24, 60, 60]
    Then Infinite Bus buys energy from the PV and sells to the load