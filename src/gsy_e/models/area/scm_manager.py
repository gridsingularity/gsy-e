from calendar import monthrange
from math import isclose
from typing import TYPE_CHECKING, Dict, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime, duration

import gsy_e.constants
from gsy_e.constants import (DEFAULT_SCM_COMMUNITY_NAME, DEFAULT_SCM_GRID_NAME,
                             FLOATING_POINT_TOLERANCE)
from gsy_e.models.area.scm_dataclasses import (HomeAfterMeterData, CommunityData, AreaFees,
                                               AreaEnergyRates, FeeContainer, FeeProperties,
                                               AreaEnergyBills)
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea


class SCMManager:
    """Handle the community manager coefficient trade."""

    def __init__(self, area: "CoefficientArea", time_slot: DateTime):
        SCMCommunityValidator.validate(community=area)

        self._home_data: Dict[str, HomeAfterMeterData] = {}

        self._community_uuid = self._get_community_uuid_from_area(area)
        self.community_data = CommunityData(self._community_uuid)
        self._time_slot = time_slot
        self._bills: Dict[str, AreaEnergyBills] = {}
        self._grid_fees_reduction = ConstSettings.SCMSettings.GRID_FEES_REDUCTION
        self._intracommunity_base_rate_eur = ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR

    @staticmethod
    def _get_community_uuid_from_area(area):
        # Community is always the root area in the context of SCM.
        # The following hack in order to support the UI which defines the Community one level
        # lower than the Grid area.
        if "Community" in area.name:
            return area.uuid

        for child in area.children:
            if "Community" in child.name:
                return child.uuid
        assert False, f"Should not reach here, configuration {gsy_e.constants.CONFIGURATION_ID}" \
                      f"should have an area with name 'Community' either on the top level or " \
                      f"on the second level after the top."

    def add_home_data(self, home_uuid: str, home_name: str,
                      coefficient_percentage: float,
                      market_maker_rate: float, feed_in_tariff: float,
                      fee_properties: FeeProperties,
                      production_kWh: float, consumption_kWh: float,
                      asset_energy_requirements_kWh: Dict[str, float]):
        # pylint: disable=too-many-arguments
        """Import data for one individual home."""
        self._home_data[home_uuid] = HomeAfterMeterData(
            home_uuid, home_name,
            sharing_coefficient_percent=coefficient_percentage,
            market_maker_rate=market_maker_rate,
            feed_in_tariff=feed_in_tariff,
            fee_properties=fee_properties,
            production_kWh=production_kWh,
            consumption_kWh=consumption_kWh,
            asset_energy_requirements_kWh=asset_energy_requirements_kWh)

    def calculate_community_after_meter_data(self):
        """Calculate community data by aggregating all single home data."""

        # Reset the community data in order to generate correct results even after consecutive
        # calls of this method.
        self.community_data = CommunityData(self._community_uuid)
        for data in self._home_data.values():
            self.community_data.production_kWh += data.production_kWh
            self.community_data.consumption_kWh += data.consumption_kWh
            self.community_data.self_consumed_energy_kWh += data.self_consumed_energy_kWh
            self.community_data.energy_surplus_kWh += data.energy_surplus_kWh
            self.community_data.energy_need_kWh += data.energy_need_kWh

        for home_data in self._home_data.values():
            home_data.set_total_community_production(
                self.community_data.energy_surplus_kWh)

        unassigned_energy_production_kWh = sum(home_data.energy_bought_from_community_kWh
                                               for home_data in self._home_data.values())
        for home_data in self._home_data.values():
            unassigned_energy_production_kWh = home_data.set_production_for_community(
                unassigned_energy_production_kWh)
            self.community_data.energy_bought_from_community_kWh += (
                home_data.energy_bought_from_community_kWh)
            self.community_data.energy_sold_to_grid_kWh += home_data.energy_sold_to_grid_kWh
            self.community_data.self_consumed_energy_kWh += (
                home_data.self_production_for_community_kWh)

    def _init_area_energy_rates(self, home_data: HomeAfterMeterData) -> AreaEnergyRates:
        slots_per_month = (duration(days=1) / GlobalConfig.slot_length) * monthrange(
            self._time_slot.year, self._time_slot.month)[1]

        intracommunity_base_rate = (
            home_data.market_maker_rate
            if self._intracommunity_base_rate_eur is None
            else self._intracommunity_base_rate_eur)

        area_fees = AreaFees(
            grid_fee=home_data.fee_properties.GRID_FEES.get("grid_fee_constant", 0),
            grid_fees_reduction=self._grid_fees_reduction,
            per_kWh_fees={k: FeeContainer(value=v)
                          for k, v in home_data.fee_properties.PER_KWH_FEES.items()},
            monthly_fees={k: FeeContainer(value=v / slots_per_month)
                          for k, v in home_data.fee_properties.MONTHLY_FEES.items()}
        )
        return AreaEnergyRates(
            area_fees=area_fees,
            utility_rate=home_data.market_maker_rate,
            intracommunity_base_rate=intracommunity_base_rate,
            feed_in_tariff=home_data.feed_in_tariff
        )

    def calculate_home_energy_bills(self, home_uuid: str) -> None:
        """Calculate energy bills for one home."""
        assert home_uuid in self._home_data
        home_data = self._home_data[home_uuid]

        area_rates = self._init_area_energy_rates(home_data)
        home_bill = AreaEnergyBills(
            energy_rates=area_rates,
            gsy_energy_bill=area_rates.area_fees.total_monthly_fees,
            self_consumed_savings=home_data.self_consumed_energy_kWh * home_data.market_maker_rate)
        home_bill.calculate_base_energy_bill(home_data, area_rates)

        # First handle the sold energy case. This case occurs in case of energy surplus of a home.
        if home_data.energy_surplus_kWh > 0.0:
            home_bill.set_sold_to_community(
                home_data.self_production_for_community_kWh, area_rates.intracommunity_rate)
            if home_data.self_production_for_community_kWh > FLOATING_POINT_TOLERANCE:
                home_data.create_sell_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                    home_data.self_production_for_community_kWh,
                    home_data.self_production_for_community_kWh *
                    area_rates.intracommunity_rate)

            home_bill.set_sold_to_grid(
                home_data.self_production_for_grid_kWh, home_data.feed_in_tariff)
            if home_data.self_production_for_grid_kWh > FLOATING_POINT_TOLERANCE:
                home_data.create_sell_trade(
                    self._time_slot, DEFAULT_SCM_GRID_NAME,
                    home_data.self_production_for_grid_kWh,
                    home_data.self_production_for_grid_kWh * home_data.feed_in_tariff)

        # Next case is the consumption. In this case the energy allocated from the community
        # is sufficient to cover the energy needs of the home.
        if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
            if home_data.energy_need_kWh > FLOATING_POINT_TOLERANCE:
                home_bill.set_bought_from_community(home_data.energy_need_kWh)
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME, home_data.energy_need_kWh,
                    home_data.energy_need_kWh * area_rates.intracommunity_rate
                )
        # Next case is in case the allocated energy from the community is not sufficient for the
        # home energy needs. In this case the energy deficit is bought from the grid.
        else:
            home_bill.set_bought_from_community(home_data.allocated_community_energy_kWh)

            energy_from_grid_kWh = (
                    home_data.energy_need_kWh - home_data.allocated_community_energy_kWh)
            home_bill.set_bought_from_grid(energy_from_grid_kWh)

            if home_data.allocated_community_energy_kWh > 0.0:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                    home_data.allocated_community_energy_kWh,
                    home_data.allocated_community_energy_kWh * area_rates.intracommunity_rate
                )

            if energy_from_grid_kWh > 0.:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_GRID_NAME,
                    energy_from_grid_kWh,
                    energy_from_grid_kWh * area_rates.utility_rate_incl_fees
                )

        self._bills[home_uuid] = home_bill

    def accumulate_community_trades(self):
        """
        Gather all trades from homes to the community after meter data, in order to have them
        available for the simulation results generation.
        """
        for home_data in self._home_data.values():
            self.community_data.trades.extend(home_data.trades)

    def get_area_results(self, area_uuid: str, serializable: bool = False) -> Dict:
        """Return the SCM results for one area (and one time slot)."""
        if area_uuid == self._community_uuid:
            return {
                "bills": self.community_bills,
                "after_meter_data": (
                    self.community_data.to_dict() if serializable is False else
                    self.community_data.serializable_dict()
                ),
                "trades": [
                    trade.serializable_dict()
                    for trade in self.community_data.trades
                ]
            }

        if area_uuid not in self._bills:
            return {"bills": {}, "after_meter_data": {}, "trades": []}

        min_savings = min(bill.savings_percent for bill in self._bills.values())
        max_savings = max(bill.savings_percent for bill in self._bills.values())
        for bill in self._bills.values():
            bill.set_min_max_community_savings(min_savings, max_savings)

        return {
            "bills": self._bills[area_uuid].to_dict(),
            "after_meter_data": (
                self._home_data[area_uuid].to_dict() if serializable is False else
                self._home_data[area_uuid].serializable_dict()
            ),
            "trades": [
                trade.serializable_dict()
                for trade in self._home_data[area_uuid].trades
            ]
        }

    def get_after_meter_data(self, area_uuid: str) -> Optional[HomeAfterMeterData]:
        """Get after meter data for the home with area_uuid. Returns None for invalid uuid."""
        return self._home_data.get(area_uuid)

    def get_home_energy_need(self, home_uuid: str) -> float:
        """Get home energy need in kWh"""
        assert home_uuid in self._home_data

        return self._home_data[home_uuid].energy_need_kWh

    @property
    def community_bills(self) -> Dict:
        """Calculate bills for the community."""
        community_bills = AreaEnergyBills()
        for data in self._bills.values():
            community_bills.base_energy_bill += data.base_energy_bill
            community_bills.base_energy_bill_revenue += data.base_energy_bill_revenue
            community_bills.base_energy_bill_excl_revenue += data.base_energy_bill_excl_revenue
            community_bills.gsy_energy_bill += data.gsy_energy_bill

            community_bills.bought_from_community += data.bought_from_community
            community_bills.spent_to_community += data.spent_to_community
            community_bills.sold_to_community += data.sold_to_community
            community_bills.earned_from_community += data.earned_from_community

            community_bills.bought_from_grid += data.bought_from_grid
            community_bills.spent_to_grid += data.spent_to_grid
            community_bills.sold_to_grid += data.sold_to_grid
            community_bills.earned_from_grid += data.earned_from_grid

            community_bills.energy_rates.accumulate_fees_in_community(data.energy_rates.area_fees)
            community_bills.grid_fees += data.grid_fees

        return community_bills.to_dict()


