from d3a.models.leaves import CommercialProducer
from d3a.models.strategy.commercial_producer import CommercialStrategy


def test_commercial_producer_leaf():
    leaf = CommercialProducer(name="cep", energy_rate=23)
    assert isinstance(leaf.strategy, CommercialStrategy)
    assert leaf.strategy.energy_rate == 23


def test_leaf_parameters():
    leaf = CommercialProducer(name="cep", energy_rate=33)
    assert leaf.parameters['energy_rate'] == 33
