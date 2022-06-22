import logging
from dataclasses import dataclass
from math import isclose
from typing import Dict, TYPE_CHECKING
from uuid import uuid4

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Trade
from pendulum import DateTime

from gsy_e.constants import DEFAULT_SCM_GRID_NAME, DEFAULT_SCM_COMMUNITY_NAME
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
    market_maker_rate: float = 0.
    feed_in_tariff: float = 0.
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh: float = 0.
    energy_surplus_kWh: float = 0.
    energy_need_kWh: float = 0.
    community_production_kWh: float = 0.
    trades = None

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
        if self.trades is None:
            self.trades = []

    def set_community_production(self, energy_kWh: float):
        """
        Set the community energy production, in order to correctly generate the community-related
        home data.
        """
        self.community_production_kWh = energy_kWh

    @property
    def allocated_community_energy_kWh(self) -> float:
        """Amount of community energy allocated to the home."""
        return self.community_production_kWh * self.sharing_coefficient_percent

    @property
    def energy_bought_from_community_kWh(self) -> float:
        """Amount of energy bought by the home from the community."""
        return min(self.allocated_community_energy_kWh, self.energy_need_kWh)

    @property
    def energy_sold_to_grid_kWh(self) -> float:
        """Amount of energy sold by the home to the grid."""
        return (
            self.allocated_community_energy_kWh - self.energy_need_kWh
            if self.allocated_community_energy_kWh > self.energy_need_kWh
            else 0.0)

    def create_buy_trade(self, current_time_slot: DateTime, seller_name: str,
                         traded_energy_kWh: float, trade_price_cents: float) -> None:
        """Create and save a trade object for buying energy."""
        trade = Trade(
            str(uuid4()), current_time_slot, None,
            seller_name, self.home_name,
            traded_energy=traded_energy_kWh, trade_price=trade_price_cents, residual=None,
            offer_bid_trade_info=None,
            seller_origin=seller_name,
            buyer_origin=self.home_name, fee_price=0., buyer_origin_id=self.home_uuid,
            seller_origin_id=None, seller_id=None, buyer_id=self.home_uuid,
            time_slot=current_time_slot)
        self.trades.append(trade)
        logging.info("[SCM][TRADE][BID] [%s] [%s] %s", self.home_name, trade.time_slot, trade)

    def create_sell_trade(self, current_time_slot: DateTime, buyer_name: str,
                          traded_energy_kWh: float, trade_price_cents: float):
        """Create and save a trade object for selling energy."""
        trade = Trade(
            str(uuid4()), current_time_slot, None,
            self.home_name, buyer_name,
            traded_energy=traded_energy_kWh, trade_price=trade_price_cents, residual=None,
            offer_bid_trade_info=None,
            seller_origin=self.home_name,
            buyer_origin=buyer_name, fee_price=0., buyer_origin_id=None,
            seller_origin_id=self.home_uuid, seller_id=self.home_uuid, buyer_id=None,
            time_slot=current_time_slot)
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


@dataclass
class HomeEnergyBills:
    """Represents home energy bills."""
    base_energy_bill: float = 0.
    gsy_energy_bill: float = 0.
    savings: float = 0.
    savings_percent: float = 0.


