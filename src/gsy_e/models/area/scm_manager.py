import logging
from calendar import monthrange
from dataclasses import asdict, dataclass, field
from math import isclose
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

from gsy_framework.constants_limits import (
    ConstSettings, GlobalConfig, is_no_community_self_consumption)
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import SCMFeeType
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
    # market_maker_rate and feed_in_tariff units are the selected currency (e.g. Euro)
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
    fee_properties: Dict[str, float] = field(default_factory=dict)
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

        if is_no_community_self_consumption():
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
class FeeContainer:
    """
    Dataclass that holds the value of the fee and the accumulated value over time and
    over areas (price).
    """

    value: float = 0.
    price: float = 0.


@dataclass
class AreaFees:
    """Dataclass that contains all fees and their accumulated values"""

    grid_fee: float = 0.
    grid_fees_reduction: float = 0.
    per_kWh_fees: Dict[str, FeeContainer] = field(default_factory=dict)
    monthly_fees: Dict[str, FeeContainer] = field(default_factory=dict)

    def prices_as_dict(self) -> Dict:
        """Return all prices (accumulated values) for the fees in a dictionary."""
        return {
            name: fee.price
            for name, fee in {**self.per_kWh_fees, **self.monthly_fees}.items()
        }

    @property
    def total_per_kWh_fee_price(self):
        """Return the sum of all per_kWh_fee prices."""
        return sum(fee.price for fee in self.per_kWh_fees.values())

    @property
    def total_monthly_fee_price(self):
        """Return the sum of all monthly_fee prices."""
        return sum(fee.price for fee in self.monthly_fees.values())

    def add_price_to_fees(self, energy_kWh: float):
        """Add prices to the container."""
        for fee in self.per_kWh_fees.values():
            fee.price += fee.value * energy_kWh

    def add_fees_to_energy_rate(self, energy_rate: float) -> float:
        """Add per_kWh_fees values to energy_rate."""
        return energy_rate + sum(fee.value for fee in self.per_kWh_fees.values())

    @property
    def total_monthly_fees(self):
        """Return the sum of all monthly fees"""
        return sum(fee.value for fee in self.monthly_fees.values())

    @property
    def decreased_grid_fee(self):
        """Return the decreased grid_fee regarding the grid_fees_reduction."""
        return self.grid_fee * (1 - self.grid_fees_reduction)


@dataclass
class AreaEnergyRates:
    """Dataclass that holds the area fees and rates."""

    area_fees: AreaFees = field(default_factory=AreaFees)
    utility_rate: float = 0.
    intracommunity_base_rate: float = 0.
    feed_in_tariff: float = 0.

    @property
    def intracommunity_rate(self):
        """Return the rate that is used for trades inside of the community."""
        return self.area_fees.add_fees_to_energy_rate(
            self.intracommunity_base_rate + self.area_fees.decreased_grid_fee)

    @property
    def utility_rate_incl_fees(self):
        """Return the utility rate including all fees."""
        return self.area_fees.add_fees_to_energy_rate(self.utility_rate) + self.area_fees.grid_fee

    def accumulate_fees_in_community(self, area_fees=AreaFees):
        """Add prices from provided area_fees input to the self.area_fees;
        used for accumulation of the prices for the community bills."""
        for fee_name, fee_dict in area_fees.per_kWh_fees.items():
            if fee_name not in self.area_fees.per_kWh_fees:
                self.area_fees.per_kWh_fees[fee_name] = FeeContainer()
            self.area_fees.per_kWh_fees[fee_name].price += fee_dict.price
        for fee_name, fee_dict in area_fees.monthly_fees.items():
            if fee_name not in self.area_fees.monthly_fees:
                self.area_fees.monthly_fees[fee_name] = FeeContainer()
            self.area_fees.monthly_fees[fee_name].price += fee_dict.price


