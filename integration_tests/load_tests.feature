Feature: Load Tests

  Scenario: DefinedLoadStrategy follows the profile provided by the user as dict
    Given we have a scenario named strategy_tests/user_profile_load_dict
    And d3a is installed
    When we run the simulation with setup file strategy_tests.user_profile_load_dict and parameters [24, 60, 60, 1]
    Then the DefinedLoadStrategy follows the Load profile provided as dict
    And load only accepted offers lower than final_buying_rate

  Scenario: Predefined load follows the string profile provided by the user
     Given a load profile string as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile

  Scenario: DefinedLoadStrategy trades energy based on csv provided profile
    Given we have a scenario named strategy_tests/user_profile_load_csv
    And d3a is installed
    When we run the simulation with setup file strategy_tests.user_profile_load_csv and parameters [24, 15, 15, 1]
    Then the DefinedLoadStrategy follows the single day Load profile provided as csv
    And load only accepted offers lower than final_buying_rate

  Scenario: DefinedLoadStrategy trades energy based on a multiday csv profile
    Given we have a scenario named strategy_tests/user_profile_load_csv_multiday
    And d3a is installed
    When we run a multi-day d3a simulation with strategy_tests.user_profile_load_csv_multiday [2019-01-01, 48, 15, 15]
    Then the DefinedLoadStrategy follows the multi day Load profile provided as csv
    And load only accepted offers lower than final_buying_rate

  Scenario: LoadHoursStrategy buys energy in the rate range provided by the user as dict profile
    Given we have a scenario named strategy_tests/user_rate_profile_load_dict
    And d3a is installed
     And export is_needed
    When we run the simulation with setup file strategy_tests.user_rate_profile_load_dict and parameters [24, 30, 30, 4]
    Then LoadHoursStrategy does not buy energy with rates that are higher than the provided profile
