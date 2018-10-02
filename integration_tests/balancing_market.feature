Feature: Balancing Market Tests

  Scenario: DeviceRegistry works as expected
    Given we have a scenario named balancing_market/test_device_registry
    And d3a is installed
    When we run the d3a simulation with balancing_market.test_device_registry [1, 30, 15]
    Then the device registry is not empty in market class

  # Scenario: default_2a buys balancing energy on all BAs
  #   Given we have configured all the default_2a devices in the registry
  #   And we have a scenario named default_2a
  #   And d3a is installed
  #   When we run the d3a simulation with default_2a [24, 15, 15]
  #   Then all BAs buy balancing energy according to their balancing ratio

  Scenario: one load one PV balancing market
    Given we have a scenario named balancing_market/one_load_one_pv
    And d3a is installed
    When we run the d3a simulation with balancing_market.one_load_one_pv [24, 15, 15]
    Then balancing market of House 1 has 2 balancing trades and 1 spot trades
    And balancing market of House 2 has 1 balancing trades and 1 spot trades
    And grid has 1 balancing trade from house 1 to house 2
    And all trades follow the device registry H1 General Load rate for demand
    And all trades are in accordance to the balancing energy ratio

