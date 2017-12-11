class FractionalOffersMixin:
    def __init__(self, *args, _offer_fraction_size=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._offer_fraction_size = _offer_fraction_size

    def offer_fractional(self, market, energy, price):
        """Offer energy in `self._offer_fraction_size` sized chunks."""

        if self._offer_fraction_size is None:
            split_factor = 1
        else:
            split_factor = energy / self._offer_fraction_size
            if split_factor - int(split_factor) == 0:
                split_factor = int(split_factor)
            else:
                split_factor = int(split_factor) + 1

        offered_energy = 0
        energy_fraction = round(energy / split_factor, 4)
        price_split_factor = split_factor
        for i in range(split_factor):
            offer = market.offer(
                price / price_split_factor,
                energy_fraction,
                self.owner.name
            )

            yield offer

            offered_energy += energy_fraction
            if offered_energy + energy_fraction > energy:
                # Due to rounding errors we need to adjust the last iteration's amount
                energy_fraction = round(energy - offered_energy, 4)
                if energy_fraction < 0.0001:
                    break
