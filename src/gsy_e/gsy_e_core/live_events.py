import logging
import traceback
from threading import Lock

from gsy_framework.constants_limits import ConstSettings, SpotMarketTypeEnum
from gsy_framework.live_events.b2b import B2BLiveEvents

from gsy_e.gsy_e_core.area_serializer import area_from_dict
from gsy_e.gsy_e_core.exceptions import LiveEventException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.models.area.event_dispatcher import DispatcherFactory
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy


class CreateAreaEvent:
    """Event that creates a new area on the area representation tree."""

    def __init__(self, parent_uuid, area_representation, config):
        self.config = config
        self.parent_uuid = parent_uuid
        self.area_representation = area_representation
        self.created_area = area_from_dict(self.area_representation, self.config)

    def apply(self, area):
        """Trigger the area creation."""
        if area.uuid != self.parent_uuid:
            return False
        try:
            # The order of the following activation calls matters:
            self.created_area.parent = area
            area.children.append(self.created_area)
            if not area._markets.markets:  # pylint: disable=protected-access
                area.cycle_markets(_trigger_event=False)
            self.created_area.activate(current_tick=area.current_tick)
            if self.created_area.strategy:
                self.created_area.strategy.event_activate()
        except Exception as ex:
            if self.created_area in area.children:
                area.children.remove(self.created_area)
            raise LiveEventException(ex) from ex
        return True

    def __repr__(self):
        return f"<CreateAreaEvent - parent UUID({self.parent_uuid} - " \
               f"params({self.area_representation}))>"


class CreateAreaEventCoefficient(CreateAreaEvent):
    """Event that creates a new area on the area representation tree for SCM simulations."""

    def apply(self, area):
        """Trigger the area creation."""
        if area.uuid != self.parent_uuid:
            return False
        try:
            self.created_area.parent = area
            area.children.append(self.created_area)
            if self.created_area.strategy:
                self.created_area.strategy.event_activate()
            else:
                self.created_area.activate_energy_parameters(
                    current_time_slot=area.current_market_time_slot)
        except Exception as ex:
            if self.created_area in area.children:
                area.children.remove(self.created_area)
            raise LiveEventException(ex) from ex
        return True


class UpdateAreaEvent:
    """Update the parameters of an area and its strategy."""

    def __init__(self, area_uuid, area_params):
        self.area_uuid = area_uuid
        self.area_params = area_params

    def apply(self, area):
        """Trigger the area update."""
        if area.uuid != self.area_uuid:
            return False
        area_type = self.area_params.pop("type", None)
        self._sanitize_live_event_parameters()
        try:
            if area_type is not None and area_type != "Area":
                if area.strategy is None:
                    return False
                reactivate = False
                if area_type == "MarketMaker":
                    area.strategy = MarketMakerStrategy(**self.area_params)
                    reactivate = True
                elif area_type == "InfiniteBus":
                    area.strategy = InfiniteBusStrategy(**self.area_params)
                    reactivate = True
                if reactivate:
                    area.activate()
                    area.strategy.event_activate()
                    area.strategy.event_market_cycle()

            area.area_reconfigure_event(**self.area_params)
        except Exception as ex:
            raise LiveEventException(ex) from ex

        return True

    def _sanitize_live_event_parameters(self):
        self.area_params.pop("energy_rate_profile_uuid", None)
        self.area_params.pop("buying_rate_profile_uuid", None)
        self.area_params.pop("name", None)
        self.area_params.pop("uuid", None)

    def __repr__(self):
        return f"<UpdateAreaEvent - area UUID({self.area_uuid}) - params({self.area_params})>"


class UpdateAreaEventCoefficient(UpdateAreaEvent):
    """Handle update live event for SCM simulations."""

    def apply(self, area):
        """Trigger the area update."""
        if area.uuid != self.area_uuid:
            return False
        self._sanitize_live_event_parameters()
        try:
            if area.strategy:
                # Currently we do not support updates of SCM strategies
                return False
            area.area_reconfigure_event(**self.area_params)
        except Exception as ex:
            raise LiveEventException(ex) from ex
        return True


