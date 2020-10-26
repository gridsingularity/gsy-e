from d3a.d3a_core.util import area_name_from_area_or_iaa_name


def is_cell_tower_type(area):
    return area['type'] == "CellTowerLoadHoursStrategy"


def is_load_node_type(area):
    return area['type'] in ["LoadHoursStrategy", "DefinedLoadStrategy",
                            "LoadHoursExternalStrategy", "LoadProfileExternalStrategy"]


def is_bulk_power_producer(area):
    return area['type'] in ["CommercialStrategy", "MarketMakerStrategy"]


def is_pv_node_type(area):
    return area['type'] in ["PVStrategy", "PVUserProfileStrategy", "PVPredefinedStrategy",
                            "PVExternalStrategy", "PVUserProfileExternalStrategy",
                            "PVPredefinedExternalStrategy"]


def is_producer_node_type(area):
    return is_bulk_power_producer(area) or is_pv_node_type(area) or \
           area['type'] == "FinitePowerPlant"


def is_prosumer_node_type(area):
    return area['type'] in ["StorageStrategy", "StorageExternalStrategy"]


def is_buffer_node_type(area):
    return area['type'] == "InfiniteBusStrategy"


def get_unified_area_type(area):
    if is_pv_node_type(area):
        return "PV"
    elif is_load_node_type(area):
        return "Load"
    elif is_cell_tower_type(area):
        return "CellTower"
    elif is_prosumer_node_type(area):
        return "Storage"
    elif is_bulk_power_producer(area) or is_buffer_node_type(area):
        return "MarketMaker"
    elif area['type'] == "FinitePowerPlant":
        return "FinitePowerPlant"
    else:
        return "Area"


def area_sells_to_child(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['seller']) == \
            area_name and area_name_from_area_or_iaa_name(trade['buyer']) in child_names


def child_buys_from_area(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['buyer']) == \
        area_name and area_name_from_area_or_iaa_name(trade['seller']) in child_names
