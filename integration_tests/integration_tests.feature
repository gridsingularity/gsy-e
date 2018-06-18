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

