"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import pytest

from gsy_e.data_classes import PlotDescription


class TestPlotDescription:
    """Tests the validation of PlotDescription data class."""

    @staticmethod
    def test_plot_description_cannot_be_instantiated_without_mandatory_parameters():
        """Test PlotDescription fails without mandatory arguments."""
        with pytest.raises(TypeError):
            PlotDescription(barmode="stack", xtitle="Time",
                            ytitle="Rate [ct./kWh]",
                            title=f"Average Trade Price {30}")
        with pytest.raises(TypeError):
            PlotDescription(data=[], xtitle="Time",
                            ytitle="Rate [ct./kWh]",
                            title=f"Average Trade Price {30}")
        with pytest.raises(TypeError):
            PlotDescription(data=[], barmode="stack",
                            ytitle="Rate [ct./kWh]",
                            title=f"Average Trade Price {30}")
        with pytest.raises(TypeError):
            PlotDescription(data=[], barmode="stack", xtitle="Time",
                            title=f"Average Trade Price {30}")
        with pytest.raises(TypeError):
            PlotDescription(data=[], barmode="stack", xtitle="Time",
                            ytitle="Rate [ct./kWh]")
