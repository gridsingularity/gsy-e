Feature: Savings KPI integration tests

  Scenario Outline: Savings KPI Cases
     Given we have a scenario named <setup>
     And gsy_e is installed
     When we run the gsy_e simulation on console with <setup> for 24 hrs
     Then saving_percentage of {'<scenario>': <saving_percentage>} are correctly reported
  Examples: Cases
    | scenario                          | setup                               | saving_percentage |
    | Young Couple House                | kpi.d3asim_3464_young_couple        |     16.6667      |
    | Family 2 children with PV         | kpi.d3asim_3464_family_with_pv      |     43.537       |
    | Family 2 children with PV + ESS   | kpi.d3asim_3464_family_with_pv_ess  |     176.514      |
