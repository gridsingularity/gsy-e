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

import csv
import logging
import pathlib
from typing import TYPE_CHECKING, Tuple

from gsy_framework.data_classes import (
    Trade,
)
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime

from gsy_e.gsy_e_core.sim_results.file_export_endpoints import CoefficientFileExportEndpoints
from gsy_e.models.area import Area
from gsy_e.gsy_e_core.export import ExportAndPlot

if TYPE_CHECKING:
    from scm.scm_manager import SCMManager

_log = logging.getLogger(__name__)


# pylint: disable=missing-class-docstring,arguments-differ,attribute-defined-outside-init
class CoefficientExportAndPlot(ExportAndPlot):

    def data_to_csv(
        self,
        area: "Area",
        time_slot: DateTime,
        is_first: bool = True,
        scm_manager: "SCMManager" = None,
    ):  # pylint: disable=arguments-renamed
        self._time_slot = time_slot
        self._scm_manager = scm_manager
        self._export_area_with_children(area, self.directory, is_first)

    @property
    def _file_export_endpoints_class(self):
        return CoefficientFileExportEndpoints

    def _export_area_with_children(
        self, area: Area, directory: dir, is_first: bool = False
    ) -> None:
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(" ", "_"))
            if not subdirectory.exists():
                subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory, is_first)

            self._export_scm_trades_to_csv_files(
                area_uuid=area.uuid,
                file_path=self._file_path(directory, f"{area.slug}-trades"),
                labels=("slot",) + Trade.csv_fields(),
                is_first=is_first,
            )

        self._export_area_stats_csv_file(area, directory, AvailableMarketTypes.SPOT, is_first)

    def _export_scm_trades_to_csv_files(
        self, area_uuid: str, file_path: dir, labels: Tuple, is_first: bool = False
    ) -> None:
        """Export files containing individual SCM trades."""
        try:
            with open(file_path, "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                if not self._scm_manager:
                    return
                after_meter_data = self._scm_manager.get_after_meter_data(area_uuid)
                if not after_meter_data:
                    return

                for trade in after_meter_data.trades:
                    row = (self._time_slot,) + trade.csv_values()
                    writer.writerow(row)
        except OSError:
            _log.exception("Could not export offers, bids, trades")
