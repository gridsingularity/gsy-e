from dataclasses import dataclass, field, fields
from typing import Dict


@dataclass
class FeeProperties:
    """Holds all fee properties of a coefficient area"""

    GRID_FEES: Dict = field(default_factory=dict)
    PER_KWH_FEES: Dict = field(default_factory=dict)
    MONTHLY_FEES: Dict = field(default_factory=dict)

    def validate(self):
        """Validate if all fee values are not None."""
        for fee_group in fields(self.__class__):
            for fee_value in getattr(self, fee_group.name).values():
                assert fee_value is not None
