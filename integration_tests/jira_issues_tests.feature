Feature: Jira Issues Tests

   Scenario: D3ASIM-595, average trade rate should be constant for every market slot
     Given we have a scenario named jira/default_595
     And d3a is installed
     When we run the d3a simulation with jira.default_595 [24, 15, 15]
     Then average trade rate is constant for every market slot for all markets
     And there are no trades with the same seller and buyer name

   Scenario: D3ASIM-645, storage should buy energy from commercial producer
     Given we have a scenario named jira/default_645
     And d3a is installed
     When we run the d3a simulation with jira.default_645 [24, 15, 15]
     Then storage buys energy from the commercial producer
     And storage final SOC is 100%
     And storage buys energy respecting the break even buy threshold