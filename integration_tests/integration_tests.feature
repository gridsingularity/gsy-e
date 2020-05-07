Feature: Run integration tests

  Scenario: Run integration tests on console
     Given we have a scenario named default_2a
     And d3a is installed
     When we run the d3a simulation on console with default_2a for 2 hrs
     Then we test the export functionality of default_2a

  Scenario: Run integration tests on console to test config parameters
     Given we have a scenario named config_parameter_test
     And d3a is installed
     When we run the simulation with setup file config_parameter_test and parameters [24, 60, 60, 1]
     Then we test the config parameters

  Scenario: Test offers, bids and balancing offers are exported
     Given we have a scenario named two_sided_market/with_balancing_market
     And d3a is installed
     When we run the d3a simulation on console with two_sided_market.with_balancing_market for 2 hrs
     Then there are files with offers (with balancing offers) and bids for every area

  Scenario Outline: Run general integration tests for simulation
     Given we have a scenario named <scenario>
     And d3a is installed
     When we run the simulation with setup file <scenario> and parameters [<duration>, <slot_length>, <tick_length>, 1]
     Then we test the output of the simulation of <scenario> [<duration>, <slot_length>, <tick_length>]
  Examples: Settings
     | scenario               | duration | slot_length | tick_length |
     |         default_2      |    24    |      60     |      60     |
     |        default_2b      |    24    |      60     |      60     |
     |        default_3       |    24    |      60     |      60     |
     |        default_3a      |    24    |      60     |      60     |
     |        default_3b      |    24    |      60     |      60     |
     |    default_3_pv_only   |    24    |      60     |      60     |
     |        default_4       |    24    |      60     |      60     |
     |        default_5       |    24    |      60     |      60     |
     |        default_csv     |    24    |      60     |      60     |

  Scenario Outline: Test Balanced Energy Bills
    Given we have a scenario named <scenario>
    And d3a is installed
    When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 1]
    Then the traded energy report the correct accumulated traded energy
    And the energy bills report the correct accumulated traded energy price
    And the energy bills report the correct external traded energy and price

  Examples: Settings
      |                scenario                |
      |         grid_fees.default_2a           |
      |           jira.d3asim_2303             |
      |              default_2a                |
      |      two_sided_market.default_2a       |
      |    two_sided_pay_as_clear.default_2a   |

  Scenario Outline: Test Cumulative Bills
    Given we have a scenario named <scenario>
    And d3a is installed
    When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 1]
    Then the cumulative energy bills for each area are the sum of its children
  Examples: Settings
      |                scenario                |
      |               default_2a               |
      |      two_sided_market.default_2a       |
      |    two_sided_pay_as_clear.default_2a   |
      |          grid_fees.default_2a          |

  Scenario Outline: Simulation subscribes on the appropriate channels
     Given d3a is installed
     When a simulation is created for scenario <scenario>
     And the method <method> is registered
     And the configured simulation is running
     And a message is sent on <channel>
     Then <method> is called
  Examples: Incoming events
     | scenario   | channel    | method       |
     | default_2a | 1234/stop  | stop         |
     | default_2a | 1234/pause | toggle_pause |
#     | default_2a | 1234/reset | reset        | To be enabled once reset is functional

  Scenario: Simulation publishes intermediate and final results
     Given d3a is installed
     When a simulation is created for scenario default_2a
     And the simulation is able to transmit intermediate results
     And the simulation is able to transmit final results
     And the simulation is able to transmit zipped results
     And the configured simulation is running
     Then intermediate results are transmitted on every slot
     And final results are transmitted once

  Scenario: Run integration tests with settings file
     Given we have a scenario named default_2a
     And d3a is installed
     When we run simulation on console with default settings file
     Then we test the export functionality of default_2a

  Scenario: Simulation returns same results for different future market counts
    Given we have a scenario named default_2a
    And d3a is installed
    When we run the simulation with setup file default_2a with two different market_counts
    Then the results are the same for each simulation run

  Scenario: Test aggregated results are exported
     Given we have a scenario named default_2a
     And d3a is installed
     When we run the d3a simulation on console with default_2a for 2 hrs
     Then aggregated result files are exported

  Scenario Outline: Unmatched loads are the same with and without keeping the past markets
     Given we have a scenario named <scenario>
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 1]
     And the reported unmatched loads are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file <scenario> and parameters [24, 60, 60, 1]
     Then the unmatched loads are identical no matter if the past markets are kept

  Examples: Settings
     | scenario     |
     |  default_2a  |
     |  default_3a  |
     |  default_3b  |

  Scenario: Cumulative Grid Trades are the same with and without keeping the past markets
     Given we have a scenario named balancing_market.default_2a
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file balancing_market.default_2a and parameters [24, 60, 60, 1]
     And the reported cumulative grid trades are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file balancing_market.default_2a and parameters [24, 60, 60, 1]
     Then the cumulative grid trades are identical no matter if the past markets are kept

  Scenario: Energy trade profile is the same with and without keeping the past markets
     Given we have a scenario named default_2a
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     And the reported energy trade profile are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     Then the energy trade profiles are identical no matter if the past markets are kept

  Scenario: Energy bills are the same with and without keeping the past markets
     Given we have a scenario named default_2a
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     And the reported energy bills are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     Then the energy bills are identical no matter if the past markets are kept

  Scenario: Cumulative bills are the same with and without keeping the past markets
     Given we have a scenario named default_2a
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     And the reported cumulative bills are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
     Then the cumulative bills are identical no matter if the past markets are kept

  Scenario Outline: Price energy day results are the same with and without keeping the past markets
     Given we have a scenario named <scenario>
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file <scenario> and parameters [24, 60, <tick_length>, 1]
     And the reported price energy day results are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file <scenario> and parameters [24, 60, <tick_length>, 1]
     Then the price energy day results are identical no matter if the past markets are kept

  Examples: Settings
     | scenario     | tick_length |
     |  default_2a  |    60       |
     |  default_3a  |    15       |
     |  default_3b  |    60       |

  Scenario: Uploaded one-day-profile gets duplicated when running the simulations for multiple days
    Given we have a scenario named strategy_tests.user_profile_load_csv
    And d3a is installed
    When we run the simulation with setup file strategy_tests.user_profile_load_csv and parameters [48, 60, 60, 1]
    Then the load profile should be identical on each day