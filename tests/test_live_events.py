import unittest
from pendulum import duration
import json
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.area import Area
from d3a.models.config import SimulationConfig
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.d3a_core.live_events import LiveEvents


class TestLiveEvents(unittest.TestCase):

    def setUp(self):

        self.config = SimulationConfig(
            sim_duration=duration(hours=12),
            slot_length=duration(minutes=15),
            tick_length=duration(seconds=15),
            market_count=1,
            cloud_coverage=0
        )

        self.live_events = LiveEvents(self.config)
        self.strategy_load = LoadHoursStrategy(
            avg_power_W=123, hrs_per_day=3, hrs_of_day=[2, 3, 4, 5], fit_to_limit=False,
            energy_rate_increase_per_update=2, update_interval=5, initial_buying_rate=11,
            final_buying_rate=31)
        self.strategy_pv = PVStrategy(
            panel_count=3, initial_selling_rate=34, final_selling_rate=12,
            fit_to_limit=False, update_interval=6, energy_rate_decrease_per_update=4,
            max_panel_power_W=432)
        self.strategy_battery = StorageStrategy(
            initial_soc=11, min_allowed_soc=10, battery_capacity_kWh=6,
            max_abs_battery_power_kW=123, cap_price_strategy=False, initial_selling_rate=32,
            final_selling_rate=20, initial_buying_rate=10, final_buying_rate=19,
            fit_to_limit=False, energy_rate_increase_per_update=5,
            energy_rate_decrease_per_update=8, update_interval=9
        )
        self.area1 = Area("load", None, None, self.strategy_load, SwitchableAppliance(),
                          self.config, None, grid_fee_percentage=0)
        self.area2 = Area("pv", None, None, self.strategy_pv, PVAppliance(),
                          self.config, None, grid_fee_percentage=0)
        self.area3 = Area("storage", None, None, self.strategy_battery, SwitchableAppliance(),
                          self.config, None, grid_fee_percentage=0)
        self.area_house1 = Area("House 1", children=[self.area1, self.area2], config=self.config)
        self.area_house2 = Area("House 2", children=[self.area3], config=self.config)
        self.area_grid = Area("Grid", children=[self.area_house1, self.area_house2],
                              config=self.config)

    def test_create_area_event_is_creating_a_new_area(self):
        event_string = json.dumps({
            "eventType": "create_area",
            "parent_uuid": self.area_house1.uuid,
            "area_representation": {
                "type": "LoadHours", "name": "new_load", "avg_power_W": 234}
        })

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)

        new_load = [c for c in self.area_house1.children if c.name == "new_load"][0]
        assert type(new_load.strategy) == LoadHoursStrategy
        assert new_load.strategy.avg_power_W == 234

    def test_delete_area_event_is_deleting_an_area(self):
        event_string = json.dumps({
            "eventType": "delete_area",
            "area_uuid": self.area1.uuid
        })

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)

        assert len(self.area_house1.children) == 1
        assert all(c.uuid != self.area1.uuid for c in self.area_house1.children)

    def test_update_area_event_is_updating_the_parameters_of_a_load(self):
        event_string = json.dumps({
            "eventType": "update_area",
            "area_uuid": self.area1.uuid,
            "area_representation": {
                "avg_power_W": 234, "hrs_per_day": 6, "hrs_of_day": [0, 1, 2, 3, 4, 5, 6, 7],
                "energy_rate_increase_per_update": 3, "update_interval": 9,
                "initial_buying_rate": 12
            }
        })

        self.area_grid.activate()

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)
        assert self.area1.strategy.avg_power_W == 234
        assert self.area1.strategy.hrs_per_day[0] == 6
        assert self.area1.strategy.hrs_of_day == [0, 1, 2, 3, 4, 5, 6, 7]
        assert set(self.area1.strategy.bid_update.energy_rate_change_per_update.values()) == {3}
        assert self.area1.strategy.bid_update.update_interval.minutes == 9
        assert set(self.area1.strategy.bid_update.initial_rate.values()) == {12}

    def test_update_area_event_is_updating_the_parameters_of_a_pv(self):
        event_string = json.dumps({
            "eventType": "update_area",
            "area_uuid": self.area2.uuid,
            "area_representation": {
                "panel_count": 12, "initial_selling_rate": 68, "final_selling_rate": 42,
                "fit_to_limit": True, "update_interval": 12, "max_panel_power_W": 999
            }
        })

        self.area_grid.activate()

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)
        assert self.area2.strategy.panel_count == 12
        assert set(self.area2.strategy.offer_update.initial_rate.values()) == {68}
        assert set(self.area2.strategy.offer_update.final_rate.values()) == {42}
        assert self.area2.strategy.offer_update.fit_to_limit is True
        assert self.area2.strategy.offer_update.update_interval.minutes == 12
        assert self.area2.strategy.max_panel_power_W == 999

    def test_update_area_event_is_updating_the_parameters_of_a_storage(self):
        event_string = json.dumps({
            "eventType": "update_area",
            "area_uuid": self.area3.uuid,
            "area_representation": {
                "cap_price_strategy": True, "initial_selling_rate": 123,
                "final_selling_rate": 120, "initial_buying_rate": 2, "final_buying_rate": 101,
                "energy_rate_increase_per_update": 4, "energy_rate_decrease_per_update": 13,
                "update_interval": 14
            }
        })

        self.area_grid.activate()

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)
        assert self.area3.strategy.cap_price_strategy is False
        assert set(self.area3.strategy.offer_update.initial_rate.values()) == {123}
        assert set(self.area3.strategy.offer_update.final_rate.values()) == {120}
        assert set(self.area3.strategy.offer_update.energy_rate_change_per_update.values()) == {13}
        assert set(self.area3.strategy.bid_update.initial_rate.values()) == {2}
        assert set(self.area3.strategy.bid_update.final_rate.values()) == {101}
        assert set(self.area3.strategy.bid_update.energy_rate_change_per_update.values()) == {-4}
        assert self.area3.strategy.offer_update.update_interval.minutes == 14
        assert self.area3.strategy.bid_update.update_interval.minutes == 14

    def test_update_area_event_is_updating_the_parameters_of_an_area(self):
        event_string = json.dumps({
            "eventType": "update_area",
            "area_uuid": self.area_house1.uuid,
            "area_representation": {
                'transfer_fee_const': 12, 'baseline_peak_energy_import_kWh': 123,
                'baseline_peak_energy_export_kWh': 456, 'import_capacity_kVA': 987,
                'export_capacity_kVA': 765
            }
        })

        self.area_grid.activate()

        self.live_events.add_event(event_string)
        self.live_events.handle_all_events(self.area_grid)
        assert self.area_house1.transfer_fee_const == 12
        assert self.area_house1.baseline_peak_energy_import_kWh == 123
        assert self.area_house1.baseline_peak_energy_export_kWh == 456
        assert self.area_house1.import_capacity_kWh == \
            987 * self.config.slot_length.total_minutes() / 60.0
        assert self.area_house1.export_capacity_kWh == \
            765 * self.config.slot_length.total_minutes() / 60.0
