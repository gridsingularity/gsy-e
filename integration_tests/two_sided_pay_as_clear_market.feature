Feature: Two sided pay_as_clear market tests

  Scenario: All Offers & Bids are traded based on Market Clearing Rate
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.default_2a and parameters [24, 60, 60]
     Then all trades are equal to market_clearing_rate
     And buyers and sellers are not same

  Scenario: Cumulative Traded Offers equal to cumulative Traded Bids
     Given we have a scenario named two_sided_pay_as_clear/test_clearing_energy
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.test_clearing_energy and parameters [24, 60, 60]
     Then all trades are equal to market_clearing_rate
     And buyers and sellers are not same
     And cumulative traded offer energy equal to cumulative bid energy

  Scenario: All Offers & Bids are traded with finite energy
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.default_2a and parameters [24, 60, 60]
     Then all traded energy have finite value

  # TODO: re-enable in context of bug/D3ASIM-3534
  @disabled
  Scenario: Test offers, bids and market-clearing-rate are exported
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And gsy-e is installed
     When we run the gsy-e simulation on console with two_sided_pay_as_clear.default_2a for 2 hrs
     Then there are files with offers, bids & market_clearing_rate for every area

  @slow
  Scenario: Supply Demand Curve
     Given we have a scenario named two_sided_pay_as_clear/test_clearing_energy
     And gsy-e is installed
     And gsy-e uses an two-sided-pay-as-clear market
     When we run the gsy-e simulation on console with two_sided_pay_as_clear.test_clearing_energy for 24 hrs
     Then the export functionality of supply/demand curve is tested

  Scenario: One Offer and One Bid are matched at the Bid Rate
     Given we have a scenario named two_sided_pay_as_clear/one_offer_one_bid
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.one_offer_one_bid and parameters [24, 60, 60]
     Then one-on-one matching of offer & bid in PAC happens at bid rate

  Scenario: One Offer and multiple Bids are matched at the last clearing bid rate
     Given we have a scenario named two_sided_pay_as_clear/one_offer_multiple_bids
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.one_offer_multiple_bids and parameters [24, 60, 60]
     Then clearing rate is the bid rate of last matched bid

  Scenario: Multiple Offer and One Bid is matched at the bid rate
     Given we have a scenario named two_sided_pay_as_clear/multiple_offers_one_bid
     And gsy-e is installed
     When we run the simulation with setup file two_sided_pay_as_clear.multiple_offers_one_bid and parameters [24, 60, 60]
     Then clearing rate is equal to the bid_rate
