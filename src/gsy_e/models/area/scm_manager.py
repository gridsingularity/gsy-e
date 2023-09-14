import logging
from calendar import monthrange
from dataclasses import asdict, dataclass, field
from math import isclose
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.sim_results.kpi_calculation_helper import KPICalculationHelper
from pendulum import DateTime, duration

import gsy_e.constants
from gsy_e.constants import (DEFAULT_SCM_COMMUNITY_NAME, DEFAULT_SCM_GRID_NAME,
                             FLOATING_POINT_TOLERANCE)
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea


@dataclass
class HomeAfterMeterData:
    # pylint: disable=too-many-instance-attributes
    """Represent all the after meter data for a single home area."""
    home_uuid: str
    home_name: str
    sharing_coefficient_percent: float = 0.
    # grid_fees, market_maker_rate and feed_in_tariff units are the selected currency (e.g. Euro)
    grid_fees: float = 0.
    taxes_surcharges: float = 0.
    fixed_monthly_fee: float = 0.
    marketplace_monthly_fee: float = 0.
    assistance_monthly_fee: float = 0.
    market_maker_rate: float = 0.
    feed_in_tariff: float = 0.
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh: float = 0.
    energy_surplus_kWh: float = 0.
    energy_need_kWh: float = 0.
    community_total_production_kWh: float = 0.
    _self_production_for_community_kWh: float = 0.
    trades: List[Trade] = None
    asset_energy_requirements_kWh: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Dict representation of the home after meter data."""
        output_dict = asdict(self)
        output_dict.update({
            "allocated_community_energy_kWh": self.allocated_community_energy_kWh,
            "energy_bought_from_community_kWh": self.energy_bought_from_community_kWh,
            "energy_sold_to_grid_kWh": self.energy_sold_to_grid_kWh,
        })
        return output_dict

    def serializable_dict(self) -> Dict:
        """Dict representation that can be serialized."""
        if not isclose(
            self.energy_surplus_kWh,
                self.energy_sold_to_grid_kWh + self.self_production_for_community_kWh):
            logging.error(
                "Incorrect calculation of sold to grid and self production for community. "
                "Home details: %s", self.to_dict())
        if abs(self.energy_sold_to_grid_kWh) > 1000.0:
            logging.error("Energy sold %s. Configuration %s, area %s.",
                          self.energy_sold_to_grid_kWh, gsy_e.constants.CONFIGURATION_ID,
                          self.home_uuid)
        output_dict = self.to_dict()
        output_dict["trades"] = [trade.serializable_dict() for trade in self.trades]
        return output_dict

    def __post_init__(self):
        # Self consumed energy of a home is the amount of energy that it consumes from its own
        # production. If the home production is larger than its consumption, self consumed energy
        # will be equal to the consumption, and if the consumption is larger than the production,
        # self consumed energy will be equal to the production. Hence, the upper limit of the
        # self consumed energy is the minimum of the production and consumption energy values
        # of the home.
        self.self_consumed_energy_kWh = min(self.consumption_kWh, self.production_kWh)
        self.energy_surplus_kWh = self.production_kWh - self.self_consumed_energy_kWh
        self.energy_need_kWh = self.consumption_kWh - self.self_consumed_energy_kWh
        assert not (self.energy_surplus_kWh > FLOATING_POINT_TOLERANCE and
                    self.energy_need_kWh > FLOATING_POINT_TOLERANCE)
        if self.trades is None:
            self.trades = []

    def set_total_community_production(self, energy_kWh: float):
        """
        Set the community energy production, in order to correctly generate the community-related
        home data.
        """
        self.community_total_production_kWh = energy_kWh

    def set_production_for_community(self, unassigned_energy_production_kWh: float):
        """Assign the energy surplus of the home to be consumed by the community."""
        if gsy_e.constants.SCM_NO_COMMUNITY_SELF_CONSUMPTION:
            self._self_production_for_community_kWh = 0
            return 0.
        if self.energy_surplus_kWh <= unassigned_energy_production_kWh:
            self._self_production_for_community_kWh = self.energy_surplus_kWh
            return unassigned_energy_production_kWh - self.energy_surplus_kWh
        self._self_production_for_community_kWh = unassigned_energy_production_kWh
        return 0.

    @property
    def self_production_for_community_kWh(self):
        """Part of the energy_surplus_kWh that is assigned to the community."""
        return self._self_production_for_community_kWh

    @property
    def self_production_for_grid_kWh(self):
        """Part of the energy_surplus_kWh that is assigned to the grid."""
        assert self.energy_surplus_kWh >= self._self_production_for_community_kWh
        return self.energy_surplus_kWh - self._self_production_for_community_kWh

    @property
    def allocated_community_energy_kWh(self) -> float:
        """Amount of community energy allocated to the home."""
        return self.community_total_production_kWh * self.sharing_coefficient_percent

    @property
    def energy_bought_from_community_kWh(self) -> float:
        """Amount of energy bought by the home from the community."""
        return min(self.allocated_community_energy_kWh, self.energy_need_kWh)

    @property
    def energy_sold_to_grid_kWh(self) -> float:
        """Amount of energy sold by the home to the grid."""
        if not isclose(
            self.production_kWh, (
                    self.self_production_for_community_kWh + self.self_production_for_grid_kWh +
                    self.self_consumed_energy_kWh)):
            logging.error(
                "Incorrect SCM calculation of sold to grid. Asset information: %s, "
                "Self production for grid: %s", asdict(self), self.self_production_for_grid_kWh)
        return self.self_production_for_grid_kWh

    def create_buy_trade(self, current_time_slot: DateTime, seller_name: str,
                         traded_energy_kWh: float, trade_price_cents: float) -> None:
        """Create and save a trade object for buying energy."""
        assert 0. < traded_energy_kWh <= self.energy_need_kWh, \
            f"Cannot buy more energy ({traded_energy_kWh}) than the energy need (" \
            f"{self.energy_need_kWh}) of the home ({self.home_name})."

        trade = Trade(
            str(uuid4()), current_time_slot,
            TraderDetails(seller_name, None, seller_name, None),
            TraderDetails(self.home_name, self.home_uuid, self.home_name, self.home_uuid),
            traded_energy=traded_energy_kWh, trade_price=trade_price_cents, residual=None,
            offer_bid_trade_info=None, fee_price=0., time_slot=current_time_slot)
        self.trades.append(trade)
        logging.info("[SCM][TRADE][BID] [%s] [%s] %s", self.home_name, trade.time_slot, trade)

    def create_sell_trade(self, current_time_slot: DateTime, buyer_name: str,
                          traded_energy_kWh: float, trade_price_cents: float):
        """Create and save a trade object for selling energy."""
        assert traded_energy_kWh <= self.energy_surplus_kWh, \
            f"Cannot sell more energy ({traded_energy_kWh}) than the energy surplus (" \
            f"{self.energy_surplus_kWh}) of the home ({self.home_name})."
        trade = Trade(
            str(uuid4()), current_time_slot,
            TraderDetails(self.home_name, self.home_uuid, self.home_name, self.home_uuid),
            TraderDetails(buyer_name, None, buyer_name, None),
            traded_energy=traded_energy_kWh, trade_price=trade_price_cents, residual=None,
            offer_bid_trade_info=None, fee_price=0., time_slot=current_time_slot)
        self.trades.append(trade)
        logging.info("[SCM][TRADE][OFFER] [%s] [%s] %s", self.home_name, trade.time_slot, trade)


@dataclass
class CommunityData:
    # pylint: disable=too-many-instance-attributes
    """Represent the energy related statistics of a community."""
    community_uuid: str
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh: float = 0.
    energy_surplus_kWh: float = 0.
    energy_need_kWh: float = 0.
    energy_bought_from_community_kWh: float = 0.
    energy_sold_to_grid_kWh: float = 0.
    trades: List[Trade] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Dict representation of the community energy data."""
        return asdict(self)

    def serializable_dict(self) -> Dict:
        """Dict representation that can be serialized."""
        output_dict = self.to_dict()
        output_dict["trades"] = [trade.serializable_dict() for trade in self.trades]
        return output_dict


