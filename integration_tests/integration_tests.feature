Feature: Run integration tests

  Scenario: Run integration tests on console
     Given we have a scenario named default_2a
     And d3a is installed
     When we run the d3a simulation on console with default_2a
     Then we test the export functionality of default_2a

  Scenario: Run integration tests on console to test config parameters
     Given we have a scenario named config_parameter_test
     And d3a is installed
     When we run the simulation with setup file config_parameter_test and parameters [24, 60, 60, 0, 1]
     Then we test the config parameters

  Scenario: Test offers, bids and balancing offers are exported
     Given we have a scenario named two_sided_market/with_balancing_market
     And d3a is installed
     When we run the d3a simulation on console with two_sided_market.with_balancing_market
     Then there are files with offers (with balancing offers) and bids for every area

  Scenario Outline: Run general integration tests for simulation
     Given we have a scenario named <scenario>
     And d3a is installed
     When we run the d3a simulation with <scenario> [<duration>, <slot_length>, <tick_length>]
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

  # TODO: Once iaa_fee is included in billing, this test to be run non-zero iaa_fee
  Scenario Outline: Test Balanced Energy Bills
    Given we have a scenario named <scenario>
    And d3a is installed
    When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 0, 1]
    Then the traded energy report the correct accumulated traded energy
    And the energy bills report the correct accumulated traded energy price
    And the traded energy profile is correctly generated

  Examples: Settings
      |                scenario                |
      |               default_2a               |
      |      two_sided_market.default_2a       |
      |    two_sided_pay_as_clear.default_2a   |


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
     | default_2a | 1234/reset | reset        |

  Scenario: Simulation publishes intermediate and final results
     Given d3a is installed
     When a simulation is created for scenario default_2a
     And the simulation is able to transmit intermediate results
     And the simulation is able to transmit final results
     And the configured simulation is running
     Then intermediate results are transmitted on every slot
     And final results are transmitted once

  Scenario: Run integration tests with settings file
     Given we have a scenario named default_2a
     And d3a is installed
     When we run simulation on console with default settings file
     Then we test the export functionality of default_2a

  Scenario: Simulation returns same results for different market counts
    Given we have a scenario named default_2a
    And d3a is installed
    When we run the simulation with setup file default_2a with two different market_counts
    Then the results are the same for each simulation run

  Scenario: Test aggregated results are exported
     Given we have a scenario named default_2a
     And d3a is installed
     When we run the d3a simulation on console with default_2a
     Then aggregated result files are exported

  Scenario: Grid fees are calculated based on the original offer rate
     Given we have a scenario named non_compounded_grid_fees
     And d3a is installed
     And d3a uses an one-sided market
     When we run the simulation with setup file non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 12.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 11.5 cents/kWh
     Then trades on the Grid market clear with 10.5 cents/kWh
     Then trades on the Neighborhood 2 market clear with 10.0 cents/kWh
     Then trades on the House 2 market clear with 10.0 cents/kWh

  Scenario: Grid fees are calculated based on the original bid rate
     Given we have a scenario named non_compounded_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-bid market
     When we run the simulation with setup file non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 20.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 19.0 cents/kWh
     Then trades on the Grid market clear with 17.0 cents/kWh
     Then trades on the Neighborhood 2 market clear with 16.0 cents/kWh
     Then trades on the House 2 market clear with 16.0 cents/kWh

  Scenario: Grid fees are calculated based on the clearing rate for pay as clear
     Given we have a scenario named non_compounded_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-clear market
     When we run the simulation with setup file non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 20.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 19.0 cents/kWh
     Then trades on the Grid market clear with 17.0 cents/kWh
     Then trades on the Neighborhood 2 market clear using a rate of either 16.0 or 16.15 cents/kWh
     Then trades on the House 2 market clear using a rate of either 16.0 or 16.15 cents/kWh

  Scenario Outline: Unmatched loads are the same with and without keeping the past markets
     Given we have a scenario named <scenario>
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file <scenario> and parameters [24, 60, 60, 0, 1]
     And the reported unmatched loads are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file <scenario> and parameters [24, 60, 60, 0, 1]
     Then the unmatched loads are identical no matter if the past markets are kept

  Examples: Settings
     | scenario     |
     |  default_2a  |
     |  default_3a  |
     |  default_3b  |

  Scenario: Energy trade profile is the same with and without keeping the past markets
     Given we have a scenario named default_2a
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file default_2a and parameters [24, 60, 60, 0, 1]
     And the reported energy trade profile are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file default_2a and parameters [24, 60, 60, 0, 1]
     Then the energy trade profiles are identical no matter if the past markets are kept

  Scenario Outline: Price energy day results are the same with and without keeping the past markets
     Given we have a scenario named <scenario>
     And d3a is installed
     And the past markets are kept in memory
     When we run the simulation with setup file <scenario> and parameters [24, 60, <tick_length>, 0, 1]
     And the reported price energy day results are saved
     And the past markets are not kept in memory
     And we run the simulation with setup file <scenario> and parameters [24, 60, <tick_length>, 0, 1]
     Then the price energy day results are identical no matter if the past markets are kept

  Examples: Settings
     | scenario     | tick_length |
     |  default_2a  |    60       |
     |  default_3a  |    15       |
     |  default_3b  |    60       |
 