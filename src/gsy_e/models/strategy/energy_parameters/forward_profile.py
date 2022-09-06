import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict

import pendulum

from gsy_framework.enums import AvailableMarketTypes
from gsy_e.gsy_e_core.util import d3a_path


# The Standard Solar Profile energy parameters in this module are not used for Intraday Markets
ALLOWED_MARKET_TYPES = [
    AvailableMarketTypes.DAY_FORWARD,
    AvailableMarketTypes.WEEK_FORWARD,
    AvailableMarketTypes.MONTH_FORWARD,
    AvailableMarketTypes.YEAR_FORWARD]


class StandardProfileException(Exception):
    """Exception for the StandardProfile."""


class StandardProfileParser:
    """Class representing the Standard Solar Profile for forward products."""

    FILENAME = Path(d3a_path) / "resources/standard_solar_profile.csv"
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    FIELDNAMES = ["INTERVAL"] + MONTHS
    SLOT_LENGTH = pendulum.duration(minutes=15)
    SLOTS_IN_ONE_HOUR = pendulum.duration(hours=1) / SLOT_LENGTH

    @classmethod
    def parse(cls) -> Dict:
        """Parse the standard solar profile.

        Returns: a dict where the keys are the numbers of the months and the values are dicts of
            {time: value} items.
        """
        data = defaultdict(dict)
        with open(cls.FILENAME, "r", encoding="utf-8") as inf:
            reader = csv.DictReader(inf, fieldnames=cls.FIELDNAMES, delimiter=";")
            next(reader)  # Skip header line
            for row in reader:
                # Only keep time, discarding the date information to make the profile more general
                slot = pendulum.parse(row["INTERVAL"], exact=True)
                # The SSP is expressed in power (kW) units, so we convert it to energy (kWh)
                for month_idx, month in cls._enumerate_months():
                    data[month_idx][slot] = float(row[month]) / cls.SLOTS_IN_ONE_HOUR

        return dict(data)

    @classmethod
    def _enumerate_months(cls):
        return enumerate(cls.MONTHS, start=1)


class ForwardTradeProfileGenerator:
    """
    Class to generate a new profile that spreads the trade energy across multiple market slots.

    The values of this profile are obtained by scaling the values of the Standard Solar Profile.
    """

    _STANDARD_SOLAR_PROFILE = StandardProfileParser.parse()

    def __init__(self, peak_kWh: float):
        self._scaler = ProfileScaler(self._STANDARD_SOLAR_PROFILE)
        self._scaled_capacity_profile = self._scaler.scale_by_peak(peak_kWh=peak_kWh)

    def generate_trade_profile(
            self, energy_kWh, market_slot, product_type):
        """Generate a profile based on the market slot and the product type."""
        trade_profile = self._scaler.scale_by_peak(peak_kWh=energy_kWh)

        # This subtraction is done _before_ expanding the slots to improve performance
        # residual_energy_profile = self._subtract_profiles(
        #     self._scaled_capacity_profile, trade_profile)

        # Target a specific market slot based on the product type and market_slot.
        return self._expand_profile_slots(trade_profile, market_slot, product_type)

    @staticmethod
    def _expand_profile_slots(profile, market_slot, product_type):
        """Create all the profile slots targeting a specific period of time (depending on the type
        of the product).

        Return:
            A new profile complete with all time slots. E.g.:
                {
                    <time_slot>: value,
                    ...
                }
        """
        assert product_type in ALLOWED_MARKET_TYPES

        period = None
        if product_type == AvailableMarketTypes.YEAR_FORWARD:
            period = pendulum.period(
                start=market_slot.start_of("year"), end=market_slot.end_of("year"))
        elif product_type == AvailableMarketTypes.MONTH_FORWARD:
            period = pendulum.period(
                start=market_slot.start_of("month"), end=market_slot.end_of("month"))
        elif product_type == AvailableMarketTypes.WEEK_FORWARD:
            # Following ISO8601, the start of the week is always Monday
            period = pendulum.period(
                start=market_slot.start_of("week"), end=market_slot.end_of("week"))
        elif product_type == AvailableMarketTypes.DAY_FORWARD:
            period = pendulum.period(
                start=market_slot.start_of("day"), end=market_slot.end_of("day"))

        assert period
        new_profile = {}
        # Create all 15-minutes slots required by the product
        for slot in period.range("minutes", 15):
            try:
                new_profile[slot] = profile[slot.month][slot.time()]
            except KeyError as ex:
                raise StandardProfileException(
                    "There is no slot in the Standard Profile for the requested time. "
                    f"Month: {slot.month}, time: {slot.time()}") from ex

        return new_profile

    @staticmethod
    def _subtract_profiles(
            profile_A: Dict[int, Dict[pendulum.Time, float]],
            profile_B: Dict[int, Dict[pendulum.Time, float]]
            ):
        """Subtract the values in the profile dictionaries.

        Each dictionary has the following structure:
            {
                <month_number>: {<time_slot>: <value>, ...}
                ...
            }
        where `month_number` is just the index of the month in the year (starting from 1).
        """
        assert profile_A.keys() == profile_B.keys()

        return {
            month_number: {
                date: profile_A[month_number][date] - profile_B[month_number][date]
                for date in profile_A[month_number]
            }
            for month_number in profile_A
        }


class ProfileScaler:
    """Class to scale existing profiles based on a new peak.

    NOTE: the profile values must represent energy (kWh).
    """

    def __init__(self, profile: Dict):
        self._original_profile: Dict[int, Dict[pendulum.DateTime, float]] = profile

    def scale_by_peak(self, peak_kWh: float) -> Dict[pendulum.DateTime, float]:
        """Return a profile obtained by scaling the original one using a new peak capacity."""
        scaling_factor = self._compute_scaling_factor(peak_kWh)
        return self._scale_by_factor(scaling_factor)

    @property
    def _original_peak_kWh(self) -> float:
        return max(
            energy_kWh
            for representative_day in self._original_profile.values()
            for energy_kWh in representative_day.values()
        )

    def _compute_scaling_factor(self, peak_kWh: float) -> float:
        """Compute the ratio to be used to scale the original profile based on the new peak."""
        return peak_kWh / self._original_peak_kWh

    def _scale_by_factor(self, scaling_factor: float):
        """Scale the original profile using the scaling factor."""
        scaled_profile = {}
        for month_idx, representative_day in self._original_profile.items():
            scaled_profile[month_idx] = {
                time: energy_kWh * scaling_factor
                for time, energy_kWh in representative_day.items()
            }

        return scaled_profile
