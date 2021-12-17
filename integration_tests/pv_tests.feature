Feature: PV Tests

  Scenario: PV limits the minimum selling rate
     Given we have a scenario named strategy_tests/pv_final_selling_rate
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.pv_final_selling_rate and parameters [24, 60, 60]
     Then the storages buy energy for no more than the min PV selling rate

  Scenario: PV CONSTANT based price decrease
     Given we have a scenario named strategy_tests/pv_const_price_decrease
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.pv_const_price_decrease and parameters [24, 60, 60]
     Then the PV strategy decrease its sold/unsold offers price as expected

  Scenario: UserProfile PV follows the profile provided by the user as dict
     Given we have a scenario named strategy_tests/user_profile_pv_dict
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.user_profile_pv_dict and parameters [24, 60, 60]
     Then the UserProfile PV follows the PV profile as dict

  Scenario: Predefined PV follows the profile provided by the user as csv
     Given we have a scenario named strategy_tests/user_profile_pv_csv
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.user_profile_pv_csv and parameters [24, 60, 60]
     Then the UserProfile PV follows the PV profile of csv

  Scenario: Predefined PV follows the profile provided by the user
     Given we have a scenario named strategy_tests/predefined_pv_test
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.predefined_pv_test and parameters [24, 60, 60]
     Then the predefined PV follows the PV profile

  Scenario: Predefined PV follows the csv profile provided by the user
     Given a PV profile csv as input to predefined PV
     And the scenario includes a predefined PV
     When the simulation is running
     Then the predefined PV follows the PV profile from the csv

  Scenario: PV capacity_kW argument changes power of a single PV panel
     Given we have a scenario named strategy_tests/pv_max_panel_output
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.pv_max_panel_output and parameters [24, 60, 60]
     Then the load buys at most the energy equivalent of 200 W

  Scenario: PV global setting capacity_kW changes power of all PV panels
     Given we have a scenario named strategy_tests/pv_max_panel_power_global
     And gsy-e is installed
     When we run the simulation with setup file strategy_tests.pv_max_panel_power_global and parameters [24, 60, 60]
     Then the load buys at most the energy equivalent of 400 W
