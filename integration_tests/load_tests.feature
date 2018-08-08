Feature: Load Tests

  Scenario: Predefined load follows the csv profile provided by the user
     Given a load profile csv as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile from the csv

  Scenario: Predefined load follows the profile provided by the user
     Given a load profile hourly dict as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile

  Scenario: Predefined load follows the string profile provided by the user
     Given a load profile string as input to predefined load
     And the scenario includes a predefined load that will not be unmatched
     When the simulation is running
     Then the predefined load follows the load profile
