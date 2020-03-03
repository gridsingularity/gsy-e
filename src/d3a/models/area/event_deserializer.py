from copy import deepcopy
from d3a.models.area.event_types import DisconnectAreaEvent, ConnectAreaEvent, \
    DisableAreaEvent, EnableAreaEvent, ConfigEvents
import datetime


_deserialize_event = {
    1: DisconnectAreaEvent,
    2: ConnectAreaEvent,
    3: DisableAreaEvent,
    4: EnableAreaEvent
}


def assign_events_to_areas(area, area_events, settings_events):
    selected_events = [event for event in area_events
                       if "area_uuid" in event and event["area_uuid"] == area.uuid]
    event_list = deepcopy(settings_events)
    if len(selected_events) == 1:
        selected_events = selected_events[0]
        for event in selected_events["trigger_events"]:
            event_class = _deserialize_event[event["type"]]
            event_time = datetime.datetime.fromtimestamp(event["time"])
            event_list.append(event_class(event_time))

    elif len(selected_events) > 1:
        raise ValueError("Multiple area events with the same area UUID.")

    area.set_events(event_list)

    if not area.children:
        return
    for child in area.children:
        assign_events_to_areas(child, area_events, settings_events)


def generate_settings_events(settings_events):
    config_events_list = []
    for event in settings_events:
        event_time = datetime.datetime.fromtimestamp(event["time"])
        market_maker_rate = event["market_maker_rate_file"] \
            if "market_maker_rate_file" in event and \
               event["market_maker_rate_file"] is not None \
            else event.get("market_maker_rate", None)
        params = {'cloud_coverage': event.get("cloud_coverage", None),
                  'pv_user_profile': event.get("pv_user_profile", None),
                  'grid_fee_percentage': event.get("iaa_fee", None),
                  'market_maker_rate': market_maker_rate}
        config_events_list.append(ConfigEvents(event_time, params))
    return config_events_list


def deserialize_events_to_areas(events, root_area):
    if not events:
        return
    settings_event_list = generate_settings_events(events.get("settings_events", [])) \
        if "settings_events" in events else []
    assign_events_to_areas(root_area, events.get("area_events", []), settings_event_list)