class SCMCommunityValidator:
    """Validator for SCM Community areas."""

    @classmethod
    def validate(cls, community: "CoefficientArea") -> None:
        """Run all validations for the given community."""
        cls._validate_coefficients(community)
        cls._validate_market_maker_rate(community)
        # Disabled validation due to infinite bus.
        # cls._validate_all_strategies_scm(community)

    @classmethod
    def _sum_of_all_coefficients_in_grid(cls, area):
        coefficient_sum = sum(
            cls._sum_of_all_coefficients_in_grid(child)
            for child in area.children
        )
        return coefficient_sum + area.coefficient_percentage

    @staticmethod
    def _validate_all_strategies_scm(community):
        for home in community.children:
            assert all(isinstance(asset.strategy, SCMStrategy) for asset in home.children), \
                f"Home {home.name} has assets with non-SCM strategies."

    @classmethod
    def _validate_coefficients(cls, community: "CoefficientArea") -> None:
        assert isclose(cls._sum_of_all_coefficients_in_grid(community), 1.0), \
            "Coefficients from all homes should sum up to 1."

    @staticmethod
    def _validate_market_maker_rate(community: "CoefficientArea") -> None:
        for home in community.children:
            assert home.market_maker_rate is not None, \
                f"Home {home.name} does not define market_maker_rate."
