Feature: Load Tests

  Scenario: DefinedLoadStrategy follows the profile provided by the user as dict
    Given we have a scenario named strategy_tests/user_profile_load_dict
    And d3a is installed
    When we run the d3a simulation with strategy_tests.user_profile_load_dict [24, 15, 15]
    Then the DefinedLoadStrategy follows the Load profile provided as dict
    And load only accepted offers lower than max_energy_rate

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
    And load only accepted offers lower than max_energy_rate

  Scenario: LoadHoursStrategy buys energy in the rate range provided by the user as dict profile
    Given we have a scenario named strategy_tests/user_rate_profile_load_dict
    And d3a is installed
    When we run the simulation with setup file strategy_tests.user_rate_profile_load_dict and parameters [24, 15, 15, 1]
    Then LoadHoursStrategy does not buy energy with rates that are higher than the provided profile

  Scenario: Custom Load strategy works as expected
     Given we have a scenario named jira/d3asim_638_custom_load
     And d3a is installed
     When we run the simulation with setup file jira.d3asim_638_custom_load and parameters [24, 15, 15, 0]
     Then the load has no unmatched loads
     And the PV always provides constant power according to load demand
     And the energy rate for all the trades is the mean of max and min load/pv rate