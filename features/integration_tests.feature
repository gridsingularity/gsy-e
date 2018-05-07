Feature: Do integration test

#  Scenario: Run an integration test
#     Given we have a scenario named default_2b
#     When we run the d3a simulation with it
#      Then the results are tested

  Scenario Outline: Run integration tests
     Given we have a scenario named <scenario>
     And d3a is installed
     When we run the d3a simulation with <scenario>
     Then the results are tested for <scenario>
  Examples: Scenarios
    | scenario |
    | default_2a |
    | default_2b |