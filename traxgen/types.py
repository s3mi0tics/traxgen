"""
Core schema enums for GraviTrax courses.

These mirror the binary format reverse-engineered by lfrancke/murmelbahn.
Integer values MUST match the schema exactly — generated courses won't load
in the real GraviTrax app if these drift.

Source of truth: https://github.com/lfrancke/murmelbahn/blob/main/imhex-schema.txt

Path: gravitrax-gen/gravitrax_gen/types.py
"""

from enum import IntEnum


class CourseKind(IntEnum):
    """Top-level classification of a course (metadata only)."""
    NONE = 0
    CUSTOM = 1
    REGULAR_EDITORIAL = 2
    TUTORIAL = 4
    DOWNLOAD_USER = 5
    RECOVERY = 6
    DOWNLOAD_EDITORIAL = 7
    IN_APP_PURCHASE = 8
    PRO_EDITORIAL = 9
    POWER_EDITORIAL = 10


class ObjectiveKind(IntEnum):
    """Course objective. Only NONE is defined in the current schema."""
    NONE = 0


class TileKind(IntEnum):
    """
    Every tile type that can sit on the hex grid.

    Integer values have gaps (e.g., 6 and 76 are absent) — this is intentional
    and matches the binary format. Do not renumber.

    Starter-Set (22410) uses a small subset: STARTER, CURVE, CATCH, GOAL_BASIN,
    DROP, CROSS, THREEWAY, TWO_WAY, SPLASH, CANNON, STACKER, STACKER_SMALL,
    SWITCH_LEFT, SWITCH_RIGHT.
    """
    NONE = 0
    STARTER = 1
    CURVE = 2
    CATCH = 3
    GOAL_BASIN = 4
    DROP = 5
    CATAPULT = 7
    CROSS = 8
    THREEWAY = 9
    TWO_WAY = 10
    SPIRAL = 11
    SPLASH = 12
    LOOP = 13
    CANNON = 14
    STACKER = 15
    STACKER_SMALL = 16
    SWITCH_LEFT = 17
    SWITCH_RIGHT = 18
    GOAL_RAIL = 19
    STACKER_BATCH = 20
    CASCADE = 21
    STRAIGHT_TUNNEL = 22
    CURVE_TUNNEL = 23
    SWITCH_TUNNEL = 24
    TRAMPOLIN_0 = 25
    TRAMPOLIN_1 = 26
    TRAMPOLIN_2 = 27
    LIFT_SMALL = 28
    LIFT_LARGE = 29
    FLIP = 30
    TIP_TUBE = 31
    VOLCANO = 32
    JUMPER = 33
    TRANSFERT = 34  # Schema spelling (French-influenced); kept as-is for round-trip fidelity
    ZIPLINE_START = 35
    ZIPLINE_END = 36
    BRIDGE = 37
    SCREW_SMALL = 38
    SCREW_MEDIUM = 39
    SCREW_LARGE = 40
    MIXER_OFFSET_EXITS = 41
    SPLITTER = 42
    STACKER_TOWER_CLOSED = 43
    STACKER_TOWER_OPENED = 44
    DOUBLE_BALCONY = 45
    MIXER_SAME_EXITS = 46
    DIPPER_LEFT = 47
    DIPPER_RIGHT = 48
    HELIX = 49
    TURNTABLE = 50
    SPINNER = 51
    TWO_IN_ONE_SMALL_CURVE_A = 52
    TWO_IN_ONE_SMALL_CURVE_B = 53
    FLEXIBLE_TWO_IN_ONE_B = 54
    RIBBON_CURVE = 55
    THREE_ENTRANCE_FUNNEL = 56
    CURVE_CROSSING = 57
    DOUBLE_BIG_CURVE = 58
    DOUBLE_SMALL_CURVE = 59
    MULTI_JUNCTION = 60
    STRAIGHT_CURVE_CROSSING = 61
    TRIPLE_SMALL_CURVE = 62
    FLEXIBLE_TWO_IN_ONE_A = 63
    COLOR_SWAP_EMPTY = 64
    COLOR_SWAP_PRELOADED = 65
    CAROUSEL_SAME_EXITS = 66
    CAROUSEL_OFFSET_EXITS = 67
    DOME_STARTER = 68
    FINISH_TRIGGER = 69
    FINISH_ARENA = 70
    TRIGGER = 71
    DROPDOWN_SWITCH_LEFT = 72
    DROPDOWN_SWITCH_RIGHT = 73
    QUEUE = 74
    LEVER = 75
    ELEVATOR = 77  # Note: value 76 is absent from the schema
    LIGHT_BASE = 78
    LIGHT_STACKER = 79
    LIGHT_STACKER_SMALL = 80
    LIGHT_STACKER_BATCH = 81
    RELEASER_1 = 82
    RELEASER_2 = 83
    RELEASER_3 = 84
    RELEASER_4 = 85


