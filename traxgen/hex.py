"""
Hex coordinate math for GraviTrax's flat-top hex grid.

We store coordinates in axial form `(y, x)` to match the binary wire format
from murmelbahn's schema, but convert to cube coordinates `(q, r, s)` where
`q + r + s = 0` for most computations — cube coords make rotation and
distance cleaner.

Key references:
  - Red Blob Games: https://www.redblobgames.com/grids/hexagons/
  - murmelbahn schema: HexVector stores y before x in the binary.

Direction convention:
  Directions 0..5 go counter-clockwise starting at EAST (+x axis). This
  matches the convention we'll verify against parsed real courses in M2.
  If real courses disagree, we adjust HEX_DIRECTIONS here and everything
  downstream stays consistent.

Path: traxgen/traxgen/hex.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

# --- Hex directions --------------------------------------------------------

# Axial offset vectors for the 6 neighbors, going counter-clockwise from EAST.
# Axial coords stored as (y, x) to match the wire format — note order!
#
#       NW    NE
#         \  /
#    W ---- * ---- E
#         /  \
#       SW    SE
#
# Indices: 0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE
HEX_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),    # 0: East
    (-1, 1),   # 1: Northeast
    (-1, 0),   # 2: Northwest
    (0, -1),   # 3: West
    (1, -1),   # 4: Southwest
    (1, 0),    # 5: Southeast
)


# --- Axial coordinate ------------------------------------------------------

@dataclass(frozen=True, slots=True)
class HexVector:
    """
    Axial hex coordinate. Stored as `(y, x)` to match the binary wire format.

    Use this for storage and serialization. For computation, convert to
    CubeVector via `to_cube()`.
    """
    y: int
    x: int

    # Class-level origin cache; lazily populated below to avoid forward-ref.
    _ORIGIN: ClassVar[HexVector | None] = None

    @classmethod
    def origin(cls) -> HexVector:
        """The (0, 0) hex. Common enough to cache."""
        if cls._ORIGIN is None:
            cls._ORIGIN = cls(0, 0)
        return cls._ORIGIN

    def to_cube(self) -> CubeVector:
        """Convert axial (y, x) to cube (q, r, s) where q + r + s = 0."""
        # Standard conversion: axial x → q, axial y → r, s = -q - r
        q = self.x
        r = self.y
        return CubeVector(q, r, -q - r)

    def neighbor(self, direction: int) -> HexVector:
        """
        Return the neighboring hex in the given direction (0..5).

        Directions: 0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE.
        """
        if not 0 <= direction <= 5:
            raise ValueError(f"direction must be 0..5, got {direction}")
        dy, dx = HEX_DIRECTIONS[direction]
        return HexVector(self.y + dy, self.x + dx)

    def neighbors(self) -> tuple[HexVector, ...]:
        """All 6 neighbors, in direction order (E, NE, NW, W, SW, SE)."""
        return tuple(self.neighbor(d) for d in range(6))

    def distance_to(self, other: HexVector) -> int:
        """Hex distance (number of steps) to another hex."""
        return self.to_cube().distance_to(other.to_cube())

    def rotate(self, steps: int) -> HexVector:
        """
        Rotate this hex around the origin by `steps` × 60°.

        Positive steps = counter-clockwise. Six steps = full turn (identity).
        """
        return self.to_cube().rotate(steps).to_axial()

    def rotate_around(self, center: HexVector, steps: int) -> HexVector:
        """Rotate this hex around an arbitrary center by `steps` × 60°."""
        # Translate so center is origin, rotate, translate back.
        translated = HexVector(self.y - center.y, self.x - center.x)
        rotated = translated.rotate(steps)
        return HexVector(rotated.y + center.y, rotated.x + center.x)

    def __add__(self, other: HexVector) -> HexVector:
        return HexVector(self.y + other.y, self.x + other.x)

    def __sub__(self, other: HexVector) -> HexVector:
        return HexVector(self.y - other.y, self.x - other.x)


# --- Cube coordinate -------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CubeVector:
    """
    Cube hex coordinate. Always satisfies q + r + s = 0.

    Use this for computation (distance, rotation, line interpolation).
    Convert to HexVector via `to_axial()` for storage.
    """
    q: int
    r: int
    s: int

    def __post_init__(self) -> None:
        if self.q + self.r + self.s != 0:
            raise ValueError(
                f"Cube coords must satisfy q + r + s = 0, got ({self.q}, {self.r}, {self.s})"
            )

    def to_axial(self) -> HexVector:
        """Convert cube (q, r, s) back to axial (y, x)."""
        # Inverse of HexVector.to_cube: axial.x = q, axial.y = r
        return HexVector(self.r, self.q)

    def distance_to(self, other: CubeVector) -> int:
        """Hex distance between two cube coords."""
        return (abs(self.q - other.q) + abs(self.r - other.r) + abs(self.s - other.s)) // 2

    def rotate(self, steps: int) -> CubeVector:
        """
        Rotate around origin by `steps` × 60°.

        Cube-coord rotation is elegant: each 60° CCW rotation cyclically
        permutes and negates the components.

        steps > 0: counter-clockwise
        steps < 0: clockwise
        steps is taken mod 6 (6 × 60° = 360° = identity).
        """
        # Normalize to 0..5
        s = steps % 6
        q, r, t = self.q, self.r, self.s
        for _ in range(s):
            # One 60° CCW rotation: (q, r, s) → (-r, -s, -q)
            q, r, t = -t, -q, -r
        return CubeVector(q, r, t)


# --- Module-level constants ------------------------------------------------

ORIGIN: HexVector = HexVector(0, 0)
"""Convenience constant for the (0, 0) hex."""
