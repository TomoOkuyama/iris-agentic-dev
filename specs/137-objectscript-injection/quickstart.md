# Quickstart: 137

```bash
# validators and the detector, no IRIS
RUST_TEST_THREADS=12 cargo test --features testing --test unit os_validators
# the whole file: its last test is the one that fails on any canary, so -k hides failures
python3 -m pytest scripts/gates/test_antipatterns.py -q
python3 scripts/gates/antipatterns.py

# live sentinel tests, against iris-dev-iris (web port 52780), serial
IRIS_HOST=localhost IRIS_WEB_PORT=52780 \
  cargo test --features testing --test integration injection_137 -- --ignored --test-threads=1

# whole suite before the docs task
cargo test --features testing -- --include-ignored --test-threads=1
```

Each live test sets `^IrisDevTest.S137<site>` to a known value, calls the tool with write tools off
and a parameter that would kill it, and asserts the refusal code and that the sentinel still holds
its value.
