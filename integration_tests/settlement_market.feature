Feature: Settlement Market Tests

  Scenario: No Settlement market created when its disabled
    Given we have a scenario named default_2a
    And d3a is installed
    When we run the simulation with setup file default_2a and parameters [24, 60, 60, 1]
    Then no settlement market is created

  Scenario: Trades are performed correctly on settlement markets
    Given we have a scenario named settlement_market/simple
    And d3a is installed
    When we run the simulation with setup file settlement_market.simple and parameters [24, 60, 60, 1]
    Then settlement markets are created
    And settlement market trades have been executed
