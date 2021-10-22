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


class DegreesOfFreedomValidator:
    """Validate the Degress of Freedom of an incoming order."""
    DEGREES_OF_FREEDOM_KEYS = ("requirements", "arguments")

    def __init__(self, accept_degrees_of_freedom: bool = True):
        self._accept_degrees_of_freedom = accept_degrees_of_freedom

    def validate(self, order: Dict) -> None:
        """Remove Degrees of Freedom (attributes and requirements) when they are disabled."""
        if self._accept_degrees_of_freedom:
            return

        if any(order.get(argument) for argument in self.DEGREES_OF_FREEDOM_KEYS):
            for degrees_of_freedom_key in self.DEGREES_OF_FREEDOM_KEYS:
                order.pop(degrees_of_freedom_key, None)

            raise OrderValidationWarning(
                "The following arguments are not supported for this market and have been "
                f"removed from your order: {self.DEGREES_OF_FREEDOM_KEYS}.")


class IncomingOrderValidator:
    """Validate the dictionary of arguments that will be used to generate a Bid or an Offer."""

    def __init__(self, accept_degrees_of_freedom: bool = True):
        self.warnings: List[OrderValidationWarning] = []
        self._accept_degrees_of_freedom = accept_degrees_of_freedom

        self._validators = [
            DegreesOfFreedomValidator(accept_degrees_of_freedom=self._accept_degrees_of_freedom)]

    def validate(self, order: Dict) -> None:
        """Validate the dictionary of arguments that define the order."""
        self.warnings = []  # Reset the warnings every time the validation is re-executed
        for validator in self._validators:
            try:
                validator.validate(order)
            except OrderValidationWarning as warning:
                self.warnings.append(warning)
                continue
