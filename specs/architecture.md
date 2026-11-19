# Architecture

In-memory Python service and command-line prototype for the one offering described in `specs/charter-and-persona.md`. Tests call the service in-process. The process is the only store.

This document refines the charter on one point: raising capacity promotes once per new seat. Recording a completed course never promotes, even when a seat is already open.

## Service boundary and module layout

The service owns the rules. The CLI parses input and prints results. Tests use the service directly.

```
registration/
  __init__.py          package marker; exports RegistrationService
  models.py            offering, learner records, action results
  service.py           enroll, drop, configure, completions, inspect, promotion, lock
  cli.py               one-process REPL over a single RegistrationService
tests/
  test_waitlist.py     capacity, duplicates, FIFO promotion, prerequisites, invalid drops, lock
```

`registration/__init__.py` only re-exports the service. Business rules stay in `service.py`.

Each public method on `RegistrationService` takes the service lock, decides, mutates, and returns a result object. It does not print and it does not raise for a refused business action. A blank id or a negative capacity is an invalid request result, not an exception.

`cli.py` keeps one `RegistrationService` for the life of the process. A person starts it with `python -m registration.cli` and types one command per line. Separate process invocations do not share state, because the store is in memory. The REPL commands are `configure`, `enroll`, `drop`, `complete`, `inspect`, and `quit`. The CLI holds no lock of its own and contains no promotion logic.

There is no HTTP server, database client, or framework. Runtime code uses the standard library (`dataclasses`, `enum`, `threading`). Tests use pytest.

## Data model and action results

### Records

One offering, created by the first successful `configure`. Learner facts live beside it. A learner does not need to be registered before a completion is recorded.

| Record | Fields | Role |
|---|---|---|
| Offering | `offering_code`, `capacity` (int ≥ 0), `prerequisite_course_code`, `enrolled` (list of learner ids), `waitlist` (list of learner ids, index 0 is the front) | The only offering. `enrolled` order is the order they took a seat. `waitlist` order is arrival order. |
| Learner record | `learner_id`, `completed_courses` (set of course codes) | Created the first time a completion is recorded, or the first time the learner enrolls or joins the waitlist. Survives a drop. |

`seats_open` is `capacity - len(enrolled)`. It is not stored.

A learner id or course code is a non-empty string. Capacity is an integer greater than or equal to zero.

### Actions

All of these run under the service lock.

**configure(offering_code, capacity, prerequisite_course_code)**

Checks run in this order. The first match is the result.

1. `invalid_request` when either code is not a non-blank string, or capacity is not an integer greater than or equal to zero. `bool` is not an accepted capacity. This wins even when the offering code also mismatches.
2. No offering yet: store it and return `configured`. Promotion does not run, because the waitlist is empty.
3. `offering_mismatch` when an offering exists and `offering_code` differs. This wins even when the requested capacity is also below the current enrollment. Change nothing.
4. `capacity_below_enrollment` when the code matches and the new capacity is below `len(enrolled)`. The prerequisite is not updated either.
5. Otherwise return `updated`.

After a request passes those checks:
- Same `offering_code`: replace capacity and the prerequisite, then promote. If the new capacity is greater than the old one, run promotion once per new seat (`new capacity - old capacity`), using the prerequisite just stored. If a pass promotes nobody, stop.
- Same capacity, including a prerequisite-only change: do not promote.
- Lower capacity that is still at least the current enrollment: update, do not promote.

**enroll(learner_id)**

Checks run in this order. The first match is the result, and the lists do not change unless the result is `enrolled` or `waitlisted`.

1. Blank learner id, or a learner id that is not a string: `invalid_request`. This wins even when no offering exists.
2. No offering: `not_configured`.
3. Already in `enrolled`: `already_enrolled`.
4. Already in `waitlist`: `already_waitlisted`.
5. Prerequisite missing from that learner's completed courses: `ineligible`. They are not added to either list.
6. `seats_open > 0`: append to `enrolled`. Result `enrolled`.
7. Otherwise: append to `waitlist`. Result `waitlisted`.

A repeat enroll never moves or removes an existing record. That stays true if the prerequisite later changes and a waiting learner would no longer qualify.

**drop(learner_id)**

- Blank id: `invalid_request`, no change.
- In `enrolled`: remove them, then run promotion once. Result `dropped`, plus the promoted learner id or none.
- In `waitlist` only: `waitlisted`. The entry stays. Promotion does not run.
- Known learner (completion record, or previously enrolled) who is not enrolled now: `not_enrolled`. No change.
- Id the service has never seen: `unknown_learner`. No change.

**record_completed_course(learner_id, course_code)**

- Blank id or course code: `invalid_request`, no change.
- Course already recorded for that learner: `already_recorded`. No change.
- Otherwise: add the course and return `recorded`.

This never enrolls, never waitlists, and never promotes. It may be called before the offering exists. A later drop or capacity increase sees the new completion.

**inspect()**

Returns a snapshot taken under the lock: offering code, capacity, prerequisite, enrolled ids, waitlist ids in FIFO order, and `seats_open`. If no offering exists, the result is `not_configured` and the snapshot is empty. The snapshot is a copy. The caller can read it after the lock is released.

### Result codes