class SCMManager:
    """Handle the community manager coefficient trade."""
    def __init__(self, area: "CoefficientArea", time_slot: DateTime):
        self._validate_community(area)
        self._home_data: Dict[str, HomeAfterMeterData] = {}
        # Community is always the root area in the context of SCM.
        self._community_uuid = area.uuid
        self.community_data = CommunityData(self._community_uuid)
        self._time_slot = time_slot
        self._bills: Dict[str, HomeEnergyBills] = {}
        self._grid_fees_reduction = ConstSettings.SCMSettings.GRID_FEES_REDUCTION

    @staticmethod
    def _validate_community(community_area: "CoefficientArea") -> None:
        assert isclose(
            sum(home.coefficient_percent for home in community_area.children), 1.0
        ), "Coefficients from all homes should sum up to 1."
        for home in community_area.children:
            assert all(isinstance(asset.strategy, SCMStrategy) for asset in home.children), \
                f"Home {home.name} has assets with non-SCM strategies."

    def add_home_data(self, home_uuid: str, home_name: str,
                      grid_fees: float, coefficient_percent: float,
                      market_maker_rate: float, feed_in_tariff: float,
                      production_kWh: float, consumption_kWh: float):
        # pylint: disable=too-many-arguments
        """Import data for one individual home."""
        if grid_fees is None:
            grid_fees = 0.0
        self._home_data[home_uuid] = HomeAfterMeterData(
            home_uuid, home_name,
            grid_fees=grid_fees,
            sharing_coefficient_percent=coefficient_percent,
            market_maker_rate=market_maker_rate,
            feed_in_tariff=feed_in_tariff,
            production_kWh=production_kWh, consumption_kWh=consumption_kWh)

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
            home_data.set_community_production(self.community_data.energy_surplus_kWh)

        for data in self._home_data.values():
            self.community_data.energy_bought_from_community_kWh += (
                data.energy_bought_from_community_kWh)
            self.community_data.energy_sold_to_grid_kWh += data.energy_sold_to_grid_kWh

    def calculate_home_energy_bills(
            self, home_uuid: str) -> None:
        """Calculate energy bills for one home."""
        assert home_uuid in self._home_data

        home_data = self._home_data[home_uuid]

        market_maker_rate = home_data.market_maker_rate
        grid_fees = home_data.grid_fees
        feed_in_tariff = home_data.feed_in_tariff

        market_maker_rate_decreased_fees = (
                market_maker_rate + grid_fees * self._grid_fees_reduction)
        market_maker_rate_normal_fees = market_maker_rate + grid_fees

        base_energy_bill = (
                home_data.energy_need_kWh * market_maker_rate_normal_fees -
                home_data.energy_surplus_kWh * feed_in_tariff)

        if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
            if home_data.energy_surplus_kWh > 0.0:
                gsy_energy_bill = -(
                    home_data.energy_bought_from_community_kWh * market_maker_rate_decreased_fees +
                    self.community_data.energy_sold_to_grid_kWh * feed_in_tariff)

                if home_data.energy_bought_from_community_kWh > 0.:
                    home_data.create_buy_trade(
                        self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                        home_data.energy_bought_from_community_kWh,
                        (home_data.energy_bought_from_community_kWh *
                         market_maker_rate_decreased_fees)
                    )
                if self.community_data.energy_sold_to_grid_kWh > 0.:
                    home_data.create_sell_trade(
                        self._time_slot, DEFAULT_SCM_GRID_NAME,
                        self.community_data.energy_sold_to_grid_kWh,
                        self.community_data.energy_sold_to_grid_kWh * feed_in_tariff)
            else:
                gsy_energy_bill = home_data.energy_need_kWh * market_maker_rate_decreased_fees
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME, home_data.energy_need_kWh,
                    home_data.energy_need_kWh * market_maker_rate_decreased_fees
                )
        else:
            gsy_energy_bill = (
                    home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees +
                    (home_data.energy_need_kWh - home_data.allocated_community_energy_kWh) *
                    market_maker_rate_normal_fees)
            if home_data.allocated_community_energy_kWh > 0.0:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_COMMUNITY_NAME,
                    home_data.allocated_community_energy_kWh,
                    home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees
                )

            energy_from_grid_kWh = (
                    home_data.energy_need_kWh - home_data.allocated_community_energy_kWh)
            if energy_from_grid_kWh > 0.:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_GRID_NAME,
                    energy_from_grid_kWh,
                    energy_from_grid_kWh * market_maker_rate_decreased_fees
                )

        savings_percent = (
                ((base_energy_bill - gsy_energy_bill) / base_energy_bill) * 100.0
                if base_energy_bill else 0.
        )

        self._bills[home_uuid] = HomeEnergyBills(
            base_energy_bill=base_energy_bill,
            gsy_energy_bill=gsy_energy_bill,
            savings=(base_energy_bill - gsy_energy_bill),
            savings_percent=savings_percent)

    @property
    def community_bills(self):
        """Calculate bills for the community."""
        home_bills = HomeEnergyBills()
        for data in self._bills.values():
            home_bills.base_energy_bill += data.base_energy_bill
            home_bills.gsy_energy_bill += data.gsy_energy_bill
            home_bills.savings += data.savings
            home_bills.savings_percent += data.savings_percent
        return home_bills
