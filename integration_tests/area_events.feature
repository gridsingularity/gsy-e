Feature: Area Events Tests

  Scenario: Area does not perform trades after disconnect event
    Given we have a scenario named area_events/isolated_disconnect_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_disconnect_event [1, 30, 15]
    Then trades occur before 12:00
    And no trades occur after 12:00

  Scenario: Area restores operation after disconnect-connect event
    Given we have a scenario named area_events/isolated_connect_event
    And d3a is installed
    When we run the d3a simulation with area_events.isolated_disconnect_event [1, 30, 15]
    Then trades occur before 12:00
    And no trades occur between 12:00 and 16:00
    And trades occur after 16:00

  Scenario: Area interrupts operation during disconnect-interval event
    Given we have a scenario named area_events/disconnect_interval_event
    And d3a is installed
    When we run the d3a simulation with area_events.disconnect_interval_event [1, 30, 15]
    Then trades occur before 6:00
    And no trades occur between 6:00 and 16:00
    And trades occur after 16:00
