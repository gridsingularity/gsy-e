from pint import UnitRegistry
ureg = UnitRegistry()
Q_ = ureg.Quantity

ureg.define('EUR=1')
ureg.define('EUR_cents=100*EUR')
