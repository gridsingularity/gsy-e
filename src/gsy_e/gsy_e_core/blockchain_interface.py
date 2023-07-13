import uuid


class NonBlockchainInterface:
    def __init__(self, market_id, simulation_id=None):
        self.market_id = market_id
        self.simulation_id = simulation_id
        #print(f"new market created with id: {market_id}")


    def create_new_offer(self, energy, price, seller):
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        return str(uuid.uuid4()), residual_offer

    def track_trade_event(self, time_slot, trade):
        pass

def blockchain_interface_factory(should_use_bc, market_id, simulation_id):
    if should_use_bc:
        from gsy_e.gsy_e_core.blockchain_interface_geth import GethBlockchainInterface
        return GethBlockchainInterface(market_id, simulation_id)
    else:
        return NonBlockchainInterface(market_id, simulation_id)