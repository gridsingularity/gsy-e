import logging
from dataclasses import dataclass, asdict
from typing import Dict
from uuid import uuid4

from gsy_framework.data_classes import Trade
from pendulum import DateTime

from gsy_e.constants import DEFAULT_GRID_SELLER_STRING, DEFAULT_SCM_SELLER_STRING


@dataclass
class HomeAfterMeterData:
    # pylint: disable=too-many-instance-attributes
    """Represent all the after meter data for a single home area."""
    home_uuid: str
    home_name: str
    sharing_coefficient_percent: float = 0.
    grid_fees_eur: float = 0.
    market_maker_rate_eur: float = 0.
    feed_in_tariff_eur: float = 0.
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh: float = 0.
    energy_surplus_kWh: float = 0.
    energy_need_kWh: float = 0.
    community_production_kWh: float = 0.
    trades = None

    def to_dict(self) -> Dict:
        output_dict = asdict(self)
        output_dict.update({
            "allocated_community_energy_kWh": self.allocated_community_energy_kWh,
            "energy_bought_from_community_kWh": self.energy_bought_from_community_kWh,
            "energy_sold_to_grid_kWh": self.energy_sold_to_grid_kWh
        })
        return output_dict

    def __post_init__(self):
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

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AreaEnergyBills:
    """Represents home energy bills."""
    base_energy_bill: float = 0.
    gsy_energy_bill: float = 0.
    bought_from_community: float = 0.
    spent_to_community: float = 0.
    bought_from_grid: float = 0.
    spent_to_grid: float = 0.
    sold_to_grid: float = 0.
    earned_from_grid: float = 0.

    def to_dict(self) -> Dict:
        output_dict = asdict(self)
        output_dict.update({
            "savings_eur": self.savings_eur,
            "savings_percent": self.savings_percent,
            "home_balance_kWh": self.home_balance_kWh,
            "home_balance_eur": self.home_balance_eur
        })
        return output_dict

    def set_bought_from_community(self, energy_kWh, energy_rate):
        self.bought_from_community += energy_kWh
        self.spent_to_community += energy_kWh * energy_rate
        self.gsy_energy_bill += energy_kWh * energy_rate

    def set_bought_from_grid(self, energy_kWh, energy_rate):
        self.bought_from_grid += energy_kWh
        self.spent_to_grid += energy_kWh * energy_rate
        self.gsy_energy_bill += energy_kWh * energy_rate

    def set_sold_to_grid(self, energy_kWh, energy_rate):
        self.sold_to_grid += energy_kWh
        self.earned_from_grid += energy_kWh * energy_rate
        self.gsy_energy_bill -= energy_kWh * energy_rate

    @property
    def savings_eur(self):
        return self.base_energy_bill - self.gsy_energy_bill

    @property
    def savings_percent(self):
        return (
            ((self.base_energy_bill - self.gsy_energy_bill) / self.base_energy_bill) * 100.0
            if self.base_energy_bill else 0.)

    @property
    def home_balance_kWh(self):
        return self.bought_from_grid + self.bought_from_community - self.sold_to_grid

    @property
    def home_balance_eur(self):
        return self.spent_to_grid + self.spent_to_community - self.earned_from_grid


