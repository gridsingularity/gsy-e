import json
import logging
from threading import Thread

import time
import websocket
from pendulum import Interval

from d3a.util import simulation_info


class Overview(Thread):
    """
    Send regular updates to d3a-web: Json object with overall
    status of the running simulation.
    """
    def __init__(self, simulation, url, update_interval=Interval(seconds=1)):
        super().__init__(name="overview", daemon=True)
        self.simulation = simulation
        self.area = simulation.area
        self.url = url
        self.update_interval = update_interval
        self.log = logging.getLogger(__name__)
        self.ws = None
        self._connect()

    def _connect(self):
        try:
            self.ws = websocket.create_connection(self.url)
        except ConnectionError as ex:
            self.log.error("Can't connect to websocket %s: %s", self.url, ex)
            self.ws = None

    def run(self):
        self.log.info("Starting update messages to WebUI with interval %s", self.update_interval)
        while True:
            if self.area.current_slot > 0:
                try:
                    if self.ws:
                        self.ws.send(json.dumps(self.current_data()))
                    else:
                        self._connect()
                except ConnectionError:
                    # try reconnecting
                    self.log.error("WebSocket connection lost, attemting reconnect.")
                    self._connect()
                except Exception:
                    self.log.exception("Could not send simulation update")
            time.sleep(self.update_interval.in_seconds())

    def current_data(self):
            return {
                'simulation_status': simulation_info(self.simulation),
                'avg-offer-price': self.area.current_market.avg_offer_price,
                'avg-trade-price': self.area.current_market.avg_trade_price,
                'actual-energy-agg': self.area.current_market.actual_energy_agg
            }
