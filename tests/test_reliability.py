"""Phase 3 reliability logic: token-bucket throttle and API circuit breaker."""
import tools
import youtube


def test_token_bucket_throttles_burst():
    uid = 999001
    tools._play_buckets.pop(uid, None)
    # capacity=3 → first three allowed, fourth throttled (refill is ~1/3s, negligible here)
    assert [tools.allow_play(uid) for _ in range(3)] == [True, True, True]
    assert tools.allow_play(uid) is False


def test_token_bucket_is_per_user():
    tools._play_buckets.pop(1, None)
    tools._play_buckets.pop(2, None)
    for _ in range(3):
        tools.allow_play(1)
    assert tools.allow_play(1) is False
    assert tools.allow_play(2) is True  # different user unaffected


def test_circuit_breaker_opens_after_threshold_and_resets():
    youtube._api_record_success()  # start closed
    assert youtube._api_breaker_open() is False
    for _ in range(youtube._API_FAIL_THRESHOLD):
        youtube._api_record_failure()
    assert youtube._api_breaker_open() is True
    youtube._api_record_success()
    assert youtube._api_breaker_open() is False
