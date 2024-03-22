# pylint: disable=unused-wildcard-import,unused-import
"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import json
from logging import getLogger

from gsy_framework.utils import convert_pendulum_to_str_in_dict, key_in_dict_and_not_none
from gsy_framework.constants_limits import ConstSettings, SpotMarketTypeEnum, GlobalConfig
from pendulum import Duration

from gsy_e.models.area import CoefficientArea, Area, Market, Asset # NOQA
from gsy_e.models.strategy import BaseStrategy
from gsy_e.models.area.throughput_parameters import ThroughputParameters

from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy  # NOQA
from gsy_e.models.strategy.commercial_producer import CommercialStrategy  # NOQA
from gsy_e.models.strategy.pv import PVStrategy  # NOQA
from gsy_e.models.strategy.storage import StorageStrategy  # NOQA
from gsy_e.models.strategy.load_hours import LoadHoursStrategy # NOQA
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy # NOQA
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy  # NOQA
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant # NOQA
from gsy_e.models.strategy.scm import SCMStrategy

from gsy_e.models.leaves import (
    Leaf, scm_leaf_mapping, CoefficientLeaf, forward_leaf_mapping) # NOQA
from gsy_e.models.leaves import *  # NOQA  # pylint: disable=wildcard-import
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

logger = getLogger(__name__)


class AreaEncoder(json.JSONEncoder):
    """Convert the Area class hierarchy to json dict."""
    def default(self, o):
        # Leaf classes are Areas too, therefore the Area/AreaBase classes need to be handled
        # separately.
        if type(o) in [Area, CoefficientArea, Market, Asset]:
            return self._encode_area(o)
        if isinstance(o, Leaf):
            return self._encode_leaf(o)
        if isinstance(o, (BaseStrategy, SCMStrategy)):
            return self._encode_subobject(o)
        if isinstance(o, TradingStrategyBase):
            return self._encode_subobject(o)
        if isinstance(o, Duration):
            return o.seconds
        return super().default(o)

    @staticmethod
    def _encode_area(area):
        result = {"name": area.name}
        if area.children:
            result["children"] = area.children
        if area.uuid:
            result["uuid"] = area.uuid
        if area.strategy:
            result["strategy"] = area.strategy
        if area.display_type:
            result["display_type"] = area.display_type
        return result

    @staticmethod
    def _encode_subobject(obj):
        result = {"type": obj.__class__.__name__}
        kwargs = obj.serialize()
        if kwargs:
            kwargs = _convert_member_dt_to_string(kwargs)
            result["kwargs"] = kwargs
        return result

    @staticmethod
    def _encode_leaf(obj):
        description = {"name": obj.name,
                       "type": obj.__class__.__name__,
                       "display_type": obj.display_type}
        description.update(obj.parameters)
        description = _convert_member_dt_to_string(description)
        return description


def _convert_member_dt_to_string(in_dict):
    """
    Converts Datetime keys of members of in_dict into strings
    """
    for key, value in in_dict.items():
        if isinstance(value, dict):
            outdict = {}
            convert_pendulum_to_str_in_dict(value, outdict)
            in_dict[key] = outdict
    return in_dict


def area_to_string(area):
    """Create a json string representation of an Area"""
    return json.dumps(area, cls=AreaEncoder)


def _instance_from_dict(description):
    try:
        return globals()[description["type"]](**description.get("kwargs", {}))
    except Exception as exception:
        if "type" in description and isinstance(exception, KeyError):
            raise ValueError(f"Unknown class {description['type']}") from exception
        raise exception


