Feature: Area Events Tests

  Scenario: Area does not perform trades after disable event
    Given we have a scenario named area_events/isolated_disable_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_disable_event [1, 30, 15]
    Then trades occur before 12:00
    And no trades occur after 12:00

  Scenario: Area restores operation after disable-enable event
    Given we have a scenario named area_events/isolated_enable_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_enable_event [1, 30, 15]
    Then trades occur before 12:00
    And no trades occur between 12:00 and 16:00
    And trades occur after 16:00

  Scenario: Area interrupts operation during disable-interval event
    Given we have a scenario named area_events/disable_interval_event
    And d3a is installed
    When we run the d3a simulation with area_events.disable_interval_event [1, 30, 15]
    Then trades occur before 6:00
    And no trades occur between 6:00 and 16:00
    And trades occur after 16:00

  Scenario: Area isolates from main grid during disconnect-interval event
    Given we have a scenario named area_events/disconnect_interval_event
    And d3a is installed
    When we run the d3a simulation with area_events.disconnect_interval_event [1, 30, 15]
    Then load and battery use energy from grid before 6:00
    And battery does not charge between 6:00 and 16:00
    And load and battery use energy from grid after 16:00

  Scenario: Area isolates from the main grid after disconnect event
    Given we have a scenario named area_events/isolated_disconnect_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_disconnect_event [1, 30, 15]
    Then load and battery use energy from grid before 12:00
    And battery does not charge between 12:00 and 24:00

  Scenario: Area reconnects to the main grid after disconnect-connect event
    Given we have a scenario named area_events/isolated_connect_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_connect_event [1, 30, 15]
    Then load and battery use energy from grid before 6:00
    And battery does not charge between 6:00 and 16:00
    And load and battery use energy from grid after 16:00

  Scenario: Load changes consumption and hours of/per day after strategy event
    Given we have a scenario named area_events/load_event
    And d3a is installed
    When we run the d3a simulation with area_events.load_event [1, 30, 15]
    Then load consumes 0.1 kWh before 12:00
    And load consumes 0.2 kWh between 12:00 and 22:00
    And no trades occur after 22:00

  Scenario: PV changes production and panel count after strategy event
    Given we have a scenario named area_events/pv_event
    And d3a is installed
    When we run the d3a simulation with area_events.pv_event [1, 30, 15]
    Then load consumes less than 0.0756 kWh between 8:00 and 12:00
    And load consumes less than 1.59 kWh between 12:00 and 16:00

  Scenario: Storage changes risk after strategy event
    Given we have a scenario named area_events/storage_event
    And d3a is installed
    When we run the d3a simulation with area_events.storage_event [1, 30, 15]
    Then load consumes 0.005 kWh with 25 ct/kWh between 0:00 and 12:00
    And load does not consume energy between 12:00 and 24:00

  Scenario: Cloud coverage event changes config value
    Given we have a scenario named area_events/cloud_coverage_event
    And d3a is installed
    When we run the d3a simulation with area_events.cloud_coverage_event [1, 30, 15]
    Then both PVs follow they sunny profile until 12:00
    And House 1 PV follows the partially cloudy profile after 12:00
    And House 2 PV follows the cloudy profile after 12:00
