from threading import Lock
import json
import logging
import traceback
from d3a.d3a_core.area_serializer import area_from_dict
from d3a.d3a_core.exceptions import D3AException


class LiveEventException(D3AException):
    pass


class CreateAreaEvent:
    def __init__(self, parent_uuid, area_params, config):
        self.parent_uuid = parent_uuid
        self.area_params = area_params
        self.created_area = area_from_dict(area_params, config)

    def apply(self, area):
        if area.uuid != self.parent_uuid:
            return False

        area.children.append(self.created_area)
        return True

    def __repr__(self):
        return f"<CreateAreaEvent - parent UUID({self.parent_uuid} - params({self.area_params}))>"


class UpdateAreaEvent:
    def __init__(self, area_uuid, area_params):
        self.area_uuid = area_uuid
        self.area_params = area_params

    def apply(self, area):
        if area.uuid != self.area_uuid:
            return False

        area.area_reconfigure_event(**self.area_params)
        return True

    def __repr__(self):
        return f"<UpdateAreaEvent - area UUID({self.area_uuid}) - params({self.area_params})>"


class DeleteAreaEvent:
    def __init__(self, area_uuid):
        self.area_uuid = area_uuid

    def apply(self, area):
        if self.area_uuid not in [c.uuid for c in area.children]:
            return False

        area.children = [c for c in area.children if c.uuid != self.area_uuid]
        return True

    def __repr__(self):
        return f"<DeleteAreaEvent - area UUID({self.area_uuid})>"


class LiveEvents:
    def __init__(self, config):
        self.event_buffer = []
        self.lock = Lock()
        self.config = config

    def add_event(self, event_string):
        with self.lock:
            event_dict = json.loads(event_string)
            if event_dict["eventType"] == "create_area":
                event_object = CreateAreaEvent(
                    event_dict["parent_uuid"], event_dict["area_representation"], self.config)
            elif event_dict["eventType"] == "delete_area":
                event_object = DeleteAreaEvent(event_dict["area_uuid"])
            elif event_dict["eventType"] == "update_area":
                event_object = UpdateAreaEvent(
                    event_dict["area_uuid"], event_dict["area_representation"])
            else:
                raise LiveEventException(f"Incorrect event type ({event_dict})")
            self.event_buffer.append(event_object)

    def _handle_event(self, area, event):
        try:
            if event.apply(area) is True:
                return True
        except Exception as e:
            logging.warning(f"Event {event} failed to apply on area {area.name}. "
                            f"Exception: {e}. Traceback: {traceback.format_exc()}")
            return False
        if not area.children:
            return False
        for child in area.children:
            if self._handle_event(child, event) is True:
                return True
        return False

    def handle_all_events(self, root_area):
        with self.lock:
            for event in self.event_buffer:
                if self._handle_event(root_area, event) is False:
                    logging.warning(f"Event {event} not applied.")
            self.event_buffer.clear()
