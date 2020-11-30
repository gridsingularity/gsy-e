Feature: Alternative Pricing

  Scenario: CLI parameter works and 4 subdirectories for results are created
    Given we have a scenario named jira/d3asim_895
    And d3a is installed
    When we run the d3a simulation with compare-alt-pricing flag with jira.d3asim_895
    Then we test the export of with compare-alt-pricing flag

  @disabled
  Scenario Outline: Pricing for alternative pricing is right
    # Scenario with one sided market is failing due to storage state issue
    Given we have a scenario named <scenario>
    And d3a is installed
    When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 1]
    Then average trade rate is the MMR until <time1>
    And average trade rate between <time1> & <time2> is <trade_rate>
  Examples: Settings
     | scenario            |  time1   | time2   | trade_rate |
     | jira.d3asim_895_pr1 |    8     |   17    |    0       |
     | jira.d3asim_895_pr2 |    8     |   17    |    15      |
     | jira.d3asim_895_pr3 |    8     |   17    |    30     |