@dataclass
class AreaEnergyBills:  # pylint: disable=too-many-instance-attributes
    """Represents home energy bills."""
    energy_rates: AreaEnergyRates = AreaEnergyRates(AreaFees())
    base_energy_bill: float = 0.
    base_energy_bill_excl_revenue: float = 0.
    base_energy_bill_revenue: float = 0.
    gsy_energy_bill: float = 0.
    grid_fees: float = 0.
    bought_from_community: float = 0.
    spent_to_community: float = 0.
    sold_to_community: float = 0.
    earned_from_community: float = 0.
    bought_from_grid: float = 0.
    spent_to_grid: float = 0.
    sold_to_grid: float = 0.
    earned_from_grid: float = 0.
    self_consumed_savings: float = 0.
    _min_community_savings_percent: float = 0.
    _max_community_savings_percent: float = 0.

    def to_dict(self) -> Dict:
        """Dict representation of the area energy bills."""
        output_dict = asdict(self)
        del output_dict["energy_rates"]
        output_dict.update({
            "fees": self.energy_rates.area_fees.prices_as_dict(),
            "savings": self.savings,
            "savings_percent": self.savings_percent,
            "energy_benchmark": self.energy_benchmark,
            "home_balance_kWh": self.home_balance_kWh,
            "home_balance": self.home_balance,
            "gsy_energy_bill_excl_revenue": self.gsy_energy_bill_excl_revenue,
            "gsy_energy_bill_excl_revenue_without_fees":
                self.gsy_energy_bill_excl_revenue_without_fees,
            "gsy_energy_bill_excl_fees": self.gsy_energy_bill_excl_fees,
            "gsy_energy_bill_revenue": self.gsy_energy_bill_revenue,
            "gsy_total_benefit": self.gsy_total_benefit
        })
        return output_dict

    def set_bought_from_community(self, energy_kWh):
        """Update price and energy counters after buying energy from the community."""
        self.bought_from_community += energy_kWh
        self.spent_to_community += energy_kWh * self.energy_rates.intracommunity_rate
        self.gsy_energy_bill += energy_kWh * self.energy_rates.intracommunity_rate
        self.energy_rates.area_fees.add_price_to_fees(energy_kWh)
        self.grid_fees += energy_kWh * self.energy_rates.area_fees.decreased_grid_fee

    def set_sold_to_community(self, energy_kWh, energy_rate):
        """Update price and energy counters after buying energy from the community."""
        self.sold_to_community += energy_kWh
        self.earned_from_community += energy_kWh * energy_rate
        self.gsy_energy_bill -= energy_kWh * energy_rate

    def set_bought_from_grid(self, energy_kWh):
        """Update price and energy counters after buying energy from the grid."""
        self.bought_from_grid += energy_kWh
        self.spent_to_grid += energy_kWh * self.energy_rates.utility_rate_incl_fees
        self.gsy_energy_bill += energy_kWh * self.energy_rates.utility_rate_incl_fees
        self.energy_rates.area_fees.add_price_to_fees(energy_kWh)
        self.grid_fees += energy_kWh * self.energy_rates.area_fees.grid_fee

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
        if is_no_community_self_consumption():
            return self.self_consumed_savings + self.gsy_energy_bill_revenue
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
        return (self.gsy_energy_bill_excl_revenue
                - self.grid_fees
                - self.energy_rates.area_fees.total_per_kWh_fee_price
                - self.energy_rates.area_fees.total_monthly_fee_price)

    @property
    def gsy_energy_bill_revenue(self):
        """Total revenue from grid and community."""
        return self.earned_from_grid + self.earned_from_community

    @property
    def gsy_energy_bill_excl_fees(self):
        """Energy bill of the home excluding fees."""
        return (self.gsy_energy_bill
                - self.grid_fees
                - self.energy_rates.area_fees.total_per_kWh_fee_price
                - self.energy_rates.area_fees.total_monthly_fee_price)

    @property
    def gsy_total_benefit(self):
        """Calculate the total savings of the home, minus the monthly fees."""
        return self.savings - self.energy_rates.area_fees.total_monthly_fee_price

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
            self, home_data: HomeAfterMeterData, area_rates: AreaEnergyRates):
        """Calculate the base (not with GSy improvements) energy bill for the home."""
        if is_no_community_self_consumption():
            self.base_energy_bill_excl_revenue = (
                    home_data.consumption_kWh * area_rates.utility_rate_incl_fees)
            self.base_energy_bill_revenue = home_data.production_kWh * area_rates.feed_in_tariff
            self.base_energy_bill = (
                    self.base_energy_bill_excl_revenue - self.base_energy_bill_revenue)
        else:
            self.base_energy_bill_revenue = (
                    home_data.energy_surplus_kWh * area_rates.feed_in_tariff)
            self.base_energy_bill_excl_revenue = (
                    home_data.energy_need_kWh * area_rates.utility_rate_incl_fees +
                    area_rates.area_fees.total_monthly_fees)
            self.base_energy_bill = (
                    self.base_energy_bill_excl_revenue - self.base_energy_bill_revenue)


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
                      fee_properties: Dict,
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
            grid_fee=home_data.fee_properties.get(
                SCMFeeType.GRID_FEES.name, {}).get("grid_fee_constant", 0),
            grid_fees_reduction=self._grid_fees_reduction,
            per_kWh_fees={k: FeeContainer(value=v)
                          for k, v in home_data.fee_properties.get(
                    SCMFeeType.PER_KWH_FEES.name, {}).items()},
            monthly_fees={k: FeeContainer(value=v / slots_per_month)
                          for k, v in home_data.fee_properties.get(
                    SCMFeeType.MONTHLY_FEES.name, {}).items()}
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
