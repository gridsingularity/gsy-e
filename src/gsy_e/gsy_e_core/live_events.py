from threading import Lock
import logging
import traceback
from gsy_e.gsy_e_core.area_serializer import area_from_dict
from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.models.area.event_dispatcher import DispatcherFactory
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy


class LiveEventException(GSyException):
    pass


class CreateAreaEvent:
    def __init__(self, parent_uuid, area_representation, config):
        self.config = config
        self.parent_uuid = parent_uuid
        self.area_representation = area_representation
        self.created_area = area_from_dict(self.area_representation, self.config)

    def apply(self, area):
        if area.uuid != self.parent_uuid:
            return False
        try:
            # The order of the following activation calls matters:
            self.created_area.parent = area
            area.children.append(self.created_area)
            if not area._markets.markets:
                area.cycle_markets(_trigger_event=False)
            self.created_area.activate(current_tick=area.current_tick)
            if self.created_area.strategy:
                self.created_area.strategy.event_activate()
        except Exception as e:
            if self.created_area in area.children:
                area.children.remove(self.created_area)
            raise e
        return True

    def __repr__(self):
        return f"<CreateAreaEvent - parent UUID({self.parent_uuid} - " \
               f"params({self.area_representation}))>"


class UpdateAreaEvent:
    def __init__(self, area_uuid, area_params):
        self.area_uuid = area_uuid
        self.area_params = area_params

    def apply(self, area):
        if area.uuid != self.area_uuid:
            return False
        area_type = self.area_params.pop("type", None)
        self.sanitize_live_event_parameters()
        if area_type is not None and area_type != "Area":
            if area.strategy is None:
                return False
            reactivate = False
            if area_type == "MarketMaker":
                area.strategy = MarketMakerStrategy(**self.area_params)
                reactivate = True
            elif area_type == "InfiniteBus":
                # TODO: After hack to move this parameter casting at the web side
                self.area_params['energy_sell_rate'] = self.area_params.pop('energy_rate', None)
                area.strategy = InfiniteBusStrategy(**self.area_params)
                reactivate = True
            if reactivate:
                area.activate()
                area.strategy.event_activate()
                area.strategy.event_market_cycle()

        area.area_reconfigure_event(**self.area_params)

        return True

    def sanitize_live_event_parameters(self):
        self.area_params.pop('energy_rate_profile_uuid', None)
        self.area_params.pop('buying_rate_profile_uuid', None)
        self.area_params.pop("name", None)
        self.area_params.pop("uuid", None)

    def __repr__(self):
        return f"<UpdateAreaEvent - area UUID({self.area_uuid}) - params({self.area_params})>"


class DeleteAreaEvent:
    def __init__(self, area_uuid):
        self.area_uuid = area_uuid

    def apply(self, area):
        if self.area_uuid not in [c.uuid for c in area.children]:
            return False

        area.children = [c for c in area.children if c.uuid != self.area_uuid]
        if len(area.children) == 0:
            area.dispatcher = DispatcherFactory(area)()
        return True

    def __repr__(self):
        return f"<DeleteAreaEvent - area UUID({self.area_uuid})>"


class LiveEvents:
    def __init__(self, config):
        self.event_buffer = []
        self.lock = Lock()
        self.config = config

    def add_event(self, event_dict, bulk_event=False):
        with self.lock:
            try:
                logging.debug(f"Received live event {event_dict}.")
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
            except Exception as e:
                if bulk_event:
                    self.event_buffer = []
                raise Exception(e)

    def _handle_event(self, area, event):
        try:
            if event.apply(area) is True:
                return True
        except Exception as e:
            logging.error(f"Event {event} failed to apply on area {area.name}. "
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
