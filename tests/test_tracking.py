from guitar_face.tracking import TrackingLossController, TrackingState


def test_tracking_loss_holds_then_returns_smoothly() -> None:
    controller = TrackingLossController(neutral_value=0, hold_ms=500, return_ms=500)
    assert controller.detected(100, 1000).state is TrackingState.TRACKING
    assert controller.missing(1500).value == 100
    halfway = controller.missing(1750)
    assert halfway.state is TrackingState.RETURNING
    assert halfway.value == 50
    lost = controller.missing(2000)
    assert lost.state is TrackingState.LOST
    assert lost.value == 0


def test_detection_cancels_return_and_inverted_neutral_is_supported() -> None:
    controller = TrackingLossController(neutral_value=127)
    controller.detected(20, 1000)
    assert controller.missing(1750).value == 74
    resumed = controller.detected(40, 1800)
    assert resumed.value == 40
    assert controller.missing(1850).value == 40


def test_never_seen_face_outputs_neutral() -> None:
    controller = TrackingLossController(neutral_value=12)
    assert controller.missing(5000).value == 12
    assert controller.missing(5000).state is TrackingState.LOST
