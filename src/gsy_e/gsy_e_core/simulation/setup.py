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

import sys
from dataclasses import dataclass
from importlib import import_module
from logging import getLogger
from types import ModuleType
from typing import TYPE_CHECKING, Optional

from gsy_framework.constants_limits import ConstSettings
from numpy import random

from gsy_e.gsy_e_core.exceptions import SimulationException
from gsy_e.gsy_e_core.non_p2p_handler import NonP2PHandler
from gsy_e.models.config import SimulationConfig

if TYPE_CHECKING:
    from gsy_e.models.area import Area

log = getLogger(__name__)
RANDOM_SEED_MAX_VALUE = 1000000


@dataclass
class SimulationSetup:
    """Static simulation configuration."""

    seed: int = 0
    enable_bc: bool = False
    use_repl: bool = False
    setup_module_name: str = ""
    started_from_cli: str = True
    config: SimulationConfig = None

    def __post_init__(self) -> None:
        self._set_random_seed(self.seed)

    def load_setup_module(self) -> "Area":
        """Load setup module and create areas that are described on the setup."""
        loaded_python_module = self._import_setup_module(self.setup_module_name)
        area = loaded_python_module.get_setup(self.config)
        NonP2PHandler(area)
        self._log_traversal_length(area)
        return area

    def _set_random_seed(self, seed: Optional[int]) -> None:
        if seed is not None:
            random.seed(int(seed))
        else:
            random_seed = random.randint(0, RANDOM_SEED_MAX_VALUE)
            random.seed(random_seed)
            seed = random_seed
            log.info("Random seed: %s", random_seed)
        self.seed = int(seed)

    def _log_traversal_length(self, area: "Area") -> None:
        no_of_levels = self._get_setup_levels(area) + 1
        num_ticks_to_propagate = no_of_levels * 2
        time_to_propagate_minutes = num_ticks_to_propagate * self.config.tick_length.seconds / 60.0
        log.info(
            "Setup has %s levels, offers/bids need at least %s minutes to propagate.",
            no_of_levels,
            time_to_propagate_minutes,
        )

    def _get_setup_levels(self, area: "Area", level_count: int = 0) -> int:
        level_count += 1
        count_list = [
            self._get_setup_levels(child, level_count) for child in area.children if child.children
        ]
        return max(count_list) if len(count_list) > 0 else level_count

    @staticmethod
    def _import_setup_module(setup_module_name: str) -> ModuleType:
        try:
            if ConstSettings.GeneralSettings.SETUP_FILE_PATH is None:
                return import_module(f".{setup_module_name}", "gsy_e.setup")
            sys.path.append(ConstSettings.GeneralSettings.SETUP_FILE_PATH)
            return import_module(f"{setup_module_name}")
        except (ModuleNotFoundError, ImportError) as ex:
            log.error("Loading the simulation setup module failed: %s", str(ex))
            raise SimulationException(f"Invalid setup module '{setup_module_name}'") from ex
        finally:
            log.debug("Using setup module '%s'", setup_module_name)
