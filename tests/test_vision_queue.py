from guitar_face.vision import LatestValueQueue


def test_latest_queue_replaces_stale_value() -> None:
    values = LatestValueQueue[int]()
    assert not values.put_latest(1)
    assert values.put_latest(2)
    assert values.get(timeout=0.01) == 2
    assert values.empty()
