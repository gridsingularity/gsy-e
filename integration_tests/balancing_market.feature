Feature: Balancing Market Tests

  Scenario: DeviceRegistry works as expected
    Given we have a scenario named balancing_market/test_device_registry
    And d3a is installed
    When we run the d3a simulation with balancing_market.test_device_registry [1, 30, 15]
    Then the device registry is not empty in market class