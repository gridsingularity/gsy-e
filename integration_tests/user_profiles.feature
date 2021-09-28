Feature: User Profiles Tests

  Scenario: Strategies follow yearly user profile saved in the DB
    Given uuids are initiated
    And a yearly PV profile exist in the DB
    And a yearly Load profile exist in the DB
    And a yearly Smart Meter profile exist in the DB
    And the connection to the profiles DB is disconnected
    And a configuration with assets using profile_uuids exists
    When the simulation is running
    Then the predefined PV follows the profile from DB
    And the predefined Load follows the profile from DB
    And the Smart Meter follows the profile from DB
