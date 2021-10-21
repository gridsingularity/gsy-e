"""Module containing validators to be applied to incoming orders of external strategies."""

from typing import Dict, List


class ValidationException(Exception):
    """Class to define issues occurring during validation.

    Please do not use this class directly, but rather use its children for more granular handling.
    """
    def __init__(self, message: str = None):
        super().__init__(message)
        self.message = message


class OrderValidationWarning(ValidationException):
    """Class to define non-blocking errors that occur during validation."""


class IncomingOrderValidator:
    """Validate the dictionary of arguments that will be used to generate a Bid or an Offer."""
    DEGREES_OF_FREEDOM_KEYS = ("requirements", "arguments")

    def __init__(self, enable_degrees_of_freedom: bool = True):
        self.warnings: List[OrderValidationWarning] = []
        self.enable_degrees_of_freedom = enable_degrees_of_freedom

    def validate(self, order: Dict) -> None:
        """Validate the dictionary of arguments that define the order."""
        self.warnings = []  # Reset the warnings on each validation call
        self._validate_degrees_of_freedom(order)

    def _validate_degrees_of_freedom(self, order: Dict) -> None:
        """Remove Degrees of Freedom (attributes and requirements) when they are disabled."""
        if self.enable_degrees_of_freedom:
            return

        if any(argument in order for argument in self.DEGREES_OF_FREEDOM_KEYS):
            for degrees_of_freedom_key in self.DEGREES_OF_FREEDOM_KEYS:
                order.pop(degrees_of_freedom_key, None)

            self.warnings.append(
                OrderValidationWarning(
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {self.DEGREES_OF_FREEDOM_KEYS}."))
