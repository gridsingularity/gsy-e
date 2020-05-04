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

  Scenario Outline: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses
     Given we have a scenario named <scenario_file>
     And d3a is installed
     When we run the d3a simulation on console with <scenario_file> for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 1.0, 'House 1': 1.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 0.8571, 'House 1': 1.0, 'House 2': 1.0, 'House 3': 0.5} are correctly reported
  Examples:
    | scenario_file               |
    | kpi.d3asim_2103             |
    | kpi.d3asim_2103_2_sided_pab |

  Scenario Outline: D3ASIM-2103, self sufficiency reports correct values on levels higher than houses with energy deficit
     Given we have a scenario named <scenario_file>
     And d3a is installed
     When we run the d3a simulation on console with <scenario_file> for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 0.8333, 'House 1': 0.0, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 1.0, 'House 1': None, 'House 2': 1.0, 'House 3': 0.5} are correctly reported
  Examples:
    | scenario_file                     |
    | kpi.d3asim_2103_nopv1             |
    | kpi.d3asim_2103_nopv1_2_sided_pab |

  Scenario: D3ASIM-2262, self sufficiency reports correct values on community that includes storage
     Given we have a scenario named kpi/d3asim_2262
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_2262 for 24 hrs (30, 30)
     Then self_sufficiency of {'Grid': 1.0, 'Community': 1.0, 'House 1': 0.66666, 'House 2': 0.5, 'House 3': 1.0} are correctly reported
     And self_consumption of {'Grid': 1.0, 'Community': 1.0, 'House 1': 1.0, 'House 2': 1.0, 'House 3': 0.5} are correctly reported
