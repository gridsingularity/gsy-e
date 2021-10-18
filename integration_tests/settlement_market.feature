Feature: Settlement Market Tests

  Scenario: No Settlement market created when its disabled
    Given we have a scenario named default_2a
    And d3a is installed
    When we run the simulation with setup file default_2a and parameters [24, 60, 60]
    Then no settlement market is created

  Scenario: Trades are performed correctly on settlement markets
    Given we have a scenario named settlement_market/simple
    And d3a is installed
    When we run the simulation with setup file settlement_market.simple and parameters [24, 60, 60]
    Then settlement markets are created
    And settlement market trades have been executed


  Scenario: D3ASIM-3653: Trade events are correctly triggered in the settlement load
    Given we have a scenario named settlement_market/simple_load_cell_tower
    And d3a is installed
    When we run the simulation with setup file settlement_market.simple_load_cell_tower and parameters [6, 15, 15, 1]
    Then maximal one trade per market in the settlement market has been executed on grid level
