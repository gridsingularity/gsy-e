Feature: Run integration tests

  Scenario Outline: Run integration tests on console
     Given we have a scenario named <scenario>
     And d3a is installed
     When we run the d3a simulation on console with <scenario>
     Then we test the export functionality of <scenario>
  Examples: Scenarios
     | scenario |
     | integration_test_setup |

  Scenario Outline: Run integration tests
     Given we have a scenario named <scenario>
     And d3a is installed
     When we run the d3a simulation with <scenario> [<duration>, <slot_length>, <tick_length>]
     Then we test the output of the simulation of <scenario> [<duration>, <slot_length>, <tick_length>]
  Examples: Settings
     | scenario               | duration | slot_length | tick_length |
     | integration_test_setup |    2     |      20     |      1      |
     | integration_test_setup |    4     |      10     |      5      |
     |         default        |    24    |      60     |      60     |
     |         default_2      |    24    |      60     |      60     |
     |        default_2a      |    24    |      60     |      60     |
     |        default_2b      |    24    |      60     |      60     |
     |        default_3       |    24    |      60     |      60     |
     |        default_3a      |    24    |      60     |      60     |
     |        default_3b      |    24    |      60     |      60     |
     |    default_3_pv_only   |    24    |      60     |      60     |
     |        default_4       |    24    |      60     |      60     |
     |        default_5       |    24    |      60     |      60     |
     |    default_appliance   |    24    |      60     |      60     |
     |        default_csv     |    24    |      60     |      60     |

  Scenario: Predefined PV follows the csv profile provided by the user
     Given a PV profile csv as input to predefined PV
     And the scenario includes a predefined PV
     When the simulation is running
     Then the predefined PV follows the PV profile from the csv

  Scenario: Predefined load follows the csv profile provided by the user
     Given a load profile csv as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile from the csv

  Scenario: Predefined PV follows the profile provided by the user
     Given a PV profile hourly dict as input to predefined load
     And the scenario includes a predefined PV
     When the simulation is running
     Then the predefined PV follows the PV profile

  Scenario: Predefined load follows the profile provided by the user
     Given a load profile hourly dict as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile
