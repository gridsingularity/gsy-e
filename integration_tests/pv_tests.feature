Feature: PV Tests

  Scenario: PV limits the minimum selling rate
     Given we have a scenario named strategy_tests/pv_min_selling_rate
     And d3a is installed
     When we run the d3a simulation with strategy_tests.pv_min_selling_rate [24, 15, 15]
     Then the storages buy energy for no more than the min PV selling rate

  Scenario: PV RISK based price decrease
     Given we have a scenario named strategy_tests/pv_risk_based_price_decrease
     And d3a is installed
     When we run the d3a simulation with strategy_tests.pv_risk_based_price_decrease [24, 15, 15]
     Then the PV risk based strategy decrease its unsold offers price as expected

  Scenario: PV can use the market maker rate as the initial rate for every market slot
     Given we have a scenario named strategy_tests/pv_initial_rate
     And d3a is installed
     When we run the d3a simulation with strategy_tests.pv_initial_rate [24, 15, 15]
     Then the PV sells energy at the market maker rate for every market slot

  Scenario: UserProfile PV follows the profile provided by the user as dict
     Given we have a scenario named strategy_tests/user_profile_pv_dict
     And d3a is installed
     When we run the d3a simulation with strategy_tests.user_profile_pv_dict [24, 15, 15]
     Then the UserProfile PV follows the PV profile as dict

  Scenario: Predefined PV follows the profile provided by the user as csv
     Given we have a scenario named strategy_tests/user_profile_pv_csv
     And d3a is installed
     When we run the d3a simulation with strategy_tests.user_profile_pv_csv [24, 15, 15]
     Then the UserProfile PV follows the PV profile of csv

  Scenario: Predefined PV follows the profile provided by the user
     Given we have a scenario named strategy_tests/predefined_pv
     And d3a is installed
     When we run the d3a simulation with strategy_tests.predefined_pv [24, 15, 15]
     Then the predefined PV follows the PV profile

  Scenario: Predefined PV follows the csv profile provided by the user
     Given a PV profile csv as input to predefined PV
     And the scenario includes a predefined PV
     When the simulation is running
     Then the predefined PV follows the PV profile from the csv