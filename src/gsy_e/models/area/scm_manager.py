from dataclasses import dataclass


@dataclass
class HomeAfterMeterData:
    home_uuid: str
    sharing_coefficient_percent = 0.
    consumption_kWh: float = 0.
    production_kWh: float = 0.
    self_consumed_energy_kWh = 0.
    energy_surplus_kWh = 0.
    energy_need_kWh = 0.
    community_production_kWh = 0.

    def __post_init__(self):
        self.self_consumed_energy_kWh = min(self.consumption_kWh, self.production_kWh)
        self.energy_surplus_kWh = self.production_kWh - self.self_consumed_energy_kWh
        self.energy_need_kWh = self.consumption_kWh - self.self_consumed_energy_kWh

    def set_community_production(self, energy_kWh):
        self.community_production_kWh = energy_kWh

    @property
    def allocated_community_energy_kWh(self):
        return self.community_production_kWh * self.sharing_coefficient_percent


class SCMManager:

    def __init__(self, community_uuid):
        self._home_data = {}
        self.community_data = HomeAfterMeterData(community_uuid)

    def add_home_data(self, home_uuid, production_kWh, consumption_kWh):
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
