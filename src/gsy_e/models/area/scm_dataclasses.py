import logging
from dataclasses import fields, asdict, dataclass, field
from math import isclose
from typing import Dict, List
from uuid import uuid4

from pendulum import DateTime

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.sim_results.kpi_calculation_helper import KPICalculationHelper

import gsy_e.constants


@dataclass
class SCMAreaProperties:
    """Holds all fee properties of a coefficient area"""

    GRID_FEES: Dict = field(default_factory=dict)
    PER_KWH_FEES: Dict = field(default_factory=dict)
    MONTHLY_FEES: Dict = field(default_factory=dict)
    AREA_PROPERTIES: Dict = field(default_factory=dict)

    def validate(self):
        """Validate if all fee values are not None."""
        for fee_group in fields(self.__class__):
            for fee_value in getattr(self, fee_group.name).values():
                assert fee_value is not None


@dataclass
class HomeAfterMeterData:
    # pylint: disable=too-many-instance-attributes
    """Represent all the after meter data for a single home area."""

    home_uuid: str
    home_name: str
    consumption_kWh: float = 0.0
    production_kWh: float = 0.0
    self_consumed_energy_kWh: float = 0.0
    energy_surplus_kWh: float = 0.0
    energy_need_kWh: float = 0.0
    community_total_production_kWh: float = 0.0
    _self_production_for_community_kWh: float = 0.0
    trades: List[Trade] = None
    area_properties: SCMAreaProperties = field(default_factory=SCMAreaProperties)

    def to_dict(self) -> Dict:
        """Dict representation of the home after meter data."""
        output_dict = asdict(self)
        output_dict.update(
            {
                "allocated_community_energy_kWh": self.allocated_community_energy_kWh,
                "energy_bought_from_community_kWh": self.energy_bought_from_community_kWh,
                "energy_sold_to_grid_kWh": self.energy_sold_to_grid_kWh,
            }
        )
        return output_dict

    def serializable_dict(self) -> Dict:
        """Dict representation that can be serialized."""
        if not isclose(
            self.energy_surplus_kWh,
            self.energy_sold_to_grid_kWh + self.self_production_for_community_kWh,
        ):
            logging.error(
                "Incorrect calculation of sold to grid and self production for community. "
                "Home details: %s",
                self.to_dict(),
            )
        if abs(self.energy_sold_to_grid_kWh) > 1000.0:
            logging.error(
                "Energy sold %s. Configuration %s, area %s.",
                self.energy_sold_to_grid_kWh,
                gsy_e.constants.CONFIGURATION_ID,
                self.home_uuid,
            )
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
        if gsy_e.constants.SCM_DISABLE_HOME_SELF_CONSUMPTION:
            self.self_consumed_energy_kWh = 0.0
        else:
            self.self_consumed_energy_kWh = min(self.consumption_kWh, self.production_kWh)
        self.energy_surplus_kWh = self.production_kWh - self.self_consumed_energy_kWh
        self.energy_need_kWh = self.consumption_kWh - self.self_consumed_energy_kWh
        if not gsy_e.constants.SCM_DISABLE_HOME_SELF_CONSUMPTION:
            assert not (
                self.energy_surplus_kWh > FLOATING_POINT_TOLERANCE
                and self.energy_need_kWh > FLOATING_POINT_TOLERANCE
            )
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
        if self.energy_surplus_kWh <= unassigned_energy_production_kWh:
            self._self_production_for_community_kWh = self.energy_surplus_kWh
            return unassigned_energy_production_kWh - self.energy_surplus_kWh
        self._self_production_for_community_kWh = unassigned_energy_production_kWh
        return 0.0

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
        return (
            self.community_total_production_kWh
            * self.area_properties.AREA_PROPERTIES["coefficient_percentage"]
        )

    @property
    def energy_bought_from_community_kWh(self) -> float:
        """Amount of energy bought by the home from the community."""
        return min(self.allocated_community_energy_kWh, self.energy_need_kWh)

    @property
    def energy_sold_to_grid_kWh(self) -> float:
        """Amount of energy sold by the home to the grid."""
        if not isclose(
            self.production_kWh,
            (
                self.self_production_for_community_kWh
                + self.self_production_for_grid_kWh
                + self.self_consumed_energy_kWh
            ),
        ):
            logging.error(
                "Incorrect SCM calculation of sold to grid. Asset information: %s, "
                "Self production for grid: %s",
                asdict(self),
                self.self_production_for_grid_kWh,
            )
        return self.self_production_for_grid_kWh

    def create_buy_trade(
        self,
        current_time_slot: DateTime,
        seller_name: str,
        traded_energy_kWh: float,
        trade_price_cents: float,
    ) -> None:
        """Create and save a trade object for buying energy."""
        assert 0.0 < traded_energy_kWh <= self.energy_need_kWh, (
            f"Cannot buy more energy ({traded_energy_kWh}) than the energy need ("
            f"{self.energy_need_kWh}) of the home ({self.home_name})."
        )

        trade = Trade(
            str(uuid4()),
            current_time_slot,
            TraderDetails(seller_name, None, seller_name, None),
            TraderDetails(self.home_name, self.home_uuid, self.home_name, self.home_uuid),
            traded_energy=traded_energy_kWh,
            trade_price=trade_price_cents,
            residual=None,
            offer_bid_trade_info=None,
            fee_price=0.0,
            time_slot=current_time_slot,
        )
        self.trades.append(trade)
        logging.info("[SCM][TRADE][BID] [%s] [%s] %s", self.home_name, trade.time_slot, trade)

    def create_sell_trade(
        self,
        current_time_slot: DateTime,
        buyer_name: str,
        traded_energy_kWh: float,
        trade_price_cents: float,
    ):
        """Create and save a trade object for selling energy."""
        assert traded_energy_kWh <= self.energy_surplus_kWh, (
            f"Cannot sell more energy ({traded_energy_kWh}) than the energy surplus ("
            f"{self.energy_surplus_kWh}) of the home ({self.home_name})."
        )
        trade = Trade(
            str(uuid4()),
            current_time_slot,
            TraderDetails(self.home_name, self.home_uuid, self.home_name, self.home_uuid),
            TraderDetails(buyer_name, None, buyer_name, None),
            traded_energy=traded_energy_kWh,
            trade_price=trade_price_cents,
            residual=None,
            offer_bid_trade_info=None,
            fee_price=0.0,
            time_slot=current_time_slot,
        )
        self.trades.append(trade)
        logging.info("[SCM][TRADE][OFFER] [%s] [%s] %s", self.home_name, trade.time_slot, trade)


