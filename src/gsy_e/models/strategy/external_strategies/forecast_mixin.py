import json
import logging
from collections import deque
from typing import Dict

from gsy_framework.utils import convert_str_to_pendulum_in_dict
from pendulum import DateTime

from gsy_e.models.strategy.external_strategies import IncomingRequest, ExternalMixin


class ForecastExternalMixin(ExternalMixin):
    """Handle external connection WRT to forecasts and measurements."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Buffers for energy forecast and measurement values,
        # that have been sent by the gsy_e-api-client in the duration of one market slot
        self.energy_forecast_buffer: Dict[DateTime, float] = {}
        self.energy_measurement_buffer: Dict[DateTime, float] = {}

    def event_tick(self):
        """Set the energy forecast using pending requests. Extends super implementation.

        This method is triggered by the TICK event.
        """
        # Need to repeat he pending request parsing in order to handle power forecasts
        # from the MQTT subscriber (non-connected admin)
        for req in self.pending_requests:
            if req.request_type == "set_energy_forecast":
                self._set_energy_forecast_impl(req.arguments, req.response_channel)
            elif req.request_type == "set_energy_measurement":
                self._set_energy_measurement_impl(req.arguments, req.response_channel)

        self.pending_requests = deque(
            req for req in self.pending_requests
            if req.request_type not in ["set_energy_forecast", "set_energy_measurement"])

        super().event_tick()

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
        """Map commands to callbacks for forecast and measurement reading."""
        if req.request_type == "set_energy_forecast":
            self._set_energy_forecast_impl(req.arguments, req.response_channel)
        elif req.request_type == "set_energy_measurement":
            self._set_energy_measurement_impl(req.arguments, req.response_channel)
        else:
            super()._incoming_commands_callback_selection(req)

    @property
    def channel_dict(self) -> Dict:
        """Extend channel_dict property with forecast related channels."""
        return {**super().channel_dict,
                self.channel_names.energy_forecast: self._set_energy_forecast,
                self.channel_names.energy_measurement: self._set_energy_measurement}

    def event_market_cycle(self) -> None:
        """Update forecast and measurement in state by reading from buffers."""
        self.update_energy_forecast()
        self.update_energy_measurement()
        self._clear_energy_buffers()
        super().event_market_cycle()

    def _clear_energy_buffers(self) -> None:
        """Clear forecast and measurement buffers."""
        self.energy_forecast_buffer = {}
        self.energy_measurement_buffer = {}

    def event_activate_energy(self) -> None:
        """This strategy does not need to initiate energy values as they are sent via the API."""
        self._clear_energy_buffers()

    @property
    def _aggregator_command_callback_mapping(self) -> Dict:
        """Add the forecast and measurement callbacks to the command mapping."""
        return {
            **super()._aggregator_command_callback_mapping,
            "set_energy_forecast": self._set_energy_forecast_aggregator,
            "set_energy_measurement": self._set_energy_measurement_aggregator
        }

    def _set_energy_forecast(self, payload: Dict) -> None:
        """Callback for set_energy_forecast redis endpoint."""
        self._set_device_energy_data(payload, "set_energy_forecast", "energy_forecast")

    def _set_energy_measurement(self, payload: Dict) -> None:
        """Callback for set_energy_measurement redis endpoint."""
        self._set_device_energy_data(payload, "set_energy_measurement", "energy_measurement")

    def _set_device_energy_data(self, payload: Dict, command_type: str,
                                energy_data_arg_name: str) -> None:
        transaction_id = self._get_transaction_id(payload)
        response_channel = (
            self.channel_names.energy_forecast
            if command_type == "set_energy_forecast"
            else self.channel_names.energy_measurement)

        arguments = json.loads(payload["data"])
        if set(arguments.keys()) == {energy_data_arg_name, "transaction_id"}:
            self.pending_requests.append(
                IncomingRequest(command_type, arguments,
                                response_channel))
        else:
            logging.exception("Incorrect %s request: Payload %s", command_type, payload)
            self.redis.publish_json(
                response_channel,
                {"command": command_type,
                 "error": f"Incorrect {command_type} request. "
                          f"Available parameters: ({energy_data_arg_name}).",
                 "transaction_id": transaction_id})

    def _set_energy_forecast_impl(self, arguments: Dict, response_channel: str) -> None:
        self._set_device_energy_data_impl(arguments, response_channel, "set_energy_forecast")

    def _set_energy_measurement_impl(self, arguments: Dict, response_channel: str) -> None:
        self._set_device_energy_data_impl(arguments, response_channel, "set_energy_measurement")

    def _set_device_energy_data_impl(self, arguments: Dict, response_channel: str,
                                     command_type: str) -> None:
        """
        Digest command from buffer and perform set_energy_forecast or set_energy_measurement.
        Args:
            arguments: Dictionary containing "energy_forecast/energy_measurement" that is a dict
                containing a profile
                key: time string, value: energy in kWh
            response_channel: redis channel string where the response should be sent to
        """
        # pylint: disable=broad-except
        try:
            self._set_device_energy_data_state(command_type, arguments)
            response = {"command": command_type, "status": "ready",
                        "transaction_id": arguments.get("transaction_id")}
        except (Exception, ):
            error_message = (f"Error when handling _{command_type}_impl "
                             f"on area {self.device.name}. Arguments: {arguments}")
            logging.exception(error_message)
            response = {"command": command_type, "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def _set_energy_forecast_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the set_energy_forecast endpoint when sent by aggregator."""
        return self._set_device_energy_data_aggregator(arguments, "set_energy_forecast")

    def _set_energy_measurement_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the set_energy_measurement endpoint when sent by aggregator."""
        return self._set_device_energy_data_aggregator(arguments, "set_energy_measurement")

    def _set_device_energy_data_aggregator(self, arguments: Dict, command_name: str) -> Dict:
        # pylint: disable=broad-except
        try:
            self._set_device_energy_data_state(command_name, arguments)
            response = {
                "command": command_name, "status": "ready",
                command_name: arguments,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except (Exception, ):
            logging.exception("Error when handling bid on area %s", self.device.name)
            response = {
                "command": command_name, "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling {command_name} "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _set_device_energy_data_state(self, command_type: str, arguments: Dict) -> None:
        """Update the state of the device with forecast and measurement data."""
        if command_type == "set_energy_forecast":
            self._validate_values_positive_in_profile(arguments["energy_forecast"])
            self.energy_forecast_buffer.update(
                convert_str_to_pendulum_in_dict(arguments["energy_forecast"]))
        elif command_type == "set_energy_measurement":
            self._validate_values_positive_in_profile(arguments["energy_measurement"])
            self.energy_measurement_buffer.update(
                convert_str_to_pendulum_in_dict(arguments["energy_measurement"]))
        else:
            assert False, f"Unsupported command {command_type}, available commands: " \
                          "set_energy_forecast, set_energy_measurement"

    @staticmethod
    def _validate_values_positive_in_profile(profile: Dict) -> None:
        """Validate whether all values are positive in a profile."""
        for time_str, energy in profile.items():
            if energy < 0.0:
                raise ValueError(f"Energy is not positive for time stamp {time_str}.")
