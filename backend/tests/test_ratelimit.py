from backend.app.ratelimit import RateLimiter


def test_sliding_window_and_retry_after():
    now = [0.0]
    rl = RateLimiter([(2, 10)], clock=lambda: now[0])
    assert rl.hit("a") == (True, 0) and rl.hit("a") == (True, 0)
    ok, retry = rl.hit("a")
    assert not ok and retry == 10
    now[0] = 4
    assert rl.hit("a") == (False, 6)
    now[0] = 10.1
    assert rl.hit("a")[0] is True


def test_keys_are_independent_and_multiple_rules():
    now = [0.0]
    rl = RateLimiter([(1, 5), (3, 100)], clock=lambda: now[0])
    assert rl.hit("x")[0] and not rl.hit("x")[0] and rl.hit("y")[0]
    now[0] = 6; assert rl.hit("x")[0]
    now[0] = 12; assert rl.hit("x")[0]
    now[0] = 18; assert not rl.hit("x")[0]  # third rule: 3 per 100s exhausted
