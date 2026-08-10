"""Feature handler modules.

All handlers are scaffolded. They must not perform SOLIDWORKS calls until the
fixed API Executor is implemented and guarded by the Policy Engine.
"""

FEATURE_MODULES = (
    "base_plate",
    "extrude",
    "cut",
    "hole",
    "boss",
    "fillet",
    "chamfer",
    "pattern",
    "revolve",
    "sweep",
    "loft",
    "shell",
    "rib",
    "draft",
    "mirror",
    "reference_geometry",
)
