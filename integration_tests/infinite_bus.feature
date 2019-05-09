Feature: Infinite Bus tests

  Scenario Outline: Infinite Bus behaviour
    Given we have a scenario named <scenario>
    And d3a is installed
    And the market type is <market_type>
    When we run the d3a simulation with <scenario> [24, 60, 60]
    Then Infinite Bus buys energy that is not needed from the PV and sells to the load
  Examples: Market Type
     | scenario                      | market_type |
     | strategy_tests.infinite_bus   |      1      |
     | two_sided_market.infinite_bus |      2      |

