import pytest


class Called:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(
            (
                tuple(repr(a) for a in args),
                {k: repr(v) for k, v in kwargs.items()}
            )
        )


@pytest.yield_fixture
def called():
    yield Called()
