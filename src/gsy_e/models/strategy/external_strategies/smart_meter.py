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

from typing import Dict, List, TYPE_CHECKING

from gsy_e.models.strategy.external_strategies import ExternalMixin, IncomingRequest
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.market import MarketBase

if TYPE_CHECKING:
    from gsy_e.models.strategy.smart_meter import SmartMeterState


class SmartMeterExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the SmartMeter strategies.
    Should always be inherited together with a superclass of SmartMeterStrategy.
    """

    state: "SmartMeterState"

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        raise NotImplementedError()

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            f"{self.channel_prefix}/offer": self.offer,
            f"{self.channel_prefix}/delete_offer": self.delete_offer,
            f"{self.channel_prefix}/list_offers": self.list_offers,
            f"{self.channel_prefix}/bid": self.bid,
            f"{self.channel_prefix}/delete_bid": self.delete_bid,
            f"{self.channel_prefix}/list_bids": self.list_bids,
        })

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        raise NotImplementedError()

    def event_tick(self) -> None:
        """Process aggregator requests on market tick. Extends super implementation."""
        raise NotImplementedError()

    def offer(self, payload: Dict) -> None:
        """Callback for offer Redis endpoint."""
        raise NotImplementedError()

    def delete_offer(self, payload: Dict) -> None:
        """Callback for delete offer Redis endpoint."""
        raise NotImplementedError()

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        raise NotImplementedError()

    def bid(self, payload: Dict) -> None:
        """Callback for bid Redis endpoint."""
        raise NotImplementedError()

    def delete_bid(self, payload: Dict) -> None:
        """Callback for delete bid Redis endpoint."""
        raise NotImplementedError()

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        raise NotImplementedError()

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
        """
        Actually handle incoming requests that are validated by the corresponding function.
        e.g. New bids are first checked by the `bid` function and put into the `pending_requests`
        queue. Then, requests are handled on each tick using this dispatcher function.
        """
        if req.request_type == "bid":
            self._bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_bid":
            self._delete_bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_bids":
            self._list_bids_impl(req.arguments, req.response_channel)
        elif req.request_type == "offer":
            self._offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_offer":
            self._delete_offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_offers":
            self._list_offers_impl(req.arguments, req.response_channel)
        elif req.request_type == "device_info":
            self._device_info_impl(req.arguments, req.response_channel)
        else:
            assert False, f"Incorrect incoming request name: {req}"

    def _bid_impl(self, arguments: Dict, response_channel: str) -> None:
        """Post the bid to the market."""
        raise NotImplementedError()

    def _delete_bid_impl(self, arguments: Dict, response_channel: str) -> None:
        """Delete a bid from the market."""
        raise NotImplementedError()

    def filtered_market_bids(self, market: MarketBase) -> List[Dict]:
        """
        Get a representation of each of the asset's bids from the market.
        Args:
            market: Market object that will read the bids from

        Returns: List of bids for the strategy asset
        """
        raise NotImplementedError()

    def _list_bids_impl(self, arguments: Dict, response_channel: str) -> None:
        """List sent bids to the market."""
        raise NotImplementedError()

    def _offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Post the offer to the market."""
        raise NotImplementedError()

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Delete an offer from the market."""
        raise NotImplementedError()

    def filtered_market_offers(self, market: MarketBase) -> List[Dict]:
        """
        Get a representation of each of the asset's offers from the market.
        Args:
            market: Market object that will read the offers from

        Returns: List of offers for the strategy asset
        """
        raise NotImplementedError()

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """List sent offers to the market."""
        raise NotImplementedError()


class SmartMeterExternalStrategy(SmartMeterExternalMixin, SmartMeterStrategy):
    """Strategy class for external SmartMeter devices."""