class LayerKind(IntEnum):
    """
    Layers are horizontal planes on which cells are placed.

    BASELAYER = the cardboard baseplate.
    LARGE_LAYER / SMALL_LAYER = transparent level plates stacked above.
    LARGE_GHOST_LAYER = visual-only/intermediate layer used internally.
    """
    BASELAYER_PIECE = 0
    BASELAYER = 1
    LARGE_LAYER = 2
    LARGE_GHOST_LAYER = 3
    SMALL_LAYER = 4


class PowerSignalMode(IntEnum):
    """
    POWER line signal color. Only relevant for POWER_2022+ save versions.
    NONE (0x80000000) is the 'unset' sentinel in the binary format.
    """
    NONE = 2147483648
    OFF = 0
    RED = 1
    GREEN = 2
    BLUE = 3
    AUTOMATIC = 4


class LightStoneColorMode(IntEnum):
    """Light stone color mode. Only relevant for LIGHT_STONES_2023 save version."""
    NONE = 2147483648
    OFF = 0
    ALTERNATING = 1
    RED = 2
    GREEN = 3
    BLUE = 4
    WHITE = 5


class CourseElementGeneration(IntEnum):
    """
    Release wave a course belongs to. Stored in the course footer; used by
    the app to decide which element set is needed.
    """
    INITIAL_LAUNCH = 0
    CHRISTMAS_2018 = 1
    EASTER_2019 = 2
    AUTUMN_2019 = 3
    EASTER_2020 = 4
    PRO = 5
    FALL_2021 = 6
    SPRING_2022 = 7
    POWER = 8
    AUTUMN_2023 = 9


class CourseSaveDataVersion(IntEnum):
    """
    Binary format version. The parser branches on this value.

    We target POWER_2022 (v4) as our write version — it's newer than the
    common-case user courses and the schema is stable. LIGHT_STONES_2023
    adds light-stone fields we don't need for starter-set generation.
    """
    INITIAL_LAUNCH = 100101
    RAIL_REWORK_2018 = 100201
    PERSISTENCE_REFACTOR_2019 = 1
    ZIPLINE_ADDED_2019 = 2
    PRO_2020 = 3
    POWER_2022 = 4
    LIGHT_STONES_2023 = 5


class RailKind(IntEnum):
    """
    Rails connect two tile exits. Value 2 is absent from the schema (intentional gap).
    Starter-Set ships with plain STRAIGHT rails only (in 3 lengths — encoded as
    rail quantity rather than rail kind).
    """
    STRAIGHT = 0
    BERNOULLI = 1
    DROP_HILL = 3
    DROP_VALLEY = 4
    U_TURN = 5
    NARROW = 6
    SLOW = 7
    BERNOULLI_SMALL_STRAIGHT = 8
    BERNOULLI_SMALL_LEFT = 9
    BERNOULLI_SMALL_RIGHT = 10
    FLEX_TUBE_0 = 11
    FLEX_TUBE_60 = 12
    FLEX_TUBE_120 = 13
    FLEX_TUBE_180 = 14
    FLEX_TUBE_240 = 15
    FLEX_TUBE_300 = 16


class RopeKind(IntEnum):
    """Zipline rope kind. Only used in ZIPLINE_ADDED_2019 save version."""
    NONE = 0
    STRAIGHT = 1


class WallSide(IntEnum):
    """Which side of a PRO wall a balcony is mounted to."""
    WEST = 0
    EAST = 1