| Action | Code | State change |
|---|---|---|
| configure | `configured` | Offering created |
| configure | `updated` | Capacity and/or prerequisite replaced. Promotion runs only when capacity grew. |
| configure | `offering_mismatch` | None |
| configure | `capacity_below_enrollment` | None |
| configure | `invalid_request` | None |
| enroll | `enrolled` | Appended to `enrolled` |
| enroll | `waitlisted` | Appended to `waitlist` |
| enroll | `already_enrolled` | None |
| enroll | `already_waitlisted` | None |
| enroll | `ineligible` | None |
| enroll | `not_configured` | None |
| enroll | `invalid_request` | None |
| drop | `dropped` | Removed from `enrolled`. At most one waiter promoted. |
| drop | `waitlisted` | None |
| drop | `not_enrolled` | None |
| drop | `unknown_learner` | None |
| drop | `invalid_request` | None |
| record completion | `recorded` | Course added |
| record completion | `already_recorded` | None |
| record completion | `invalid_request` | None |
| inspect | `ok` | None (read) |
| inspect | `not_configured` | None |

A `dropped` result includes `promoted_learner_id`, which is null when nobody eligible was waiting. An `updated` result includes how many learners were promoted by that capacity increase (zero or more).

The CLI prints the code and those ids. A business refusal still exits 0, because the service answered. Unparseable input exits 2 and does not call the service.

## Core invariants

These hold before and after every public method returns.

1. **Capacity.** Once an offering exists, `0 <= len(enrolled) <= capacity`.
2. **One place per learner.** A learner id occurs at most once in `enrolled`, at most once in `waitlist`, and never in both.
3. **Idempotent enroll.** `already_enrolled` and `already_waitlisted` are no-ops. A second request does not create a second record.
4. **Ineligible enroll.** `ineligible` writes neither list.
5. **Safe drops.** `waitlisted`, `not_enrolled`, `unknown_learner`, and `invalid_request` leave enrollment, capacity, the prerequisite, and the waitlist as they were.
6. **Stable queue.** A skipped learner keeps the same relative order. Promotion removes only the learner who takes the seat.
7. **Completion is not enrollment.** `recorded` changes only that learner's completed-course set.

Changing the prerequisite does not remove anyone who is already enrolled and does not remove anyone from the waitlist. Later enroll and promotion checks use the new code.

## FIFO promotion

Promotion is private. It runs only while the service lock is already held, from `drop` and from a capacity increase. It is not a public action.

**One pass**

1. If `len(enrolled) >= capacity`, stop. Nobody moves.
2. Walk `waitlist` from index 0.
3. The first learner whose completed courses contain `prerequisite_course_code` is removed from the waitlist and appended to `enrolled`. Everyone else keeps their order. The pass returns that learner id.
4. A learner who has not completed the prerequisite stays at that index. They do not block the walk.
5. If the walk finishes with no eligible learner, both lists are unchanged and the pass returns none. Any open seat stays open.

**Who calls it**

- Successful `drop`: one pass.
- `configure` that raises capacity by N: up to N passes. Stop early when a pass returns none.
- `record_completed_course`: zero passes.
- `enroll`: zero passes. A free seat is taken by the caller directly in step 6 of enroll, not by the waitlist.
- A prerequisite-only configure, or a capacity decrease: zero passes.

An open seat left behind by an earlier pass is not filled when someone later completes the prerequisite. It is filled only by a later drop (one pass) or by new seats from a capacity increase.

Example. Capacity 2, both seats taken, waitlist `[A, B, C]`. A has not completed the prerequisite. B and C have. A drop removes the enrolled learner and runs one pass: A stays at the front, B is promoted, waitlist is `[A, C]`.

The operator then raises capacity from 2 to 4 (two new seats) while A is still ineligible and C is eligible. Pass one promotes C. Pass two finds only A, promotes nobody, and stops. A remains waiting. One new seat stays open.

## Thread safety, persistence, and limitations

### Locking

`RegistrationService` holds one `threading.Lock`.

- Every public method acquires it for the whole read-decide-write, then releases it.
- Inspect copies state inside the lock and returns that copy.
- Promotion does not acquire the lock. It runs on the calling thread inside `drop` or `configure`, which already hold it. The lock is not re-entrant, so a public method must not call another public method.
- The CLI does not share the service across processes. The lock is there so in-process callers, including a concurrency test, can invoke the service together.

The concurrency test in `tests/test_waitlist.py` should race two enrolls against one open seat and observe one `enrolled` result, one `waitlisted` result, and lists that still satisfy the invariants.

### In-memory persistence

The offering, both lists, and completion sets live on the service instance. Nothing is written to disk. This matches the assessment boundary: no external database.

The tradeoff is that the CLI can demonstrate a sequence only inside one process, and the tests can build a scenario only inside one service instance. When the process exits, the roster is gone. Two REPLs do not see each other. A crash cannot be recovered.

That is acceptable for this slice. Restarting from a saved roster, or sharing one roster across processes, would be a different store.

### Limitations and follow-up risks

- A seat left open because nobody waiting was eligible stays open across later prerequisite completions. The next drop promotes one eligible waiter. A capacity increase fills only the newly added seats, not that older hole.
- Ineligible waiters stay on the queue until they become the earliest eligible learner on some later promotion, or until the process exits. The slice has no waitlist-leave action.
- Completions are additive. Nothing revokes a completed course.
- An enrolled learner who no longer meets a changed prerequisite stays enrolled.
- The CLI trusts whoever has the terminal. There is no identity check.
- The lock does not coordinate multiple processes, and it does not survive a restart.
- `Course-Registration-Rubric-Score.md` is still absent. Behavior is checked against the assessment and these two specs.
