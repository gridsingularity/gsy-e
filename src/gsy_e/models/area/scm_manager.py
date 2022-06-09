from typing import Dict
from dataclasses import dataclass
from gsy_framework.constants_limits import GlobalConfig


@dataclass
class HomeAfterMeterData:
    home_uuid: str
    sharing_coefficient_percent: float = 0.
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh: float = 0.
    energy_surplus_kWh: float = 0.
    energy_need_kWh: float = 0.
    community_production_kWh: float = 0.

    def __post_init__(self):
        self.self_consumed_energy_kWh = min(self.consumption_kWh, self.production_kWh)
        self.energy_surplus_kWh = self.production_kWh - self.self_consumed_energy_kWh
        self.energy_need_kWh = self.consumption_kWh - self.self_consumed_energy_kWh

    def set_community_production(self, energy_kWh: float):
        self.community_production_kWh = energy_kWh

    @property
    def allocated_community_energy_kWh(self) -> float:
        return self.community_production_kWh * self.sharing_coefficient_percent

    @property
    def energy_bought_from_community_kWh(self) -> float:
        return min(self.allocated_community_energy_kWh, self.energy_need_kWh)

    @property
    def energy_sold_to_grid_kWh(self) -> float:
        return (
            self.allocated_community_energy_kWh - self.energy_need_kWh
            if self.allocated_community_energy_kWh > self.energy_need_kWh
            else 0.0)


@dataclass
class CommunityData:
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
    base_energy_bill: float
    gsy_energy_bill: float
    savings_euro: float
    savings_percent: float


class SCMManager:

    def __init__(self, community_uuid: str):
        self._home_data: Dict[str, HomeAfterMeterData] = {}
        self.community_data = CommunityData(community_uuid)
        self._bills: Dict[str, HomeEnergyBills] = {}
        self._community_bills = HomeEnergyBills()
        self._market_maker_rate = GlobalConfig.MARKET_MAKER_RATE
        self._feed_in_tariff = 0.1
        self._grid_fees_reduction = 0.28

    def add_home_data(self, home_uuid: str, production_kWh: float, consumption_kWh: float):
        self._home_data[home_uuid] = HomeAfterMeterData(
            home_uuid, production_kWh=production_kWh, consumption_kWh=consumption_kWh)

    def calculate_community_after_meter_data(self):
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
            self, home_uuid: str, grid_fees: float) -> None:
        if home_uuid not in self._home_data:
            return
        home_data = self._home_data[home_uuid]

        market_maker_rate_decreased_fees = (
                self._market_maker_rate + grid_fees * self._grid_fees_reduction)
        market_maker_rate_normal_fees = self._market_maker_rate + grid_fees

        base_energy_bill = (
                home_data.energy_need_kWh * market_maker_rate_normal_fees -
                home_data.energy_surplus_kWh * self._feed_in_tariff)

        if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
            if home_data.energy_surplus_kWh > 0.0:
                # I followed the excel sheet but this looks like it is not correct.
                # We use the community data in order to calculate the gsy bill for the house
                # which does not look right in my eyes
                gsy_energy_bill = -(
                    (self.community_data.energy_bought_from_community_kWh -
                     home_data.energy_bought_from_community_kWh
                     ) * market_maker_rate_decreased_fees +
                    self.community_data.energy_sold_to_grid_kWh * self._feed_in_tariff)
            else:
                gsy_energy_bill = home_data.energy_need_kWh * market_maker_rate_decreased_fees
        else:
            gsy_energy_bill = (
                    home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees +
                    (home_data.energy_need_kWh - home_data.allocated_community_energy_kWh) *
                    market_maker_rate_normal_fees)

        # if home_data.allocated_community_energy_kWh > home_data.energy_need_kWh:
        #     gsy_energy_bill = (
        #         (home_data.energy_need_kWh -
        #          home_data.energy_surplus_kWh) * market_maker_rate_decreased_fees)
        # else:
        #     gsy_energy_bill = (
        #         home_data.allocated_community_energy_kWh * market_maker_rate_decreased_fees
        #         + (home_data.energy_need_kWh -
        #            home_data.allocated_community_energy_kWh) * market_maker_rate_normal_fees)

        self._bills[home_uuid] = HomeEnergyBills(
            base_energy_bill=base_energy_bill,
            gsy_energy_bill=gsy_energy_bill,
            savings_euro=(base_energy_bill - gsy_energy_bill),
            savings_percent=((base_energy_bill - gsy_energy_bill) / base_energy_bill) * 100.0)

    def calculate_community_bills(self):
        self._community_bills.base_energy_bill = sum(
            data.base_energy_bill for data in self._bills.values())
        self._community_bills.gsy_energy_bill = sum(
            data.gsy_energy_bill for data in self._bills.values())
        self._community_bills.savings_euro = sum(
            data.savings_euro for data in self._bills.values())
        self._community_bills.savings_percent = sum(
            data.savings_percent for data in self._bills.values())
