Feature: GridFee integration tests
  Scenario Outline: Grid fees are calculated based on the original offer rate
     Given we have a scenario named grid_fees/non_compounded_grid_fees
     And d3a is installed
     And d3a uses an one-sided market
     And the minimum offer age is <min_offer_age>
     When we run the simulation with setup file grid_fees.non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 12.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 11.5 cents/kWh and at grid_fee_rate with 0.5 cents/kWh
     Then trades on the Grid market clear with 10.5 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the Neighborhood 2 market clear with 10.0 cents/kWh and at grid_fee_rate with 0.5 cents/kWh
     Then trades on the House 2 market clear with 10.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Grid fees are calculated based on the original bid rate
     Given we have a scenario named grid_fees/non_compounded_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-bid market
     And the minimum offer age is <min_offer_age>
     When we run the simulation with setup file grid_fees.non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 30.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 30 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the Grid market clear with 28.75 cents/kWh and at grid_fee_rate with 2.5 cents/kWh
     Then trades on the Neighborhood 2 market clear with 26.25 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the House 2 market clear with 25.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Grid fees are calculated based on the clearing rate for pay as clear while dispatching top to bottom
     Given we have a scenario named grid_fees/non_compounded_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-clear market
     And the minimum offer age is <min_offer_age>
     And d3a dispatches events from top to bottom
     When we run the simulation with setup file grid_fees.non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 30 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 30 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the Grid market clear with 28.75 cents/kWh and at grid_fee_rate with 2.5 cents/kWh
     Then trades on the Neighborhood 2 market clear with 26.25 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the House 2 market clear with 25 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Grid fees are calculated based on the clearing rate for pay as clear while dispatching bottom to top
     Given we have a scenario named grid_fees/non_compounded_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-clear market
     And the minimum offer age is <min_offer_age>
     And d3a dispatches events from bottom to top
     When we run the simulation with setup file grid_fees.non_compounded_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 30 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 30 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the Grid market clear with 28.75 cents/kWh and at grid_fee_rate with 2.5 cents/kWh
     Then trades on the Neighborhood 2 market clear with 26.25 cents/kWh and at grid_fee_rate with 1.25 cents/kWh
     Then trades on the House 2 market clear with 25 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Constant grid fees are calculated correctly
     Given we have a scenario named grid_fees/constant_grid_fees
     And d3a is installed
     And d3a uses an one-sided market
     And the minimum offer age is <min_offer_age>
     When we run the simulation with setup file grid_fees.constant_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 14.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 13.0 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the Grid market clear with 11.0 cents/kWh and at grid_fee_rate with 2.0 cents/kWh
     Then trades on the Neighborhood 2 market clear with 10.0 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the House 2 market clear with 10.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Constant grid fees are calculated correctly on pay as bid market
     Given we have a scenario named grid_fees/constant_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-bid market
     And the minimum offer age is <min_offer_age>
     When we run the simulation with setup file grid_fees.constant_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 30.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 30.0 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the Grid market clear with 29 cents/kWh and at grid_fee_rate with 2.0 cents/kWh
     Then trades on the Neighborhood 2 market clear with 27 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the House 2 market clear with 26.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |

  Scenario Outline: Constant grid fees are calculated correctly on pay as clear market
     Given we have a scenario named grid_fees/constant_grid_fees
     And d3a is installed
     And d3a uses an two-sided pay-as-clear market
     And the minimum offer age is <min_offer_age>
     And d3a dispatches events from top to bottom
     When we run the simulation with setup file grid_fees.constant_grid_fees and parameters [24, 60, 60, 0, 1]
     Then trades on the House 1 market clear with 30.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
     Then trades on the Neighborhood 1 market clear with 30.0 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the Grid market clear with 29 cents/kWh and at grid_fee_rate with 2.0 cents/kWh
     Then trades on the Neighborhood 2 market clear with 27 cents/kWh and at grid_fee_rate with 1.0 cents/kWh
     Then trades on the House 2 market clear with 26.0 cents/kWh and at grid_fee_rate with 0.0 cents/kWh
  Examples: Minimum Offer Age
     | min_offer_age |
     |       0       |
     |       5       |
     |       9       |
