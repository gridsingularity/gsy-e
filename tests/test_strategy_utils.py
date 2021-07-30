"""
Copyright 2018 Grid Singularity This file is part of D3A.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or(at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
import pytest

from d3a.models.strategy import utils


class TestStrategyUtils:
    """Test utility functions for strategy modules."""

    @staticmethod
    @pytest.mark.parametrize("execution_number", range(10))
    def test_alter_energy(execution_number):  # pylint: disable=W0613
        """The alter_energy util function always returns a value in the expected deviation range.

        This test is run multiple times to make sure that the output is reliable.
        """
        assert 900 <= utils.alter_energy(1000, max_deviation_pct=10) <= 1100
        assert 950 <= utils.alter_energy(1000, max_deviation_pct=5) <= 1050