def _leaf_from_dict(description, config):
    if ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
        strategy_type = description.pop("type")
        leaf_type = forward_leaf_mapping.get(strategy_type)
        if not leaf_type:
            return None
        if not issubclass(leaf_type, Leaf):
            raise ValueError(f"Unknown forward leaf type '{leaf_type}'")
    elif ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
        strategy_type = description.pop("type")
        leaf_type = scm_leaf_mapping.get(strategy_type)
        if not leaf_type:
            return None
        if not issubclass(leaf_type, CoefficientLeaf):
            raise ValueError(f"Unknown coefficient leaf type '{leaf_type}'")
    else:
        leaf_type = globals().get(description.pop("type"), type(None))
        if not issubclass(leaf_type, Leaf):
            raise ValueError(f"Unknown leaf type '{leaf_type}'")
    description = leaf_type.strategy_type.deserialize_args(description)
    display_type = description.pop("display_type", None)
    try:
        leaf_object = leaf_type(**description, config=config)
    except KeyError as exc:
        # If the strategy is not supported in SCM or normal operating mode, do
        # not create the area at all.
        logger.error("Failed to create leaf %s %s %s", leaf_type, description, exc)
        return None
    if display_type is not None:
        leaf_object.display_type = display_type
    return leaf_object


def area_from_dict(description, config):
    """Create Area tree from JSON dict."""
    def optional(attr):
        return _instance_from_dict(description[attr]) if attr in description else None
    try:
        if "type" in description:
            return _leaf_from_dict(description, config)  # Area is a Leaf
        name = description["name"]
        uuid = description.get("uuid", None)
        external_connection_available = description.get("allow_external_connection", False)
        baseline_peak_energy_import_kWh = description.get("baseline_peak_energy_import_kWh", None)
        baseline_peak_energy_export_kWh = description.get("baseline_peak_energy_export_kWh", None)
        import_capacity_kVA = description.get("import_capacity_kVA", None)
        export_capacity_kVA = description.get("export_capacity_kVA", None)
        if key_in_dict_and_not_none(description, "children"):
            children = [area_from_dict(child, config) for child in description["children"]]
        else:
            children = None

        grid_fee_percentage = description.get("grid_fee_percentage", None)
        grid_fee_constant = description.get("grid_fee_constant", None)

        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            # For the SCM only use the CoefficientArea strategy.
            grid_import_fee_const = description.get("grid_import_fee_const", None)
            grid_import_fee_const = (
                grid_import_fee_const if grid_import_fee_const is not None else grid_fee_constant)
            grid_export_fee_const = description.get("grid_export_fee_const", None)
            area = CoefficientArea(
                name, children, uuid, optional("strategy"), config,
                coefficient_percentage=description.get("coefficient_percentage", 0.0),
                taxes_surcharges=description.get("taxes_surcharges", 0.0),
                fixed_monthly_fee=description.get("fixed_monthly_fee", 0.0),
                marketplace_monthly_fee=description.get("marketplace_monthly_fee", 0.0),
                assistance_monthly_fee=description.get("assistance_monthly_fee", 0.0),
                market_maker_rate=description.get(
                    "market_maker_rate",
                    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE / 100.),
                feed_in_tariff=description.get(
                    "feed_in_tariff", GlobalConfig.FEED_IN_TARIFF / 100.,),
                grid_fee_percentage=grid_fee_percentage,
                grid_import_fee_const=grid_import_fee_const,
                grid_export_fee_const=grid_export_fee_const
            )
        else:
            area = Area(name, children, uuid, optional("strategy"), config,
                        grid_fee_percentage=grid_fee_percentage,
                        grid_fee_constant=grid_fee_constant,
                        external_connection_available=external_connection_available and
                        config.external_connection_enabled,
                        throughput=ThroughputParameters(
                            baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                            baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                            import_capacity_kVA=import_capacity_kVA,
                            export_capacity_kVA=export_capacity_kVA))
        if "display_type" in description:
            area.display_type = description["display_type"]
        return area
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Input is not a valid area description "
                         f"({error} {description})") from error


def area_from_string(string, config):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string), config)


def are_all_areas_unique(area, set_of_areas=None):
    """Assert that all areas have unique names. Currently disabled."""
    if not set_of_areas:
        set_of_areas = set()
    assert area.name not in set_of_areas
    set_of_areas.add(area.name)

    for child in area.children:
        set_of_areas = are_all_areas_unique(child, set_of_areas)

    return set_of_areas
