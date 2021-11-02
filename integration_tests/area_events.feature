Feature: Area Events Tests

  Scenario: Area does not perform trades after disable event
    Given we have a scenario named area_events/isolated_disable_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.isolated_disable_event and parameters [24, 60, 60]
    Then trades occur before 12:00
    And no trades occur after 12:00

  Scenario: Area restores operation after disable-enable event
    Given we have a scenario named area_events/isolated_enable_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.isolated_enable_event and parameters [24, 60, 60]
    Then trades occur before 12:00
    And no trades occur between 12:00 and 16:00
    And trades occur after 16:00

  Scenario: Area interrupts operation during disable-interval event
    Given we have a scenario named area_events/disable_interval_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.disable_interval_event and parameters [24, 60, 60]
    Then trades occur before 6:00
    And no trades occur between 6:00 and 16:00
    And trades occur after 16:00

  @disabled
  Scenario: Area isolates from main grid during disconnect-interval event
    Given we have a scenario named area_events/disconnect_interval_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.disconnect_interval_event and parameters [24, 60, 15]
    Then load and battery use energy from grid before 6:00
    And battery does not charge between 6:00 and 16:00
    And load and battery use energy from grid after 16:00

  @disabled
  Scenario: Area isolates from the main grid after disconnect event
    Given we have a scenario named area_events/isolated_disconnect_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.isolated_disconnect_event and parameters [24, 60, 60]
    Then load and battery use energy from grid before 12:00
    And battery does not charge between 12:00 and 24:00

  @disabled
  Scenario: Area reconnects to the main grid after disconnect-connect event
    Given we have a scenario named area_events/isolated_connect_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.isolated_connect_event and parameters [24, 60, 60]
    Then load and battery use energy from grid before 6:00
    And battery does not charge between 6:00 and 16:00
    And load and battery use energy from grid after 16:00

  Scenario: Load changes consumption and hours of/per day after strategy event
    Given we have a scenario named area_events/load_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.load_event and parameters [24, 60, 60]
    Then load consumes 0.2 kWh between 00:00 and 12:00
    And load consumes 0.4 kWh between 12:00 and 15:00
    And no trades occur after 15:00

  Scenario: PredefinedLoad changes consumption and hours of/per day after strategy event
    Given we have a scenario named area_events/predefined_load_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.predefined_load_event and parameters [24, 60, 60]
    Then load consumes 0.2 kWh between 00:00 and 12:00
    And load consumes 0.4 kWh between 12:00 and 15:00
    And no trades occur after 15:00

  Scenario: PV changes production and panel count after strategy event
    Given we have a scenario named area_events/pv_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.pv_event and parameters [24, 60, 60]
    Then Grid Load consumes less than 0.15891 kWh between 8:00 and 12:00
    And Grid Load consumes less than 1.5891 kWh between 12:00 and 16:00

  Scenario: PredefinedPV changes production when it gets cloudy
    Given we have a scenario named area_events/predefined_pv_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.predefined_pv_event and parameters [24, 60, 60]
    Then load consumes energy following the sunny profile between 6:00 and 14:00
    And load consumes energy following the cloudy profile between 14:00 and 19:00
    And no trades occur after 20:00

  Scenario: UserProfilePV changes production when user changes profile
    Given we have a scenario named area_events/userprofile_pv_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.userprofile_pv_event and parameters [24, 60, 60]
    Then Grid Load consumes 0.2 kWh between 00:00 and 12:00
    And Grid Load consumes 0.4 kWh between 12:00 and 14:00
    And Grid Load consumes 0.6 kWh between 14:00 and 18:00
    And no trades occur after 20:00

  Scenario: Storage changes initial_selling_rate after strategy event
    Given we have a scenario named area_events/storage_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.storage_event and parameters [24, 60, 30]
    Then load consumes 0.01 kWh with 31 ct/kWh between 0:00 and 12:00
    And load consumes 0.01 kWh with 33 ct/kWh between 13:00 and 15:00
    And load consumes 0.01 kWh with 35 ct/kWh between 16:00 and 24:00

  Scenario: Cloud coverage event changes config value
    Given we have a scenario named area_events/cloud_coverage_event
    And gsy_e is installed
    When we run the simulation with setup file area_events.cloud_coverage_event and parameters [24, 60, 60]
    Then both PVs follow they sunny profile until 12:00
    And House 1 PV follows the partially cloudy profile after 12:00
    And House 2 PV follows the cloudy profile after 12:00
