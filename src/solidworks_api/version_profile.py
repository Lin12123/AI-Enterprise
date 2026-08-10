"""SOLIDWORKS version profile data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolidWorksVersionProfile:
    name: str
    top_plane_aliases: tuple[str, ...]


SOLIDWORKS_2019_SP5 = SolidWorksVersionProfile(
    name="SOLIDWORKS 2019 SP5.0",
    top_plane_aliases=("Top Plane", "上视基准面", "上视基准面1", "Top"),
)


DEFAULT_PROFILE = SOLIDWORKS_2019_SP5