class SCMManager:
    """Handle the community manager coefficient trade."""
    def __init__(self, community_uuid: str, time_slot: DateTime):
        self._home_data: Dict[str, HomeAfterMeterData] = {}
        self.community_data = CommunityData(community_uuid)
        self._time_slot = time_slot
        self._bills: Dict[str, AreaEnergyBills] = {}
        self._grid_fees_reduction = 0.28
        self._community_uuid = community_uuid

    def add_home_data(self, home_uuid: str, home_name: str,
                      grid_fees_eur: float, coefficient_percent: float,
                      market_maker_rate_eur: float, feed_in_tariff_eur: float,
                      production_kWh: float, consumption_kWh: float):
        # pylint: disable=too-many-arguments
        """Import data for one individual home."""
        if grid_fees_eur is None:
            grid_fees_eur = 0.0
        self._home_data[home_uuid] = HomeAfterMeterData(
            home_uuid, home_name,
            grid_fees_eur=grid_fees_eur,
            sharing_coefficient_percent=coefficient_percent,
            market_maker_rate_eur=market_maker_rate_eur,
            feed_in_tariff_eur=feed_in_tariff_eur,
            production_kWh=production_kWh, consumption_kWh=consumption_kWh)

    def calculate_community_after_meter_data(self):
        """Calculate community data by aggregating all single home data."""
        self.community_data.production_kWh = sum(
            data.production_kWh for data in self._home_data.values())
        self.community_data.consumption_kWh = sum(
            data.consumption_kWh for data in self._home_data.values())
        self.community_data.self_consumed_energy_kWh = sum(
            data.self_consumed_energy_kWh for data in self._home_data.values())
        self.community_data.energy_surplus_kWh = sum(
            data.energy_surplus_kWh for data in self._home_data.values())
        self.community_data.energy_need_kWh = sum(
            data.energy_need_kWh for data in self._home_data.values())

        for home_data in self._home_data.values():
            home_data.set_community_production(self.community_data.energy_surplus_kWh)

        self.community_data.energy_bought_from_community_kWh = sum(
            data.energy_bought_from_community_kWh for data in self._home_data.values())
        self.community_data.energy_sold_to_grid_kWh = sum(
            data.energy_sold_to_grid_kWh for data in self._home_data.values())

    def calculate_home_energy_bills(
            self, home_uuid: str) -> None:
        """Calculate energy bills for one home."""
        assert home_uuid in self._home_data

        home_data = self._home_data[home_uuid]

        market_maker_rate_eur = home_data.market_maker_rate_eur
        grid_fees_eur = home_data.grid_fees_eur
        feed_in_tariff_eur = home_data.feed_in_tariff_eur

        market_maker_rate_decreased_fees = (
                market_maker_rate_eur + grid_fees_eur * self._grid_fees_reduction)
        market_maker_rate_normal_fees = market_maker_rate_eur + grid_fees_eur

        home_bill = AreaEnergyBills()

        base_energy_bill = (
                home_data.energy_need_kWh * market_maker_rate_normal_fees -
                home_data.energy_surplus_kWh * feed_in_tariff_eur)
        home_bill.base_energy_bill = base_energy_bill

        if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
            if home_data.energy_surplus_kWh > 0.0:
                bought_from_community_kWh = (
                    self.community_data.energy_bought_from_community_kWh -
                    home_data.energy_bought_from_community_kWh)

                home_bill.set_bought_from_community(
                    bought_from_community_kWh, market_maker_rate_decreased_fees)
                home_bill.set_sold_to_grid(
                    self.community_data.energy_sold_to_grid_kWh, feed_in_tariff_eur)

                if bought_from_community_kWh > 0.:
                    home_data.create_buy_trade(
                        self._time_slot, DEFAULT_SCM_SELLER_STRING, bought_from_community_kWh,
                        bought_from_community_kWh * market_maker_rate_decreased_fees
                    )
                if self.community_data.energy_sold_to_grid_kWh > 0.:
                    home_data.create_sell_trade(
                        self._time_slot, DEFAULT_GRID_SELLER_STRING,
                        self.community_data.energy_sold_to_grid_kWh,
                        self.community_data.energy_sold_to_grid_kWh * feed_in_tariff_eur)
            else:
                home_bill.set_bought_from_community(
                    home_data.energy_need_kWh, market_maker_rate_decreased_fees)
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_SELLER_STRING, home_data.energy_need_kWh,
                    home_data.energy_need_kWh * market_maker_rate_decreased_fees
                )
        else:
            home_bill.set_bought_from_community(
                home_data.allocated_community_energy_kWh, market_maker_rate_decreased_fees)

            energy_from_grid_kWh = (
                    home_data.energy_need_kWh - home_data.allocated_community_energy_kWh)
            home_bill.set_bought_from_grid(energy_from_grid_kWh, market_maker_rate_normal_fees)

            if home_data.allocated_community_energy_kWh > 0.0:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_SCM_SELLER_STRING,
                    home_data.allocated_community_energy_kWh,
                    home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees
                )

            if energy_from_grid_kWh > 0.:
                home_data.create_buy_trade(
                    self._time_slot, DEFAULT_GRID_SELLER_STRING,
                    energy_from_grid_kWh,
                    energy_from_grid_kWh * market_maker_rate_normal_fees
                )

        self._bills[home_uuid] = home_bill

    def get_area_results(self, area_uuid):
        if area_uuid == self._community_uuid:
            return {
                "bills": self.community_bills,
                "after_meter_data": {}
            }

        if area_uuid not in self._bills:
            return {"bills": {}, "after_meter_data": {}}
        return {
            "bills": self._bills[area_uuid].to_dict(),
            "after_meter_data": self._home_data[area_uuid].to_dict()
        }

    @property
    def community_bills(self):
        """Calculate bills for the community."""
        member_to_sum = ["base_energy_bill", "gsy_energy_bill", "bought_from_community",
                         "spent_to_community", "bought_from_grid", "spent_to_grid",
                         "sold_to_grid", "earned_from_grid"]

        community_bills = AreaEnergyBills()
        for member in member_to_sum:
            setattr(community_bills, member,
                    sum(getattr(home_bill, member) for home_bill in self._bills.values()))

        return asdict(community_bills)
