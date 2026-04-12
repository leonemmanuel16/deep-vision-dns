"""
Grid Selector — Dynamic mosaic builder based on active camera count.

Decides how to batch active cameras for DeepStream processing:
- 0 active  → GPU sleeps
- 1 active  → full frame
- 2 active  → 2x1 split
- 3-4       → 2x2 grid
- 5-8       → 2x2 rotating
- 9-12      → 3x3
- 13-18     → 2x 3x3 rotating
"""

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GridConfig:
    """Configuration for a specific grid layout."""
    rows: int
    cols: int
    cell_width: int
    cell_height: int
    batch_size: int
    rotation_needed: bool = False
    rotation_groups: int = 1

    @property
    def total_cells(self) -> int:
        return self.rows * self.cols

    @property
    def mux_width(self) -> int:
        return self.cols * self.cell_width

    @property
    def mux_height(self) -> int:
        return self.rows * self.cell_height


class GridSelector:
    """
    Selects optimal grid configuration based on number of active cameras.
    Provides DeepStream nvstreammux parameters.
    """

    BASE_RESOLUTION = 960  # Base cell size for grid

    def select(self, num_active: int) -> GridConfig | None:
        """
        Select grid configuration for given number of active cameras.
        Returns None if no cameras are active (GPU should sleep).
        """
        if num_active <= 0:
            logger.debug("Grid selector: 0 active cameras, GPU sleeping")
            return None

        if num_active == 1:
            return GridConfig(
                rows=1, cols=1,
                cell_width=1280, cell_height=720,
                batch_size=1,
            )

        if num_active == 2:
            return GridConfig(
                rows=1, cols=2,
                cell_width=960, cell_height=540,
                batch_size=2,
            )

        if num_active <= 4:
            return GridConfig(
                rows=2, cols=2,
                cell_width=960, cell_height=540,
                batch_size=num_active,
            )

        if num_active <= 8:
            return GridConfig(
                rows=2, cols=2,
                cell_width=960, cell_height=540,
                batch_size=4,
                rotation_needed=True,
                rotation_groups=math.ceil(num_active / 4),
            )

        if num_active <= 12:
            return GridConfig(
                rows=3, cols=3,
                cell_width=640, cell_height=360,
                batch_size=min(num_active, 9),
            )

        # 13-18+: two 3x3 grids with rotation
        return GridConfig(
            rows=3, cols=3,
            cell_width=640, cell_height=360,
            batch_size=9,
            rotation_needed=True,
            rotation_groups=math.ceil(num_active / 9),
        )

    def get_rotation_batches(
        self, active_cameras: list[str], grid: GridConfig
    ) -> list[list[str]]:
        """
        Split active cameras into rotation groups for the grid.
        Each group fills one grid batch.
        """
        if not grid.rotation_needed:
            return [active_cameras]

        batch_size = grid.total_cells
        batches = []
        for i in range(0, len(active_cameras), batch_size):
            batches.append(active_cameras[i : i + batch_size])
        return batches

    def get_mux_properties(self, grid: GridConfig) -> dict:
        """
        Return nvstreammux properties for DeepStream pipeline.
        """
        return {
            "batch-size": grid.batch_size,
            "width": grid.mux_width,
            "height": grid.mux_height,
            "batched-push-timeout": 40000,  # microseconds
            "live-source": True,
            "enable-padding": True,
        }
