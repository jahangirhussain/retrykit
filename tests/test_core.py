import asyncio
import unittest

from retrykit import Backoff, retry


class Flaky:
    def __init__(self, failures, exc=ConnectionError):
        self.failures, self.exc, self.calls = failures, exc, 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc(f"boom {self.calls}")
        return "ok"


class BackoffTests(unittest.TestCase):
    def test_ceiling_grows_then_caps(self):
        b = Backoff(base=1, cap=10, factor=2)
        self.assertEqual([b.ceiling(i) for i in range(5)], [1, 2, 4, 8, 10])

    def test_full_jitter_scales_ceiling(self):
        b = Backoff(base=1, cap=10)
        self.assertEqual(b.delay(2, rng=lambda: 0.5), 2.0)
        self.assertEqual(b.delay(2, rng=lambda: 0.0), 0.0)

    def test_rejects_bad_config(self):
        with self.assertRaises(ValueError):
            Backoff(base=0)


class RetryTests(unittest.TestCase):
    def test_succeeds_after_transient_failures(self):
        slept = []
        fn = retry(attempts=4, sleep=slept.append, rng=lambda: 1.0)(Flaky(2))
        self.assertEqual(fn(), "ok")
        self.assertEqual(len(slept), 2)

    def test_reraises_last_error_when_exhausted(self):
        flaky = Flaky(10)
        fn = retry(attempts=3, sleep=lambda s: None)(flaky)
        with self.assertRaisesRegex(ConnectionError, "boom 3"):
            fn()
        self.assertEqual(flaky.calls, 3)

    def test_unlisted_exception_is_not_retried(self):
        flaky = Flaky(5, exc=ValueError)
        fn = retry(on=(ConnectionError,), sleep=lambda s: None)(flaky)
        with self.assertRaises(ValueError):
            fn()
        self.assertEqual(flaky.calls, 1)

    def test_on_retry_receives_attempt_exc_delay(self):
        seen = []
        fn = retry(
            attempts=3,
            sleep=lambda s: None,
            rng=lambda: 1.0,
            backoff=Backoff(base=1, cap=100),
            on_retry=lambda n, e, d: seen.append((n, type(e), d)),
        )(Flaky(2))
        fn()
        self.assertEqual(seen, [(1, ConnectionError, 1.0), (2, ConnectionError, 2.0)])

    def test_attempts_must_be_positive(self):
        with self.assertRaises(ValueError):
            retry(attempts=0)

    def test_async_functions_are_supported(self):
        slept, calls = [], 0

        async def fake_sleep(s):
            slept.append(s)

        @retry(attempts=3, sleep=fake_sleep)
        async def fetch():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError
            return calls

        self.assertEqual(asyncio.run(fetch()), 3)
        self.assertEqual(len(slept), 2)

    def test_preserves_metadata(self):
        @retry()
        def documented():
            """doc"""

        self.assertEqual(documented.__name__, "documented")
        self.assertEqual(documented.__doc__, "doc")


if __name__ == "__main__":
    unittest.main()