class DeleteAreaEvent:
    """Delete an area from the area representation tree."""

    def __init__(self, area_uuid):
        self.area_uuid = area_uuid

    def apply(self, area):
        """Trigger the area deletion."""
        if self.area_uuid not in [c.uuid for c in area.children]:
            return False

        area.children = [c for c in area.children if c.uuid != self.area_uuid]
        if len(area.children) == 0:
            area.dispatcher = DispatcherFactory(area)()
        return True

    def __repr__(self):
        return f"<DeleteAreaEvent - area UUID({self.area_uuid})>"


class ForwardMarketsEvent:
    """Add a forward market-related event."""

    def __init__(self, area_uuid, event_params):
        self._area_uuid = area_uuid
        self._event_params = event_params

    def apply(self, area):
        """Trigger the forward market event."""
        if self._area_uuid not in [c.uuid for c in area.children]:
            return False
        area.strategy.apply_live_event(self._event_params)
        return True

    def __repr__(self):
        return f"<ForwardMarketsEvent - area UUID({self._area_uuid})>"


def create_area_live_event_factory():
    """Factory method for the create area live event."""
    return (CreateAreaEventCoefficient
            if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value
            else CreateAreaEvent)


def update_area_live_event_factory():
    """Factory method for the update area live event."""
    return (UpdateAreaEventCoefficient
            if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value
            else UpdateAreaEvent)


class LiveEvents:
    """Manage the incoming live events."""

    def __init__(self, config):
        self._event_buffer = []
        self._tick_event_buffer = []
        self._lock = Lock()
        self._config = config

    def add_event(self, event_dict, bulk_event=False):
        """Add a new event in order to be processed on the next market cycle."""
        with self._lock:
            try:
                logging.debug("Received live event %s.", event_dict)
                if event_dict["eventType"] == "create_area":
                    event_object = create_area_live_event_factory()(
                        event_dict["parent_uuid"], event_dict["area_representation"], self._config)
                elif event_dict["eventType"] == "delete_area":
                    event_object = DeleteAreaEvent(event_dict["area_uuid"])
                elif event_dict["eventType"] == "update_area":
                    event_object = update_area_live_event_factory()(
                        event_dict["area_uuid"], event_dict["area_representation"])
                elif B2BLiveEvents.is_supported_event(event_dict["eventType"]):
                    event_object = ForwardMarketsEvent(event_dict["area_uuid"], event_dict)
                    self._tick_event_buffer.append(event_object)
                    return
                else:
                    raise LiveEventException(f"Incorrect event type ({event_dict})")
                self._event_buffer.append(event_object)
            except Exception as ex:
                if bulk_event:
                    self._event_buffer = []
                raise LiveEventException(ex) from ex

    def _handle_event(self, area, event):
        try:
            if event.apply(area) is True:
                return True
        except LiveEventException as ex:
            logging.error("Event %s failed to apply on area %s. Exception: %s. Traceback: %s",
                          event, area.name, ex, traceback.format_exc())
            return False
        if not area.children:
            return False
        for child in area.children:
            if self._handle_event(child, event) is True:
                return True
        return False

    def _handle_events(self, root_area, event_buffer):
        with self._lock:
            for event in event_buffer:
                if self._handle_event(root_area, event) is False:
                    logging.warning("Event %s not applied.", event)
            event_buffer.clear()

    def handle_all_events(self, root_area):
        """Handle all events that arrived during the past market slot."""
        if self._event_buffer:
            global_objects.profiles_handler.update_time_and_buffer_profiles(
                root_area.current_market_time_slot, root_area)
        self._handle_events(root_area, self._event_buffer)

    def handle_tick_events(self, root_area):
        """Handle all events that arrived during the past tick."""
        if self._tick_event_buffer:
            global_objects.profiles_handler.update_time_and_buffer_profiles(
                root_area.current_market_time_slot, root_area)
        self._handle_events(root_area, self._tick_event_buffer)
