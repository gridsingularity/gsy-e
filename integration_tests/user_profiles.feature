Feature: User Profiles Tests

  Scenario: PV follows yearly user profile
    Given uuids are initiated
    And a yearly PV profile exist in the DB
    And a yearly Load profile exist in the DB
    And a configuration containing a PV and Load using profile_uuids exists
    When the simulation is running
    Then the predefined PV follows the profile from DB
    And the predefined Load follows the profile from DB
