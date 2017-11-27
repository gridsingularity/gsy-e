from math import floor


class FractionalOffersMixin:
    def __init__(self, *args, _offer_fraction_size=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._offer_fraction_size = _offer_fraction_size

    def offer_fractional(self, market, energy, price):
        """Offer energy in `self._offer_fraction_size` sized chunks."""

        if self._offer_fraction_size is None:
            split_factor = 1
        else:
            split_factor = int(floor(energy / self._offer_fraction_size)) + 1

        offered_energy = 0
        energy_fraction = round(energy / split_factor, 4)
        for i in range(split_factor):
            offer = market.offer(
                price * energy_fraction,
                energy_fraction,
                self.owner.name
            )

            yield offer

            offered_energy += energy_fraction
            if offered_energy + energy_fraction > energy:
                # Due to rounding errors we need to adjust the last iteration's amount
                energy_fraction = energy - offered_energy
                if energy_fraction < 0.0001:
                    break
