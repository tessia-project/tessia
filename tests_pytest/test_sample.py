# Content of test_sample.py (taken from the official pytest manual).
# Used to check the pytest tool call from CI and must be removed
# when adding real tests.
def inc(x):
    return x + 1


def test_answer():
    assert inc(3) != 5
