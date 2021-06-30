Feature: Savings KPI integration tests

  Scenario: Young Couple House
     Given we have a scenario named kpi.d3asim_3464_young_couple
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_3464_young_couple for 24 hrs
     Then saving_percentage of {'Young Couple House': -16.6667} are correctly reported

  Scenario: Family House with PV
     Given we have a scenario named kpi.d3asim_3464_family_with_pv
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_3464_family_with_pv for 24 hrs
     Then saving_percentage of {'Family 2 children with PV': -43.537} are correctly reported

  Scenario: Family House with PV & ESS
     Given we have a scenario named kpi.d3asim_3464_family_with_pv_ess
     And d3a is installed
     When we run the d3a simulation on console with kpi.d3asim_3464_family_with_pv_ess for 24 hrs
     Then saving_percentage of {'Family 2 children with PV + ESS': -176.514} are correctly reported
