Feature: Future market tests
  Scenario: Trades in the future
    Given we have a scenario named two_sided_market.future_market
    And gsy-e is installed
    And export is_needed
    When we run the simulation with setup file two_sided_market.future_market and parameters [24, 60, 6]
    Then hi