from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.read_user_profile import read_arbitrary_profile
from d3a.models.strategy.read_user_profile import InputProfileTypes
from d3a import TIME_FORMAT


class ElectrolyzerStrategy(StorageStrategy):

    def __init__(self, discharge_profile,
                 conversion_factor_kg_to_kWh: float=50.0,
                 reservoir_capacity_kg: float=56.0,
                 reservoir_initial_capacity_kg: float= 5.6,
                 production_rate_kg_h: float=1.0):

        initial_capacity_kWh = reservoir_initial_capacity_kg * conversion_factor_kg_to_kWh
        capacity_kWh = reservoir_capacity_kg * conversion_factor_kg_to_kWh
        production_rate_kW = production_rate_kg_h * conversion_factor_kg_to_kWh

        super().__init__(0, initial_capacity_kWh=initial_capacity_kWh,
                         battery_capacity_kWh=capacity_kWh,
                         max_abs_battery_power_kW=production_rate_kW,
                         min_allowed_soc=0.,
                         break_even=(31, 32))

        self.discharge_profile = discharge_profile
        self.conversion_factor_kWh_kg = conversion_factor_kg_to_kWh
        self.load_profile_kWh = {}

    def event_activate(self):
        super().event_activate()

        load_profile_raw = read_arbitrary_profile(
            InputProfileTypes.IDENTITY,
            self.discharge_profile,
            slot_length=self.area.config.slot_length)

        for key, value in load_profile_raw.items():
            self.load_profile_kWh[key] = value * self.conversion_factor_kWh_kg

    def event_market_cycle(self):
        self.update_market_cycle_offers(self.break_even[self.area.now.strftime(TIME_FORMAT)][1])
        current_market = self.area.next_market
        if self.area.past_markets:
            past_market = self.area.last_past_market
            self.state.market_cycle(past_market.time_slot, current_market.time_slot)

        if (self.state.used_storage - self.load_profile_kWh[current_market.time_slot_str]) >= 0:
            self.state._used_storage -= self.load_profile_kWh[current_market.time_slot_str]
        else:
            requested_h2_kg = self.load_profile_kWh[current_market.time_slot_str] / \
                              self.conversion_factor_kWh_kg
            raise Exception(f"[{current_market.time_slot}]The Electrolyzer storage is not charged "
                            f"properly. The costumer requested {requested_h2_kg} kg but only "
                            f"{self.state.used_storage/self.conversion_factor_kWh_kg} kg "
                            f"are available")
