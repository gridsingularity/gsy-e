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
     Then self_sufficiency of {'Grid': 1.0, 'House 1': 0.3644} are correctly reported
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
     And self_consumption of {'Grid': 1.0} are correctly reported

  Scenario: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses for SSM
     Given we have a scenario named kpi.d3asim_2103
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2103 for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 0.8333, 'House 1': 1.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 0.71428, 'House 1': 1.0, 'House 2': 1.0, 'House 3': 0.5} are correctly reported

  Scenario: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses for PAB
     Given we have a scenario named kpi.d3asim_2103_2_sided_pab
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2103_2_sided_pab for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 1.0, 'House 1': 1.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 0.8571, 'House 1': 1.0, 'House 2': 1.0, 'House 3': 0.5} are correctly reported

  Scenario: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses with energy deficit for SSM
     Given we have a scenario named kpi.d3asim_2103_nopv1
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2103_nopv1 for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 0.666, 'House 1': 0.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 0.8, 'House 1': None, 'House 2': 1.0, 'House 3': 0.5} are correctly reported

  Scenario: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses with energy deficit for PAB
     Given we have a scenario named kpi.d3asim_2103_nopv1_2_sided_pab
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2103_nopv1_2_sided_pab for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 0.833, 'House 1': 0.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 1.0, 'House 1': None, 'House 2': 1.0, 'House 3': 0.5} are correctly reported

  Scenario: D3ASIM-2262, self sufficiency reports correct values on community that includes storage
     Given we have a scenario named kpi/d3asim_2262
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2262 for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 1.0, 'House 1': 0.66666, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 1.0, 'House 1': 1.0, 'House 2': 1.0, 'House 3': 0.5} are correctly reported
