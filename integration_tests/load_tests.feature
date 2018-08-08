Feature: Load Tests

  Scenario: DefinedLoadStrategy follows the profile provided by the user as dict
    Given we have a scenario named strategy_tests/user_profile_load_dict
    And d3a is installed
    When we run the d3a simulation with strategy_tests.user_profile_load_dict [24, 15, 15]
    Then the DefinedLoadStrategy follows the Load profile provided as dict
    And load only accepted offers lower than acceptable_energy_rate

  Scenario: Predefined load follows the string profile provided by the user
     Given a load profile string as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile

  Scenario: DefinedLoadStrategy trades energy based on csv provided profile
    Given we have a scenario named strategy_tests/user_profile_load_csv
    And d3a is installed
    When we run the d3a simulation with strategy_tests.user_profile_load_csv [24, 15, 15]
    Then the DefinedLoadStrategy follows the Load profile provided as csv
    And load only accepted offers lower than acceptable_energy_rate
