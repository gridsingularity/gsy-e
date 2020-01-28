Feature: Two sided pay_as_clear market tests

  Scenario: All Offers & Bids are traded based on Market Clearing Rate
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And d3a is installed
     When we run the simulation with setup file two_sided_pay_as_clear.default_2a and parameters [24, 60, 60, 0, 1]
     Then all trades are equal to market_clearing_rate
     And buyers and sellers are not same

  Scenario: Cumulative Traded Offers equal to cumulative Traded Bids
     Given we have a scenario named two_sided_pay_as_clear/test_clearing_energy
     And d3a is installed
     When we run the simulation with setup file two_sided_pay_as_clear.test_clearing_energy and parameters [24, 60, 60, 0, 1]
     Then all trades are equal to market_clearing_rate
     And buyers and sellers are not same
     And cumulative traded offer energy equal to cumulative bid energy

  Scenario: All Offers & Bids are traded with finite energy
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And d3a is installed
     When we run the simulation with setup file two_sided_pay_as_clear.default_2a and parameters [24, 60, 60, 1, 1]
     Then all traded energy have finite value

  Scenario: Test offers, bids and market-clearing-rate are exported
     Given we have a scenario named two_sided_pay_as_clear/default_2a
     And d3a is installed
     When we run the d3a simulation on console with two_sided_pay_as_clear.default_2a for 2 hrs
     Then there are files with offers, bids & market_clearing_rate for every area

  Scenario: Supply Demand Curve
     Given we have a scenario named two_sided_pay_as_clear/test_clearing_energy
     And d3a is installed
     When we run the d3a simulation on console with two_sided_pay_as_clear.test_clearing_energy for 24 hrs
     Then the export functionality of supply/demand curve is tested


  Scenario: One Offer and One Bid are matched at the Bid Rate
     Given we have a scenario named two_sided_pay_as_clear/one_offer_one_bid
     And d3a is installed
     When we run the simulation with setup file two_sided_pay_as_clear.one_offer_one_bid and parameters [24, 60, 60, 0, 1]
     Then one-on-one matching of offer & bid in PAC happens at bid rate

  Scenario: One Offer and multiple Bids are matched at the last clearing bid rate
     Given we have a scenario named two_sided_pay_as_clear/one_offer_multiple_bids
     And d3a is installed
     When we run the simulation with setup file two_sided_pay_as_clear.one_offer_multiple_bids and parameters [24, 60, 60, 0, 1]
     Then clearing rate is the bid rate of last matched bid
