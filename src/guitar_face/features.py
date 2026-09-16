"""MediaPipe blendshape groups used to learn a personal guitar face."""

FEATURE_FAMILIES: dict[str, tuple[str, ...]] = {
    "brows": (
        "browDownLeft",
        "browDownRight",
        "browInnerUp",
        "browOuterUpLeft",
        "browOuterUpRight",
    ),
    "eyes": (
        "cheekSquintLeft",
        "cheekSquintRight",
        "eyeSquintLeft",
        "eyeSquintRight",
    ),
    "mouth": (
        "jawForward",
        "jawLeft",
        "jawOpen",
        "jawRight",
        "mouthClose",
        "mouthDimpleLeft",
        "mouthDimpleRight",
        "mouthFrownLeft",
        "mouthFrownRight",
        "mouthFunnel",
        "mouthLeft",
        "mouthLowerDownLeft",
        "mouthLowerDownRight",
        "mouthPressLeft",
        "mouthPressRight",
        "mouthPucker",
        "mouthRight",
        "mouthRollLower",
        "mouthRollUpper",
        "mouthShrugLower",
        "mouthShrugUpper",
        "mouthSmileLeft",
        "mouthSmileRight",
        "mouthStretchLeft",
        "mouthStretchRight",
        "mouthUpperUpLeft",
        "mouthUpperUpRight",
        "noseSneerLeft",
        "noseSneerRight",
    ),
}

FEATURE_TO_FAMILY = {
    feature: family
    for family, features in FEATURE_FAMILIES.items()
    for feature in features
}
CANDIDATE_FEATURES = tuple(FEATURE_TO_FAMILY)

# A sparse, expressive subset of the 478 face landmarks for the preview.
OVERLAY_LANDMARK_INDICES = (
    1,
    4,
    13,
    14,
    33,
    61,
    70,
    78,
    105,
    107,
    133,
    145,
    159,
    263,
    291,
    300,
    308,
    334,
    336,
    362,
    374,
    386,
)
