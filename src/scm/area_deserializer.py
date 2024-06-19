from typing import List, Optional, Dict, Union
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime
from collections import defaultdict
from random import random

from scm.scm_dataclasses import FeeProperties


class AreaObject:
    def __init__(
            self, name: str = None, uuid: str = None,
            children: List[Union["AreaObject", "AssetObject"]] = None,
            coefficient_percentage: float = 0.0,
            fee_properties: dict = None,
            market_maker_rate: float = (
                    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE / 100.),
            feed_in_tariff: float = GlobalConfig.FEED_IN_TARIFF / 100.):
        # pylint: disable=too-many-arguments
        self.uuid = uuid
        self.name = name
        self.display_type = "CoefficientArea"
        self.coefficient_percentage = self.validate_coefficient_area_setting(
            coefficient_percentage, "coefficient_percentage")
        self._market_maker_rate = self.validate_coefficient_area_setting(
            market_maker_rate, "market_maker_rate")
        self._feed_in_tariff = self.validate_coefficient_area_setting(
            feed_in_tariff, "feed_in_tariff")
        self.past_market_time_slot = None
        self.fee_properties = FeeProperties()
        self.update_fee_properties(fee_properties)
        self.children = children

    @property
    def is_asset(self):
        return False

    def _is_home_area(self):
        return self.children and all(child.is_asset for child in self.children)

    def update_fee_properties(self, properties: dict) -> None:
        """Update fee_properties."""
        for property_name, fee_dict in properties.items():
            setattr(self.fee_properties, property_name, fee_dict)
        try:
            self.fee_properties.validate()
        except AssertionError as ex:
            raise Exception(f"Invalid fee properties {self.fee_properties}") from ex

    def validate_coefficient_area_setting(
            self, setting: Optional[float], setting_name: str) -> float:
        """Check if coefficient area that is not an asset provided SCM setting."""
        if self._is_home_area() and setting is None:
            raise Exception(f"In SCM simulations {setting_name} can not be None.")
        return setting

    def _calculate_home_after_meter_data(
            self, scm_manager: "SCMManager") -> None:
        home_production_kWh = 0
        home_consumption_kWh = 0

        asset_energy_requirements_kWh = defaultdict(lambda: 0)

        for child in self.children:
            # import
            consumption_kWh = child.consumption_kWh
            asset_energy_requirements_kWh[child.uuid] += consumption_kWh
            home_consumption_kWh += consumption_kWh
            # export
            production_kWh = child.production_kWh
            asset_energy_requirements_kWh[child.uuid] -= production_kWh
            home_production_kWh += production_kWh

        scm_manager.add_home_data(
            self.uuid, self.name, self.coefficient_percentage,
            self._market_maker_rate, self._feed_in_tariff, self.fee_properties,
            home_production_kWh, home_consumption_kWh, dict(asset_energy_requirements_kWh))

    def calculate_home_after_meter_data(
            self, scm_manager: "SCMManager") -> None:
        """Recursive function that calculates the home after meter data."""
        if self._is_home_area():
            self._calculate_home_after_meter_data(scm_manager)
        for child in sorted(self.children, key=lambda _: random()):
            child.calculate_home_after_meter_data(scm_manager)

    def trigger_energy_trades(self, scm_manager: "SCMManager") -> None:
        """Recursive function that triggers energy trading on all children of the root area."""
        if self._is_home_area():
            scm_manager.calculate_home_energy_bills(self.uuid)
        for child in sorted(self.children, key=lambda _: random()):
            child.trigger_energy_trades(scm_manager)

    @property
    def market_maker_rate(self) -> float:
        """Get the market maker rate."""
        return self._market_maker_rate

    def _change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        community_total_energy_need = scm_manager.community_data.energy_need_kWh
        home_energy_need = scm_manager.get_home_energy_need(self.uuid)
        if community_total_energy_need != 0:
            self.coefficient_percentage = home_energy_need / community_total_energy_need

    def change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        """Recursive function that change home coefficient percentage based on energy need.
        This method is for dynamic energy allocation algorithm.
        """
        if self._is_home_area():
            self._change_home_coefficient_percentage(scm_manager)
        for child in self.children:
            child.change_home_coefficient_percentage(scm_manager)


class AssetObject:
    def __init__(self, name, uuid, type, production_kWh, consumption_kWh):
        self.name = name
        self.uuid = uuid
        self.type = type
        self.production_kWh = production_kWh
        self.consumption_kWh = consumption_kWh

    @property
    def is_asset(self):
        return True


class AreaDeserializer:

    def __init__(self, area_dict: dict, energy_values_kWh: dict, fee_properties: dict):
        self._fee_properties = fee_properties
        self._energy_values_kWh = energy_values_kWh
        self._area = self._deserialize_area(area_dict)

    @property
    def root_area(self):
        return self._area

    def _deserialize_area(self, area_dict):
        children = area_dict.pop("children", None)

        if not area_dict.get("type", "Area") == "Area":
            return AssetObject(
                name=area_dict["name"], uuid=area_dict["uuid"], type=area_dict["type"],
                production_kWh=self._energy_values_kWh[area_dict["uuid"]]["production_kWh"],
                consumption_kWh=self._energy_values_kWh[area_dict["uuid"]]["consumption_kWh"])

        deserialized_children = [
            self._deserialize_area(child) for child in children
        ] if children else []

        return AreaObject(
            name=area_dict["name"],
            children=deserialized_children,
            uuid=area_dict["uuid"],
            fee_properties=self._fee_properties.get(area_dict["uuid"], {}),
            coefficient_percentage=area_dict["coefficient_percentage"],
            market_maker_rate=area_dict["market_maker_rate"],
            feed_in_tariff=area_dict["feed_in_tariff"])
