Feature: Jira Issues Tests

   Scenario: D3ASIM-595, average trade rate should be constant for every market slot
     Given we have a scenario named jira/default_595
     And gsy-e is installed
     When we run the simulation with setup file jira.default_595 and parameters [24, 60, 15]
     Then average trade rate is constant for every market slot for all markets
     And there are no trades with the same seller and buyer name

  Scenario: D3ASIM-645, storage should buy energy from commercial producer
    Given we have a scenario named jira/default_645
    And gsy-e is installed
    When we run the simulation with setup file jira.default_645 and parameters [24, 60, 60]
    Then storage buys energy from the commercial producer
    And storage final SOC is 100%
    And storage buys energy respecting the break even buy threshold

  Scenario: D3ASIM-662, MarketAgent should always track offers back to its source
     Given we have a scenario named strategy_tests/home_cp_ess_load
     And gsy-e is installed
     And export is_needed
     When we run the simulation with setup file strategy_tests.home_cp_ess_load and parameters [24, 60, 60]
     Then all load demands in setup was fulfilled on every market slot
     And on every market slot there should be matching trades on grid and house markets

  @slow
  Scenario: D3ASIM-706, multi-day simulation for load and pv
     Given we have a scenario named default_3
     And gsy-e is installed
     And the min offer age is set to 1 tick
     When we run a multi-day gsy-e simulation with default_3 [None, 72, 15, 60]
     Then pv produces the same energy on each corresponding time slot regardless of the day
     And all loads consume the same energy on each corresponding time slot regardless of the day
     And all loads adhere to the hours of day configuration

  Scenario: D3ASIM-780, Electrolyser does not report 0 soc on first market slot
     Given we have a scenario named jira/d3asim_780
     And gsy-e is installed
     When we run the simulation with setup file jira.d3asim_780 and parameters [24, 60, 60]
     Then there should be a reported SOC of 0.1 on the first market

  Scenario: D3ASIM-778, load reaches maximum price before the end of the market slot
     Given we have a scenario named jira/d3asim_778
     And gsy-e is installed
     When we run the simulation with setup file jira.d3asim_778 and parameters [24, 60, 60]
     Then there should be trades on all markets using the max load rate

  Scenario: D3ASIM-871, unmatched loads are not reported if hours per day are covered
     Given we have a scenario named jira/d3asim_871
     And gsy-e is installed
     And export is_needed
     When we run the simulation with setup file jira.d3asim_871 and parameters [24, 60, 60]
     Then all load demands in setup was fulfilled on every market slot

  @disabled
  Scenario: D3ASIM-874, alternative pricing can buy energy from MarketAgent if there is not enough self-consumption
     Given we have a scenario named jira/d3asim_869
     And gsy-e is installed
     When we run the simulation with setup file jira.d3asim_869 and parameters [24, 60, 60]
     Then the Load of House 1 should only buy energy from MarketAgent between 5:00 and 8:00
     And the Commercial Producer should never sell energy

  # TODO: re-enable in context of bug/D3ASIM-3534
  @disabled
  Scenario: D3ASIM-891, bids are reported correctly in csv export files
     Given we have a scenario named two_sided_pay_as_clear.default_2a
     And gsy-e is installed
     When we run the gsy-e simulation on console with two_sided_pay_as_clear.default_2a for 2 hrs
     Then there are nonempty files with offers (without balancing offers) and bids for every area

  Scenario: D3ASIM-962, Device Statistics are calculated and returned correctly
    Given we have a scenario named jira/d3asim_962
    And gsy-e is installed
    When export is needed
    And we run a multi-day gsy-e simulation with jira.d3asim_962 [2019-01-01, 48, 60, 60]
    Then the device statistics are correct

  @slow
  Scenario: D3ASIM-1139, no unmatched loads on setup with many loads and only one CEP
    Given we have a scenario named jira/d3asim_1139
    And gsy-e is installed
    And export is_needed
    When we run the simulation with setup file jira.d3asim_1139 and parameters [24, 60, 60]
    Then all load demands in setup was fulfilled on every market slot

  Scenario: D3ASIM-1475, default_2off finishes successfully for two-sided pay as clear market
    Given we have a scenario named jira/default_2off_d3asim_1475
    And gsy-e is installed
    Then we run the simulation with setup file jira.default_2off_d3asim_1475 and parameters [24, 60, 60]

  Scenario: D3ASIM-1525, PAC simulation finishes without assert in PAC engine
    Given we have a scenario named jira/d3asim_1525
    And gsy-e is installed
    Then we run the simulation with setup file jira.d3asim_1525 and parameters [24, 60, 60]

  Scenario: D3ASIM-1535, User should not be able to add area to leaf area
    Given we have a scenario named jira/d3asim_1535
    And gsy-e is installed
    And raising exceptions when running the simulation is disabled
    When we run the simulation with setup file jira.d3asim_1535 and parameters [24, 60, 60]
    Then an AreaException is raised

  Scenario: D3ASIM-1531: Trades happen in simulation with only one PAB market in the root area
    Given we have a scenario named jira/d3asim_1531
    And gsy-e is installed
    And gsy-e uses an two-sided-pay-as-bid market
    When we run the simulation with setup file jira.d3asim_1531 and parameters [24, 60, 60]
    Then trades happen when the load seeks energy

  Scenario: D3ASIM-1531: Trades happen in simulation with only one PAC market in the root area
    Given we have a scenario named jira/d3asim_1531
    And gsy-e is installed
    And gsy-e uses an two-sided pay-as-clear market
    When we run the simulation with setup file jira.d3asim_1531 and parameters [24, 60, 60]
    Then trades happen when the load seeks energy

  @disabled
  Scenario: D3ASIM-1637: Pay as bid repeats clearing until all available offers and bids are exhausted
    Given we have a scenario named json_file
    And gsy-e is installed
    And gsy-e uses an two-sided-pay-as-bid market
    And the file jira/d3asim_1637.json is used for the area setup
    When we run the simulation with setup file json_file and parameters [24, 30, 30]
    Then all load demands in setup was fulfilled on every market slot

  # TODO: re-enable in context of bug/D3ASIM-3534
  @disabled
  Scenario: D3ASIM-1690: No unmatched load
    Given we have a scenario named two_sided_pay_as_clear/jira_d3asim_1690
    And gsy-e is installed
    And export is_needed
    When we run the simulation with setup file two_sided_pay_as_clear.jira_d3asim_1690 and parameters [24, 60, 60]
    Then all load demands in setup was fulfilled on every market slot

  Scenario: D3ASIM-1862: DSO doesnt pay the grid fee of the Grid
    Given we have a scenario named jira/d3asim_1862
    And gsy-e is installed
    When export is needed
    And we run the simulation with setup file jira.d3asim_1862 and parameters [3, 15, 15]
    Then the DSO doesnt pay the grid fee of the Grid, but House 1

