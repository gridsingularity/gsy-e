Feature: Infinite Bus tests

  Scenario Outline: Infinite Bus behaviour
    Given we have a scenario named <scenario>
    And gsy_e is installed
    And the market type is <market_type>
    And export is_needed
    When we run the simulation with setup file <scenario> and parameters [24, 60, 60]
    Then Infinite Bus buys energy that is not needed from the PV and sells to the load
  Examples: Market Type
     | scenario                      | market_type |
     | strategy_tests.infinite_bus   |      1      |
     | two_sided_market.infinite_bus |      2      |


  Scenario: InfiniteBus Respects its buy/sell rate
    Given we have a scenario named two_sided_market.jira_d3asim-1675
    And gsy_e is installed
    When we run the simulation with setup file two_sided_market.jira_d3asim-1675 and parameters [24, 60, 60]
    Then the infinite bus traded energy respecting its buy/sell rate
