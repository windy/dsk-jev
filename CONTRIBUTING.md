# Contributing

Open an issue describing the problem and a reproducible example, with credentials and private inputs removed. Small focused pull requests are welcome.

Run the offline checks in README before submitting. Tests must not depend on provider keys or paid API calls. Add behavioral tests for protocol changes, validation, and retries; preserve existing text clients when extending vision. Keep default behavior stable and mark experimental modes explicitly.

For benchmarks, record model, date, dataset hash, prompt/output mode, retry policy, connection reuse, concurrency, cache state, all attempted token usage and pricing snapshot. Include failures in effective accuracy. Do not tune against a test set and call it a blind holdout.

By contributing, you agree that your contributions are provided under the project's MIT license. Preserve third-party notices.