Scenario: D3ASIM-2034: DSO doesnt pay the grid fee of the Grid
    Given we have a scenario named jira/d3asim_2034
    And gsy-e is installed
    When export is needed
    And we run the simulation with setup file jira.d3asim_2034 and parameters [3, 60, 60]
    Then the DSO doesnt pay the grid fee of the Grid, but Community

  Scenario: D3ASIM-1896: Storage decreases bid rate until final buying rate
    Given we have a scenario named jira/d3asim_1896
    And gsy-e is installed
    When we run the simulation with setup file jira.d3asim_1896 and parameters [6, 60, 60]
    Then the storage decreases bid rate until final buying rate

  Scenario: D3ASIM-2244: Cumulative Trading Graph correctly reports the External Trades
    Given we have a scenario named jira/d3asim_2244
    And gsy-e is installed
    When we run the simulation with setup file jira.d3asim_2244 and parameters [24, 15, 15]
    Then cumulative grid trades correctly reports the external trade

  # TODO: re-enable in context of bug/D3ASIM-3534
  @disabled
  Scenario Outline: D3ASIM-2948: min/max/avg trade rate is correctly reflected irrespective of market type
     Given we have a scenario named jira/d3asim_2948
     And gsy-e is installed
     And gsy-e uses an <market_type> market
     And export is_needed
     When we run the simulation with setup file jira.d3asim_2948 and parameters [24, 60, 60]
     Then we test the min/max/avg trade and devices bill
  Examples: MarketSettings
     |      market_type             |
     |      one-sided               |
     |      two-sided-pay-as-bid    |
     |      two-sided-pay-as-clear  |
