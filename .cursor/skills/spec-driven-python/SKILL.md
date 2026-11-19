---
name: spec-driven-python
description: Enforce spec-driven Python implementation and pytest coverage for the single-offering course waitlist service. Use when implementing registration/, tests/test_waitlist.py, or RUNBOOK.md.
---

# Spec-Driven Python Implementation

## Rules
1. Follow the approved specs strictly for data models, check order, result codes, FIFO promotion, and `threading.Lock` usage.
2. Keep runtime dependencies limited to the Python standard library; use `pytest` for tests.
3. Do not add out-of-scope features (no frontend, catalog, payments, identity integrations, multi-term logic, external database, or configurable policy engine).
4. Keep methods returning clear result objects rather than raising for refused business or invalid input cases.
