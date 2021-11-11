Feature: Fees along path

    Scenario:
        Given we have a scenario named grid_fees/test_grid_fees
        And gsy-e is installed
        When we run the simulation with setup file grid_fees.test_grid_fees and parameters [24, 60, 60]
        Then the load initial buying rate adds grid fees
        And the PV initial selling rate subtracts grid fees
