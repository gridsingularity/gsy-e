Feature: Balancing Market Tests

  Scenario: No Balancing market created when its disabled
    Given we have a scenario named default_2a
    And gsy_e is installed
    When we run the simulation with setup file default_2a and parameters [24, 60, 60]
    Then no balancing market is created

  Scenario: DeviceRegistry works as expected
    Given we have a scenario named balancing_market/test_device_registry
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.test_device_registry and parameters [24, 60, 60]
    Then the device registry is not empty in market class

  Scenario: one load one PV balancing market
    Given we have a scenario named balancing_market/one_load_one_pv
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.one_load_one_pv and parameters [24, 60, 60]
    Then balancing market of House 1 has 2 balancing trades and 1 spot trades
    And balancing market of House 2 has 1 reserve trades and 1 spot trades
    And grid has 1 balancing trade from house 1 to house 2
    And all trades follow the device registry H1 General Load rate for supply and demand
    And all trades are in accordance to the balancing energy ratio

  Scenario: one storage one PV balancing market
    Given we have a scenario named balancing_market/one_storage_one_pv
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.one_storage_one_pv and parameters [24, 60, 60]
    Then balancing market of House 1 has 4 balancing trades and 1 spot trades
    And balancing market of House 2 has 2 reserve trades and 1 spot trades
    And grid has 2 balancing trades from house 1 to house 2
    And all trades follow the device registry H1 Storage rate for supply and demand
    And all trades are in accordance to the balancing energy ratio

  Scenario: one storage one load balancing market
    Given we have a scenario named balancing_market/one_load_one_storage
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.one_load_one_storage and parameters [24, 60, 60]
    Then there are balancing trades on all markets for every market slot
    And all trades follow one of H2 Storage or H1 Load rates for supply and demand
    And every balancing trade matches a spot market trade according to the balancing energy ratio

  Scenario: default_2a buys balancing energy on all BAs
    Given we have configured all the balancing_market.default_2a devices in the registry
    And we have a scenario named balancing_market/default_2a
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.default_2a and parameters [24, 60, 60]
    Then all trades follow one of H1 Storage1 or H1 General Load rates for supply and demand
    And there are balancing trades on some markets

  Scenario: Balancing market is compatible to the 2 sided market
    Given we have a scenario named balancing_market/two_sided_one_load_one_pv
    And gsy_e is installed
    When we run the simulation with setup file balancing_market.two_sided_one_load_one_pv and parameters [24, 60, 60]
    Then balancing market of House 1 has 2 balancing trades and 1 spot trades
    And balancing market of House 2 has 1 reserve trades and 1 spot trades
    And grid has 1 balancing trade from house 1 to house 2
    And all trades follow the device registry H1 General Load rate for supply and demand
    And all trades are in accordance to the balancing energy ratio
