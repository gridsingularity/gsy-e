from d3a.d3a_core.util import area_name_from_area_or_iaa_name


def is_cell_tower_type(area):
    return area['type'] == "CellTowerLoadHoursStrategy"


def is_load_node_type(area):
    return area['type'] in ["LoadHoursStrategy", "DefinedLoadStrategy",
                            "LoadHoursExternalStrategy", "LoadProfileExternalStrategy"]


def is_producer_node_type(area):
    return area['type'] in ["PVStrategy", "PVUserProfileStrategy", "PVPredefinedStrategy",
                            "CommercialStrategy", "FinitePowerPlant", "MarketMakerStrategy"]


def is_pv_node_type(area):
    return area['type'] in ["PVStrategy", "PVUserProfileStrategy", "PVPredefinedStrategy",
                            "PVExternalStrategy", "PVUserProfileExternalStrategy"]


def is_prosumer_node_type(area):
    return area['type'] in ["StorageStrategy", "StorageExternalStrategy"]


def is_buffer_node_type(area):
    return area['type'] == "InfiniteBusStrategy"


def area_sells_to_child(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['seller']) == \
            area_name and area_name_from_area_or_iaa_name(trade['buyer']) in child_names


def child_buys_from_area(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['buyer']) == \
        area_name and area_name_from_area_or_iaa_name(trade['seller']) in child_names