class HomeAfterMeterDataWithoutSurplusTrade(HomeAfterMeterData):
    """Dedicated HomeAfterMeterData class, specific for the non-suplus trade SCM."""

    def set_production_for_community(self, unassigned_energy_production_kWh: float):
        """Assign the energy surplus of the home to be consumed by the community."""
        self._self_production_for_community_kWh = 0
        return 0.0


@dataclass
class CommunityData:
    # pylint: disable=too-many-instance-attributes
    """Represent the energy related statistics of a community."""

    community_uuid: str
    consumption_kWh: float = 0.0
    production_kWh: float = 0.0
    self_consumed_energy_kWh: float = 0.0
    energy_surplus_kWh: float = 0.0
    energy_need_kWh: float = 0.0
    energy_bought_from_community_kWh: float = 0.0
    energy_sold_to_grid_kWh: float = 0.0
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

    value: float = 0.0
    price: float = 0.0


@dataclass
class ContractedPowerFeeContainer:
    """
    Dataclass that holds the value of the fee and the accumulated value over time and
    over areas (price).
    """

    value: float = 0.0
    price: float = 0.0


@dataclass
class AreaFees:
    """Dataclass that contains all fees and their accumulated values"""

    grid_import_fee_const: float = 0.0
    grid_export_fee_const: float = 0.0
    grid_fees_reduction: float = 0.0
    per_kWh_fees: Dict[str, FeeContainer] = field(default_factory=dict)
    monthly_fees: Dict[str, FeeContainer] = field(default_factory=dict)

    def prices_as_dict(self) -> Dict:
        """Return all prices (accumulated values) for the fees in a dictionary."""
        # monthly fees are not accumulated but already set for the market slot,
        # hence we only report the value of the FeeContainer here
        monthly_prices = {name: fee.value for name, fee in self.monthly_fees.items()}
        per_kwh_prices = {name: fee.price for name, fee in self.per_kWh_fees.items()}
        return {**monthly_prices, **per_kwh_prices}

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
        return self.grid_import_fee_const * (1 - self.grid_fees_reduction)


