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
from unittest.mock import patch

from d3a.models.strategy import utils


class TestStrategyUtils:
    """Test utility functions for strategy modules."""
    @staticmethod
    @patch("d3a.models.strategy.utils.np.random.normal")
    def test_alter_energy_positive_return_values(numpy_normal_mock):
        """Test alter_energy with positive returned values."""
        numpy_normal_mock.return_value = 100  # Avoid random behavior
        assert utils.alter_energy(-1000, relative_std=10) == 0
        # Return 0 when the new energy flips the sign of the original
        assert utils.alter_energy(1000, relative_std=10) > 0

    @staticmethod
    @patch("d3a.models.strategy.utils.np.random.normal")
    def test_alter_energy_negative_return_values(numpy_normal_mock):
        """Test alter_energy with negative returned values."""
        numpy_normal_mock.return_value = -100  # Avoid random behavior
        assert utils.alter_energy(1000, relative_std=10) == 0
        # Return 0 when the new energy flips the sign of the original
        assert utils.alter_energy(-1000, relative_std=10) < 0
