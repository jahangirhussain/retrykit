# retrykit

Tiny, dependency-free retries for Python, with exponential backoff and full jitter. One decorator, sync and async, fully deterministic under test.

```python
from retrykit import retry

@retry(attempts=5, on=(ConnectionError, TimeoutError))
def fetch_report():
    ...
```

## Why this exists

Retrying a failed call looks simple until many clients do it at once. If every client waits exactly 1s, then 2s, then 4s, they all retry in the same instant and hit the recovering service as a synchronized wave. This is the *thundering herd* problem.

retrykit spreads retries out with **full jitter**: each wait is a random value between 0 and the current backoff ceiling. The design rationale is in [docs/design-notes.md](docs/design-notes.md).

## Install

```bash
pip install git+https://github.com/<your-username>/retrykit.git
```

Requires Python 3.8+. There are no runtime dependencies.

## Usage

### Retry specific errors

Only exceptions listed in `on` are retried. Anything else propagates immediately, so programming errors are never hidden behind a retry loop.

```python
@retry(attempts=4, on=(ConnectionError,))
def call_api():
    ...
```

### Async functions

Coroutine functions are detected automatically and awaited between tries using `asyncio.sleep`.

```python
@retry(attempts=3, on=(TimeoutError,))
async def fetch(session, url):
    ...
```

### Tune the schedule

```python
from retrykit import Backoff, retry

@retry(backoff=Backoff(base=0.5, cap=10, factor=2))
def sync_inventory():
    ...
```

With `base=0.5`, the ceilings for the first four waits are 0.5s, 1s, 2s and 4s, capped at 10s. The actual wait is a random draw below each ceiling.

### Observe retries

```python
def log_retry(attempt, exc, delay):
    print(f"attempt {attempt} failed ({exc!r}); retrying in {delay:.2f}s")

@retry(on_retry=log_retry)
def job():
    ...
```

## API

### `retry(*, attempts=5, on=(Exception,), backoff=Backoff(), sleep=None, rng=random.random, on_retry=None)`

| Parameter  | Description |
|------------|-------------|
| `attempts` | Total tries including the first. Must be at least 1. |
| `on`       | Tuple of exception types that trigger a retry. |
| `backoff`  | A `Backoff` schedule. |
| `sleep`    | Replacement for `time.sleep` (sync) or `asyncio.sleep` (async). |
| `rng`      | Function returning a float in `[0, 1)`. |
| `on_retry` | Callback `(attempt, exc, delay)` invoked before each wait. |

When attempts are exhausted, the last exception is re-raised unchanged, with its original traceback.

### `Backoff(base=0.1, cap=30.0, factor=2.0)`

Immutable schedule. `ceiling(attempt)` returns `min(cap, base * factor ** attempt)` and `delay(attempt)` returns a uniform draw from `[0, ceiling)`. `attempt` is zero-based.

## Testing code that retries

`sleep` and `rng` are injectable, so tests run instantly and deterministically:

```python
slept = []
fn = retry(attempts=3, sleep=slept.append, rng=lambda: 1.0)(flaky_call)
fn()
assert slept == [0.1, 0.2]
```

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## License

MIT
