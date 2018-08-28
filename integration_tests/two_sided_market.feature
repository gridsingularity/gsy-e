Feature: Two sided market tests

  Scenario: One storage, one load
     Given we have a scenario named two_sided_market/one_load_one_storage
     And d3a is installed
     When we run the d3a simulation with two_sided_market.one_load_one_storage [24, 15, 15]
     Then the storage is never buying energy and is always selling energy
     And the storage final SOC is 0%
     And all the trade rates are between break even sell and market maker rate price

  Scenario: One pv, one load
     Given we have a scenario named two_sided_market/one_pv_one_load
     And d3a is installed
     When we run the d3a simulation with two_sided_market.one_pv_one_load [24, 15, 15]
     Then the load has no unmatched loads
     And the PV always provides constant power according to load demand
     And the energy rate for all the trades is the mean of max and min load/pv rate

  Scenario: One storage, one pv
     Given we have a scenario named two_sided_market/one_pv_one_storage
     And d3a is installed
     When we run the d3a simulation with two_sided_market.one_pv_one_storage [24, 15, 15]
     Then the storage is never selling energy
     And the storage final SOC is 100%
     And the energy rate for all the trades is the mean of max and min pv/storage rate
