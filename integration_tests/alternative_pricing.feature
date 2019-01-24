Feature: Alternative Pricing

  Scenario: CLI parameter works and 4 subdirectories for results are created
    Given we have a scenario named jira/d3asim_895
    And d3a is installed
    When we run the d3a simulation with compare-alt-pricing flag with jira.d3asim_895
    Then we test the export of with compare-alt-pricing flag

  Scenario Outline: Pricing for alternative pricing is right
    Given we have a scenario named <scenario>
    And d3a is installed
    When we run the d3a simulation with <scenario> [None, 24, 30, 15]
    Then average trade rate is the MMR until <time>
    And average trade rate after <time> is <trade_rate>
  Examples: Settings
     | scenario            |  time   | trade_rate |
     | jira.d3asim_895_pr1 |    8    |      0     |
     | jira.d3asim_895_pr2 |    8    |      15    |
     | jira.d3asim_895_pr3 |    8    |      30    |