@dataclass
class AreaEnergyBills:  # pylint: disable=too-many-instance-attributes
    """Represents home energy bills."""
    base_energy_bill: float = 0.
    base_energy_bill_excl_revenue: float = 0.
    base_energy_bill_revenue: float = 0.
    gsy_energy_bill: float = 0.
    grid_fees: float = 0.
    tax_surcharges: float = 0.
    bought_from_community: float = 0.
    spent_to_community: float = 0.
    sold_to_community: float = 0.
    earned_from_community: float = 0.
    bought_from_grid: float = 0.
    spent_to_grid: float = 0.
    sold_to_grid: float = 0.
    earned_from_grid: float = 0.
    marketplace_fee: float = 0.
    assistance_fee: float = 0.
    fixed_fee: float = 0.
    _min_community_savings_percent: float = 0.
    _max_community_savings_percent: float = 0.

    def to_dict(self) -> Dict:
        """Dict representation of the area energy bills."""
        output_dict = asdict(self)
        output_dict.update({
            "savings": self.savings,
            "savings_percent": self.savings_percent,
            "energy_benchmark": self.energy_benchmark,
            "home_balance_kWh": self.home_balance_kWh,
            "home_balance": self.home_balance,
            "gsy_energy_bill_excl_revenue": self.gsy_energy_bill_excl_revenue,
            "gsy_energy_bill_excl_revenue_without_fees":
                self.gsy_energy_bill_excl_revenue_without_fees
        })
        return output_dict

    def set_bought_from_community(
            self, energy_kWh, energy_rate, grid_fee_rate, tax_surcharge_rate):
        """Update price and energy counters after buying energy from the community."""
        self.bought_from_community += energy_kWh
        self.spent_to_community += energy_kWh * energy_rate
        self.gsy_energy_bill += energy_kWh * energy_rate
        self.tax_surcharges += energy_kWh * tax_surcharge_rate
        self.grid_fees += energy_kWh * grid_fee_rate

    def set_sold_to_community(self, energy_kWh, energy_rate):
        """Update price and energy counters after buying energy from the community."""
        self.sold_to_community += energy_kWh
        self.earned_from_community += energy_kWh * energy_rate
        self.gsy_energy_bill -= energy_kWh * energy_rate

    def set_bought_from_grid(
            self, energy_kWh, energy_rate, grid_fee_rate, tax_surcharge_rate):
        """Update price and energy counters after buying energy from the grid."""
        self.bought_from_grid += energy_kWh
        self.spent_to_grid += energy_kWh * energy_rate
        self.gsy_energy_bill += energy_kWh * energy_rate
        self.tax_surcharges += energy_kWh * tax_surcharge_rate
        self.grid_fees += energy_kWh * grid_fee_rate

    def set_sold_to_grid(self, energy_kWh, energy_rate):
        """Update price and energy counters after selling energy to the grid."""
        self.sold_to_grid += energy_kWh
        self.earned_from_grid += energy_kWh * energy_rate
        self.gsy_energy_bill -= energy_kWh * energy_rate

    def set_min_max_community_savings(
            self, min_savings_percent: float, max_savings_percent: float):
        """
        Update the minimum and maximum saving of a home in the community.
        Used in order to calculate the energy benchmark.
        """
        self._min_community_savings_percent = min_savings_percent
        self._max_community_savings_percent = max_savings_percent

    @property
    def savings(self):
        """Absolute price savings of the home, compared to the base energy bill."""
        # The savings and the percentage might produce negative and huge percentage values
        # in cases of production. This is due to the fact that the energy bill in these cases
        # will be negative, and the producer will not have "savings". For a more realistic case
        # the revenue should be omitted from the calculation of the savings, however this needs
        # to be discussed.
        savings_absolute = KPICalculationHelper().saving_absolute(
            self.base_energy_bill_excl_revenue, self.gsy_energy_bill_excl_revenue)
        assert savings_absolute > -FLOATING_POINT_TOLERANCE
        return savings_absolute

    @property
    def savings_percent(self):
        """Percentage of the price savings of the home, compared to the base energy bill."""
        return KPICalculationHelper().saving_percentage(
            self.savings, self.base_energy_bill_excl_revenue)

    @property
    def energy_benchmark(self):
        """Savings ranking compared to the homes with the min and max savings."""
        return KPICalculationHelper().energy_benchmark(
            self.savings_percent, self._min_community_savings_percent,
            self._max_community_savings_percent)

    @property
    def gsy_energy_bill_excl_revenue(self):
        """Energy bill of the home excluding revenue."""
        return self.gsy_energy_bill + self.earned_from_grid + self.earned_from_community

    @property
    def gsy_energy_bill_excl_revenue_without_fees(self):
        """Energy bill of the home excluding revenue and excluding all fees."""
        return (self.gsy_energy_bill_excl_revenue - self.grid_fees - self.tax_surcharges
                - self.fixed_fee - self.marketplace_fee - self.assistance_fee)

    @property
    def home_balance_kWh(self):
        """Energy balance of the home. Equals to energy bought minus energy sold."""
        return (self.bought_from_grid + self.bought_from_community
                - self.sold_to_grid - self.sold_to_community)

    @property
    def home_balance(self):
        """Price balance of the home. Equals to currency spent minus currency earned."""
        return (self.spent_to_grid + self.spent_to_community
                - self.earned_from_grid - self.earned_from_community)

    def calculate_base_energy_bill(
            self, home_data: HomeAfterMeterData, market_maker_rate_normal_fees: float,
            feed_in_tariff: float):
        """Calculate the base (not with GSy improvements) energy bill for the home."""
        if gsy_e.constants.SCM_NO_COMMUNITY_SELF_CONSUMPTION:
            self.base_energy_bill_excl_revenue = (
                    home_data.consumption_kWh * market_maker_rate_normal_fees)
            self.base_energy_bill_revenue = home_data.production_kWh * feed_in_tariff
            self.base_energy_bill = (
                    self.base_energy_bill_excl_revenue - self.base_energy_bill_revenue)
        else:
            base_energy_bill = (
                    home_data.energy_need_kWh * market_maker_rate_normal_fees +
                    self.marketplace_fee + self.fixed_fee + self.assistance_fee -
                    home_data.energy_surplus_kWh * feed_in_tariff)
            self.base_energy_bill = base_energy_bill
            self.base_energy_bill_revenue = home_data.energy_surplus_kWh * feed_in_tariff
            self.base_energy_bill_excl_revenue = (
                    home_data.energy_need_kWh * market_maker_rate_normal_fees +
                    self.marketplace_fee + self.fixed_fee + self.assistance_fee)


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
                      grid_fees: float, coefficient_percentage: float,
                      taxes_surcharges: float, fixed_monthly_fee: float,
                      marketplace_monthly_fee: float, assistance_monthly_fee: float,
                      market_maker_rate: float, feed_in_tariff: float,
                      production_kWh: float, consumption_kWh: float,
                      asset_energy_requirements_kWh: Dict[str, float]):
        # pylint: disable=too-many-arguments
        """Import data for one individual home."""
        if grid_fees is None:
            grid_fees = 0.0
        self._home_data[home_uuid] = HomeAfterMeterData(
            home_uuid, home_name,
            grid_fees=grid_fees,
            sharing_coefficient_percent=coefficient_percentage,
            fixed_monthly_fee=fixed_monthly_fee,
            marketplace_monthly_fee=marketplace_monthly_fee,
            assistance_monthly_fee=assistance_monthly_fee,
            taxes_surcharges=taxes_surcharges,
            market_maker_rate=market_maker_rate,
            feed_in_tariff=feed_in_tariff,
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

    def calculate_home_energy_bills(
            self, home_uuid: str) -> None:
        """Calculate energy bills for one home."""
        assert home_uuid in self._home_data

        home_data = self._home_data[home_uuid]

        market_maker_rate = home_data.market_maker_rate
        grid_fees = home_data.grid_fees
        taxes_surcharges = home_data.taxes_surcharges
        feed_in_tariff = home_data.feed_in_tariff

        slots_per_month = (duration(days=1) / GlobalConfig.slot_length) * monthrange(
            self._time_slot.year, self._time_slot.month)[1]
        marketplace_fee = home_data.marketplace_monthly_fee / slots_per_month
        assistance_fee = home_data.assistance_monthly_fee / slots_per_month
        fixed_fee = home_data.fixed_monthly_fee / slots_per_month

        market_maker_rate_decreased_fees = (
                market_maker_rate + grid_fees * (1.0 - self._grid_fees_reduction) +
                taxes_surcharges)
        market_maker_rate_normal_fees = market_maker_rate + grid_fees + taxes_surcharges

        home_bill = AreaEnergyBills(
            marketplace_fee=marketplace_fee, fixed_fee=fixed_fee, assistance_fee=assistance_fee,
            gsy_energy_bill=marketplace_fee + fixed_fee + assistance_fee)
        home_bill.calculate_base_energy_bill(
            home_data, market_maker_rate_normal_fees, feed_in_tariff)

        # First handle the sold energy case. This case occurs in case of energy surplus of a home.
        if home_data.energy_surplus_kWh > 0.0:
            home_bill.set_sold_to_community(
                home_data.self_production_for_community_kWh, market_maker_rate_decreased_fees)
            if home_data.self_production_for_community_kWh > FLOATING_POINT_TOLERANCE:
                home_data.create_sell_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                    home_data.self_production_for_community_kWh,
                    home_data.self_production_for_community_kWh *
                    market_maker_rate_decreased_fees)

            home_bill.set_sold_to_grid(
                home_data.self_production_for_grid_kWh, feed_in_tariff)
            if home_data.self_production_for_grid_kWh > FLOATING_POINT_TOLERANCE:
                home_data.create_sell_trade(
                    self._time_slot, DEFAULT_SCM_GRID_NAME,
                    home_data.self_production_for_grid_kWh,
                    home_data.self_production_for_grid_kWh * feed_in_tariff)

        # Next case is the consumption. In this case the energy allocated from the community
        # is sufficient to cover the energy needs of the home.
        if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
            if home_data.energy_need_kWh > FLOATING_POINT_TOLERANCE:
                home_bill.set_bought_from_community(
                    home_data.energy_need_kWh, market_maker_rate_decreased_fees,
                    grid_fees * (1.0 - self._grid_fees_reduction), taxes_surcharges
                )
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME, home_data.energy_need_kWh,
                    home_data.energy_need_kWh * market_maker_rate_decreased_fees
                )
        # Next case is in case the allocated energy from the community is not sufficient for the
        # home energy needs. In this case the energy deficit is bought from the grid.
        else:
            home_bill.set_bought_from_community(
                home_data.allocated_community_energy_kWh, market_maker_rate_decreased_fees,
                grid_fees * (1.0 - self._grid_fees_reduction), taxes_surcharges
            )

            energy_from_grid_kWh = (
                    home_data.energy_need_kWh - home_data.allocated_community_energy_kWh)
            home_bill.set_bought_from_grid(energy_from_grid_kWh, market_maker_rate_normal_fees,
                                           grid_fees, taxes_surcharges)

            if home_data.allocated_community_energy_kWh > 0.0:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                    home_data.allocated_community_energy_kWh,
                    home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees
                )

            if energy_from_grid_kWh > 0.:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_GRID_NAME,
                    energy_from_grid_kWh,
                    energy_from_grid_kWh * market_maker_rate_normal_fees
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
            community_bills.gsy_energy_bill += data.gsy_energy_bill
            community_bills.base_energy_bill_excl_revenue += data.base_energy_bill_excl_revenue

            community_bills.bought_from_community += data.bought_from_community
            community_bills.spent_to_community += data.spent_to_community
            community_bills.sold_to_community += data.sold_to_community
            community_bills.earned_from_community += data.earned_from_community

            community_bills.bought_from_grid += data.bought_from_grid
            community_bills.spent_to_grid += data.spent_to_grid
            community_bills.sold_to_grid += data.sold_to_grid
            community_bills.earned_from_grid += data.earned_from_grid

            community_bills.tax_surcharges += data.tax_surcharges
            community_bills.grid_fees += data.grid_fees
            community_bills.marketplace_fee += data.marketplace_fee
            community_bills.assistance_fee += data.assistance_fee
            community_bills.fixed_fee += data.fixed_fee

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
