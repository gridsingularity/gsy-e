Feature: Two sided market tests

  Scenario: One storage, one load
     Given we have a scenario named two_sided_market/one_load_one_storage
     And d3a is installed
     When we run the simulation with setup file two_sided_market.one_load_one_storage and parameters [24, 15, 15, 0, 1]
     Then the storage is never buying energy and is always selling energy
     And the storage final SOC is 0%
     And all the trade rates are between break even sell and market maker rate price

  Scenario: One pv, one load
     Given we have a scenario named two_sided_market/one_pv_one_load
     And d3a is installed
     When we run the simulation with setup file two_sided_market.one_pv_one_load and parameters [24, 15, 15, 0, 4]
     Then the load has no unmatched loads
     And the PV always provides constant power according to load demand

  Scenario: One storage, one pv
     Given we have a scenario named two_sided_market/one_pv_one_storage
     And d3a is installed
     When we run the simulation with setup file two_sided_market.one_pv_one_storage and parameters [24, 15, 15, 0, 4]
     Then the storage is never selling energy
     And the storage final SOC is 100%
     And the energy rate for all the trades is the mean of max and min pv/storage rate

  Scenario: 5 pv, one load
     Given we have a scenario named two_sided_market/one_load_5_pv_partial
     And d3a is installed
     When we run the simulation with setup file two_sided_market.one_load_5_pv_partial and parameters [24, 15, 15, 0, 4]
     Then the load has unmatched loads
     And the load bid is partially fulfilled by the PV offers

  Scenario: 5 pv, one storage
     Given we have a scenario named two_sided_market/one_storage_5_pv_partial
     And d3a is installed
     When we run the simulation with setup file two_sided_market.one_storage_5_pv_partial and parameters [24, 15, 15, 0, 4]
     Then the storage bid is partially fulfilled by the PV offers

  Scenario: LoadHoursStrategy buys energy in the min rate range provided by the user as dict profile
    Given we have a scenario named two_sided_market/user_min_rate_profile_load_dict
    And d3a is installed
    When we run the simulation with setup file two_sided_market.user_min_rate_profile_load_dict and parameters [24, 15, 15, 1, 4]
    Then LoadHoursStrategy buys energy with rates equal to the min rate profile
