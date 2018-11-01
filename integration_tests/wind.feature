Feature: WindStrategy Tests

  Scenario: WindUserProfileStrategy follows the profile provided by the user as csv
     Given we have a scenario named strategy_tests/user_profile_wind_csv
     And d3a is installed
     When we run the d3a simulation with strategy_tests.user_profile_wind_csv [24, 60, 60]
     Then the UserProfileWind follows the Wind profile of csv
