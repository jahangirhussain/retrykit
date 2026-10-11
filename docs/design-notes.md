# Design notes

## Problem

A client that retries a failed request is trying to ride out a transient fault. The retry policy has two competing goals:

1. Recover quickly when the fault is brief.
2. Avoid adding load to a service that is already struggling.

## Decision: exponential backoff with full jitter

**Exponential backoff** raises the wait after every failure (`base * factor ** attempt`, capped). Short outages recover fast, and long outages stop receiving frequent retries.

**Jitter** breaks the synchronization between clients. Plain exponential backoff still produces waves: clients that failed together retry together. We draw each wait uniformly from `[0, ceiling)` ("full jitter"), which spreads retries across the whole window.

Alternatives considered:

| Strategy | Trade-off |
|----------|-----------|
| Fixed delay | Simple, but synchronized and does not back off under sustained failure. |
| Exponential, no jitter | Backs off, but clients stay in lockstep. |
| Equal jitter (`ceiling/2 + rand * ceiling/2`) | Guarantees a minimum wait, but clusters retries in the upper half of the window. |
| **Full jitter** | Best spread; can occasionally retry almost immediately, which is acceptable because the ceiling still grows. |

## Decision: injectable `sleep` and `rng`

Retry logic is awkward to test because it involves time and randomness. Both are parameters with production defaults, so tests can assert exact delays and never actually sleep.

## Decision: re-raise the original exception

Wrapping the final failure in a custom `RetryError` would force callers to unwrap it. Re-raising the original keeps `except ConnectionError:` working around a retried call and preserves the traceback.

## Non-goals

- **Circuit breaking.** Stopping all calls after repeated failure is a separate concern.
- **Idempotency.** retrykit cannot know whether repeating a call is safe. Only decorate operations that are.