@dataclass
class AreaEnergyRates:
    """Dataclass that holds the area fees and rates."""

    area_fees: AreaFees = field(default_factory=AreaFees)
    utility_rate: float = 0.0
    intracommunity_base_rate: float = 0.0
    feed_in_tariff: float = 0.0

    @property
    def intracommunity_rate(self):
        """Return the rate that is used for trades inside of the community."""
        return self.intracommunity_base_rate + self.area_fees.decreased_grid_fee

    @property
    def utility_rate_incl_fees(self):
        """Return the utility rate including all fees."""
        return (
            self.area_fees.add_fees_to_energy_rate(self.utility_rate)
            + self.area_fees.grid_import_fee_const
        )

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

    energy_rates: AreaEnergyRates = field(default_factory=AreaEnergyRates)
    base_energy_bill: float = 0.0
    base_energy_bill_excl_revenue: float = 0.0
    base_energy_bill_revenue: float = 0.0
    gsy_energy_bill: float = 0.0
    bought_from_community: float = 0.0
    spent_to_community: float = 0.0
    sold_to_community: float = 0.0
    earned_from_community: float = 0.0
    bought_from_grid: float = 0.0
    spent_to_grid: float = 0.0
    sold_to_grid: float = 0.0
    earned_from_grid: float = 0.0
    self_consumed_savings: float = 0.0
    import_grid_fees: float = 0.0
    export_grid_fees: float = 0.0
    _min_community_savings_percent: float = 0.0
    _max_community_savings_percent: float = 0.0

    def to_dict(self) -> Dict:
        """Dict representation of the area energy bills."""
        output_dict = asdict(self)
        del output_dict["energy_rates"]
        output_dict.update(
            {
                "fees": self.energy_rates.area_fees.prices_as_dict(),
                "savings": self.savings,
                "savings_percent": self.savings_percent,
                "energy_benchmark": self.energy_benchmark,
                "home_balance_kWh": self.home_balance_kWh,
                "home_balance": self.home_balance,
                "gsy_energy_bill_excl_revenue": self.gsy_energy_bill_excl_revenue,
                "gsy_energy_bill_excl_"
                "revenue_without_fees": self.gsy_energy_bill_excl_revenue_without_fees,
                "gsy_energy_bill_excl_fees": self.gsy_energy_bill_excl_fees,
                "gsy_energy_bill_revenue": self.gsy_energy_bill_revenue,
                "gsy_total_benefit": self.gsy_total_benefit,
            }
        )
        return output_dict

    def set_bought_from_community(self, energy_kWh):
        """Update price and energy counters after buying energy from the community."""
        self.bought_from_community += energy_kWh
        self.spent_to_community += energy_kWh * self.energy_rates.intracommunity_rate
        self.gsy_energy_bill += energy_kWh * self.energy_rates.intracommunity_rate
        self.energy_rates.area_fees.add_price_to_fees(energy_kWh)
        self.import_grid_fees += energy_kWh * self.energy_rates.area_fees.decreased_grid_fee

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
        self.import_grid_fees += energy_kWh * self.energy_rates.area_fees.grid_import_fee_const

    def set_sold_to_grid(self, energy_kWh, energy_rate):
        """Update price and energy counters after selling energy to the grid."""
        self.sold_to_grid += energy_kWh
        self.earned_from_grid += energy_kWh * energy_rate
        self.gsy_energy_bill -= energy_kWh * energy_rate

    def set_export_grid_fees(self, energy_kWh: float):
        """Set export grid fees."""
        export_price = energy_kWh * self.energy_rates.area_fees.grid_export_fee_const
        self.export_grid_fees += export_price

    def set_min_max_community_savings(
        self, min_savings_percent: float, max_savings_percent: float
    ):
        """
        Update the minimum and maximum saving of a home in the community.
        Used in order to calculate the energy benchmark.
        """
        self._min_community_savings_percent = min_savings_percent
        self._max_community_savings_percent = max_savings_percent

    @property
    def savings(self):
        """Absolute price savings of the home, compared to the base energy bill."""
        savings_absolute = KPICalculationHelper().saving_absolute(
            self.base_energy_bill_excl_revenue, self.gsy_energy_bill_excl_revenue
        )
        assert savings_absolute > -FLOATING_POINT_TOLERANCE
        return savings_absolute

    @property
    def savings_percent(self):
        """Percentage of the price savings of the home, compared to the base energy bill."""
        return KPICalculationHelper().saving_percentage(
            self.savings, self.base_energy_bill_excl_revenue
        )

    @property
    def energy_benchmark(self):
        """Savings ranking compared to the homes with the min and max savings."""
        return KPICalculationHelper().energy_benchmark(
            self.savings_percent,
            self._min_community_savings_percent,
            self._max_community_savings_percent,
        )

    @property
    def gsy_energy_bill_excl_revenue(self):
        """Energy bill of the home excluding revenue."""
        return self.gsy_energy_bill + self.earned_from_grid + self.earned_from_community

    @property
    def gsy_energy_bill_excl_revenue_without_fees(self):
        """Energy bill of the home excluding revenue and excluding all fees."""
        return (
            self.gsy_energy_bill_excl_revenue
            - self.import_grid_fees
            - self.energy_rates.area_fees.total_per_kWh_fee_price
            - self.energy_rates.area_fees.total_monthly_fee_price
        )

    @property
    def gsy_energy_bill_revenue(self):
        """Total revenue from grid and community."""
        return self.earned_from_grid + self.earned_from_community

    @property
    def gsy_energy_bill_excl_fees(self):
        """Energy bill of the home excluding fees."""
        return (
            self.gsy_energy_bill
            - self.import_grid_fees
            - self.energy_rates.area_fees.total_per_kWh_fee_price
            - self.energy_rates.area_fees.total_monthly_fee_price
        )

    @property
    def gsy_total_benefit(self):
        """Calculate the total savings of the home, minus the monthly fees."""
        return self.savings - self.energy_rates.area_fees.total_monthly_fee_price

    @property
    def home_balance_kWh(self):
        """Energy balance of the home. Equals to energy bought minus energy sold."""
        return (
            self.bought_from_grid
            + self.bought_from_community
            - self.sold_to_grid
            - self.sold_to_community
        )

    @property
    def home_balance(self):
        """Price balance of the home. Equals to currency spent minus currency earned."""
        return (
            self.spent_to_grid
            + self.spent_to_community
            - self.earned_from_grid
            - self.earned_from_community
        )

    def calculate_base_energy_bill(
        self, home_data: HomeAfterMeterData, area_rates: AreaEnergyRates
    ):
        """Calculate the base (not with GSy improvements) energy bill for the home."""
        self.base_energy_bill_revenue = home_data.energy_surplus_kWh * area_rates.feed_in_tariff
        self.base_energy_bill_excl_revenue = (
            home_data.energy_need_kWh * area_rates.utility_rate_incl_fees
            + area_rates.area_fees.total_monthly_fees
        )
        self.base_energy_bill = self.base_energy_bill_excl_revenue - self.base_energy_bill_revenue


class AreaEnergyBillsWithoutSurplusTrade(AreaEnergyBills):
    """Dedicated AreaEnergyBills class, specific for the non-suplus trade SCM."""

    @property
    def savings(self):
        """Absolute price savings of the home, compared to the base energy bill."""
        # The savings and the percentage might produce negative and huge percentage values
        # in cases of production. This is due to the fact that the energy bill in these cases
        # will be negative, and the producer will not have "savings". For a more realistic case
        # the revenue should be omitted from the calculation of the savings, however this needs
        # to be discussed.
        return self.self_consumed_savings + self.gsy_energy_bill_revenue

    def calculate_base_energy_bill(
        self, home_data: HomeAfterMeterData, area_rates: AreaEnergyRates
    ):
        """Calculate the base (not with GSy improvements) energy bill for the home."""

        self.base_energy_bill_excl_revenue = (
            home_data.consumption_kWh * area_rates.utility_rate_incl_fees
            + area_rates.area_fees.total_monthly_fees
        )
        self.base_energy_bill_revenue = 0.0
        self.base_energy_bill = self.base_energy_bill_excl_revenue
