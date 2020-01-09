Feature: KPI integration tests

  Scenario: House is not self sufficient
     Given we have a scenario named kpi.house_not_self_sufficient
     And d3a is installed
     When we run the d3a simulation on console with kpi.house_not_self_sufficient for 24 hrs
     Then self_sufficiency of {'Grid': 1.0, 'House 1': 0.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'House 1': None} are correctly reported

  Scenario: House is fully self sufficient
     Given we have a scenario named kpi.house_fully_self_sufficient
     And d3a is installed
     When we run the d3a simulation on console with kpi.house_fully_self_sufficient for 24 hrs
     Then self_sufficiency of {'Grid': 1.0, 'House 1': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'House 1': 1.0} are correctly reported

  Scenario: House is partially self sufficient
     Given we have a scenario named kpi.house_partially_self_sufficient
     And d3a is installed
     When we run the d3a simulation on console with kpi.house_partially_self_sufficient for 24 hrs
     Then self_sufficiency of {'Grid': 1.0, 'House 1': 0.34925} are correctly reported
     And self_consumption of {'Grid': 1.0, 'House 1': 1.0} are correctly reported

  Scenario: House fully self_sufficiency with storage
     Given we have a scenario named kpi.house_self_sufficient_with_ess
     And d3a is installed
     When we run the d3a simulation on console with kpi.house_self_sufficient_with_ess for 24 hrs
     Then self_sufficiency of {'Grid': 1.0, 'House 1': 1.0} are correctly reported
     And self_consumption of {'Grid': 0.7407, 'House 1': 0.7407} are correctly reported

  Scenario: Root Area fully self_sufficiency with InfinitBus
     Given we have a scenario named kpi.root_area_self_sufficient_with_infinitebus
     And d3a is installed
     When we run the d3a simulation on console with kpi.root_area_self_sufficient_with_infinitebus for 24 hrs
     Then self_sufficiency of {'Grid': 1.0} are correctly reported
     And self_consumption of {'Grid': 0.10524} are correctly reported
