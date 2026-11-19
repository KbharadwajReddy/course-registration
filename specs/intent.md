# Behavioral intents

Service-level outcomes for `RegistrationService`. Each intent is one assertion a test can make: the result code, the result fields, and the offering afterward. These intents do not cover REPL text or exit codes.

`specs/charter-and-persona_2.md` is not in the repo. The behavior below follows `specs/charter-and-persona.md` and `specs/architecture.md`.

A refused action does not raise. Unless an intent says a list changed, `enrolled`, `waitlist`, `capacity`, `prerequisite_course_code`, and every completed-course set stay as they were.

## Terms

- A **blank** value is not a `str`, or is a `str` whose `strip()` is empty. Stored codes and learner ids are kept as given. `"CS101"` and `"cs101"` are different codes.
- A learner is **eligible** when their completed courses contain the offering's current prerequisite, compared exactly.
- `seats_open` is `capacity - len(enrolled)`.
- `configure` failures are decided in this order: `invalid_request`, then `offering_mismatch`, then `capacity_below_enrollment`.
- `dropped.promoted_learner_id` is the learner promoted by that drop, or null when the one pass promotes nobody.
- `updated.promoted_count` is how many learners that capacity increase promoted. It is `0` when capacity did not grow.

## 1. Configure and inspect

### CFG-1. First configure

- Given: no offering.
- When: `configure("CS200", 2, "CS101")`.
- Then: `configured`. Inspect is `ok` with offering `CS200`, capacity `2`, prerequisite `CS101`, `enrolled []`, `waitlist []`, `seats_open 2`.

### CFG-2. Inspect before any offering

- Given: no offering.
- When: `inspect()`.
- Then: `not_configured`. No offering fields are returned.

### CFG-3. Inspect returns a copy

- Given: CFG-1, then an eligible learner is enrolled so `enrolled` is `["L1"]`.
- When: the caller appends `"other"` to the list inside the `ok` snapshot and inspects again.
- Then: the second snapshot still has `enrolled ["L1"]`.

### CFG-4. Capacity zero is a valid offering

- Given: no offering.
- When: `configure("CS200", 0, "CS101")`.
- Then: `configured`. Capacity `0`, `seats_open 0`.

### CFG-5. Repeating the same values

- Given: CFG-1.
- When: `configure("CS200", 2, "CS101")` again.
- Then: `updated` with `promoted_count 0`. Capacity, prerequisite, and both lists are unchanged.

### CFG-6. Capacity increase promotes once per new seat and skips ineligible learners

- Given: offering `CS200`, capacity `1`, prerequisite `CS101`. `enrolled ["E1"]`. `waitlist ["A", "B", "C"]`. A has not completed `CS101`. B and C have.
- When: `configure("CS200", 3, "CS101")` (two new seats).
- Then: `updated`, `promoted_count 2`. `enrolled ["E1", "B", "C"]`. `waitlist ["A"]`. Capacity `3`, `seats_open 0`. A keeps the front of the queue.

### CFG-7. A capacity increase does not fill an older open seat

- Given: offering `CS200`, capacity `2`, prerequisite `CS999`. `enrolled ["E1"]`, so one seat is already open. `waitlist ["A", "B"]`. A has not completed `CS999`. B has.
- When: `configure("CS200", 3, "CS999")` (one new seat).
- Then: `updated`, `promoted_count 1`. `enrolled ["E1", "B"]`. `waitlist ["A"]`. Capacity `3`, `seats_open 1`. The seat that was already open is still open. B took the new seat.

### CFG-8. Capacity decrease does not promote

- Given: capacity `5`, prerequisite `CS101`, `enrolled ["E1", "E2"]`, `waitlist ["W1"]`. W1 has completed `CS101`. `seats_open` is `3`.
- When: `configure("CS200", 4, "CS101")`.
- Then: `updated`, `promoted_count 0`. `enrolled ["E1", "E2"]`. `waitlist ["W1"]`. Capacity `4`, `seats_open 2`.

### CFG-9. Decrease down to the current enrollment

- Given: the offering in CFG-8.
- When: `configure("CS200", 2, "CS101")`.
- Then: `updated`, `promoted_count 0`. `enrolled ["E1", "E2"]`. `waitlist ["W1"]`. `seats_open 0`.

### CFG-10. Capacity below enrollment changes nothing, including the prerequisite

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1", "E2"]`.
- When: `configure("CS200", 1, "CS201")`.
- Then: `capacity_below_enrollment`. Capacity stays `2`, prerequisite stays `CS101`, both lists stay put.

### CFG-11. A prerequisite-only change does not promote or remove anyone

- Given: capacity `1`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["W1"]`. Both have completed `CS101` and neither has completed `CS201`.
- When: `configure("CS200", 1, "CS201")`.
- Then: `updated`, `promoted_count 0`. Prerequisite is `CS201`. `enrolled ["E1"]`. `waitlist ["W1"]`.
- And: `enroll("W1")` returns `already_waitlisted`. `enroll("L9")` for a learner who has only `CS101` returns `ineligible`.

### CFG-12. A capacity increase uses the prerequisite stored by that same call

- Given: capacity `1`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["W2", "W1"]`. W2 has completed `CS101` only. W1 has completed `CS201` only.
- When: `configure("CS200", 2, "CS201")`.
- Then: `updated`, `promoted_count 1`. Prerequisite is `CS201`. `enrolled ["E1", "W1"]`. `waitlist ["W2"]`. W2 is skipped because the new prerequisite applies to that promotion.

### CFG-13. A different offering code

- Given: offering `CS200`, capacity `2`, prerequisite `CS101`, `enrolled ["E1"]`.
- When: `configure("CS300", 9, "CS201")`.
- Then: `offering_mismatch`. Offering code, capacity, prerequisite, and both lists stay as given.

### CFG-14. Invalid configure wins over a mismatched code

- Given: the offering in CFG-13.
- When: `configure("CS300", -1, "CS101")`.
- Then: `invalid_request`, not `offering_mismatch`. State unchanged.
- The same code is returned for `configure("", 2, "CS101")`, `configure("CS200", -1, "CS101")`, `configure("CS200", True, "CS101")`, `configure("CS200", 1.5, "CS101")`, and `configure("CS200", 2, " ")`. None of these change state.

### CFG-15. Mismatch wins over capacity below enrollment

- Given: capacity `2`, `enrolled ["E1", "E2"]`, offering code `CS200`.
- When: `configure("OTHER", 0, "CS101")`.
- Then: `offering_mismatch`, not `capacity_below_enrollment`. State unchanged.

### CFG-16. The first configure is rejected whole when the request is invalid

- Given: no offering.
- When: `configure("", 2, "CS101")`, then `configure("CS200", -1, "CS101")`.
- Then: each call is `invalid_request`. `inspect()` is still `not_configured`.

## 2. Recording completed courses

`record_completed_course` never enrolls, never waitlists, and never promotes.

### REC-1. Record before an offering exists

- Given: no offering.
- When: `record_completed_course("L1", "CS101")`.
- Then: `recorded`. L1's completed courses are `{"CS101"}`. `inspect()` is still `not_configured`.

### REC-2. Recording again is a no-op

- Given: REC-1.
- When: `record_completed_course("L1", "CS101")` again.
- Then: `already_recorded`. The set is still `{"CS101"}`.

### REC-3. A second course is added beside the first

- Given: REC-1.
- When: `record_completed_course("L1", "CS102")`.
- Then: `recorded`. The set is `{"CS101", "CS102"}`.

### REC-4. Completing the prerequisite leaves a waiting learner where they are

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1"]` (one seat already open), `waitlist ["W1", "W2"]`. W1 has not completed `CS101`. W2 has.
- When: `record_completed_course("W1", "CS101")`.
- Then: `recorded`. W1's set contains `CS101`. `enrolled` is still `["E1"]`. `waitlist` is still `["W1", "W2"]`. `seats_open` is still `1`. W2 is not promoted.

### REC-5. An unrelated course does not make a learner eligible

- Given: CFG-1, and `record_completed_course("L1", "CS999")` returned `recorded`.
- When: `enroll("L1")`.
- Then: `ineligible`. Both lists stay empty. L1's set is still `{"CS999"}`.

### REC-6. Blank arguments

- Given: no offering.
- When: `record_completed_course("", "CS101")`, `record_completed_course("L1", "")`, or `record_completed_course("L1", " ")`.
- Then: each call is `invalid_request`. No learner record is created. A later `drop("L1")` is `unknown_learner`.

## 3. Enroll

Membership is checked before eligibility. A learner who is already enrolled or already waiting does not move.

### ENR-1. Eligible learner takes an open seat

- Given: CFG-1, and L1 has completed `CS101`.
- When: `enroll("L1")`.
- Then: `enrolled`. `enrolled ["L1"]`. `waitlist []`. `seats_open 1`.

### ENR-2. A second eligible learner keeps enrollment order

- Given: ENR-1, and L2 has completed `CS101`.
- When: `enroll("L2")`.
- Then: `enrolled`. `enrolled ["L1", "L2"]`. `waitlist []`. `seats_open 0`.

### ENR-3. A full offering waitlists each eligible learner once, in arrival order

- Given: ENR-2. A, then B, have completed `CS101`.
- When: `enroll("A")`, then `enroll("B")`.
- Then: both results are `waitlisted`. `enrolled ["L1", "L2"]`. `waitlist ["A", "B"]`. `seats_open 0`.

### ENR-4. Duplicate enroll of an enrolled learner

- Given: ENR-1.
- When: `enroll("L1")` again.
- Then: `already_enrolled`. `enrolled` is still `["L1"]` and `waitlist` is still `[]`.

### ENR-5. Duplicate enroll of a waitlisted learner

- Given: ENR-3.
- When: `enroll("A")` again.
- Then: `already_waitlisted`. `waitlist` is still `["A", "B"]`.

### ENR-6. Prerequisite failure with seats open

- Given: CFG-1. L1 has no completed courses.
- When: `enroll("L1")`.
- Then: `ineligible`. Both lists stay empty. The call does not create a learner record: a following `drop("L1")` is `unknown_learner`.

### ENR-7. Prerequisite failure when the offering is full

- Given: ENR-2. L9 has no completed courses.
- When: `enroll("L9")`.
- Then: `ineligible`. `waitlist` stays `[]`. `enrolled` stays `["L1", "L2"]`.

### ENR-8. Enroll before configure

- Given: no offering.
- When: `enroll("L1")`.
- Then: `not_configured`. No offering is created.
- When: `enroll("")` or `enroll(" ")`.
- Then: `invalid_request`. A blank id is rejected before the offering check. `inspect()` is still `not_configured`.

### ENR-9. Blank id after configure

- Given: CFG-1.
- When: `enroll("")` or `enroll(" ")`.
- Then: `invalid_request`. Both lists stay empty.

### ENR-10. An open seat is taken by the caller, not by the waitlist

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["W1"]`, `seats_open 1`. W1 has completed `CS101`. L9 has completed `CS101` and is on neither list.
- When: `enroll("L9")`.
- Then: `enrolled`. `enrolled ["E1", "L9"]`. `waitlist ["W1"]`. `seats_open 0`. W1 is not promoted.

### ENR-11. Capacity zero waitlists an eligible learner

- Given: CFG-4, and L1 has completed `CS101`.
- When: `enroll("L1")`.
- Then: `waitlisted`. `enrolled []`. `waitlist ["L1"]`. `seats_open 0`.

### ENR-12. A course recorded before configure counts at enroll time

- Given: `record_completed_course("L1", "CS101")` returned `recorded`, then `configure("CS200", 1, "CS101")` returned `configured`.
- When: `enroll("L1")`.
- Then: `enrolled`. `enrolled ["L1"]`.

### ENR-13. After a drop, the same learner may enroll again

- Given: ENR-1, then `drop("L1")` returned `dropped` with `promoted_learner_id` null. L1 still has `CS101`.
- When: `enroll("L1")`.
- Then: `enrolled`. `enrolled ["L1"]`. The earlier drop did not create a second record; the learner was on neither list at this call.

## 4. Drop

A successful drop removes that learner and runs one promotion pass. Every other drop code changes nothing.

### DRP-1. Drop promotes the earliest eligible learner and leaves ineligible learners in order

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1", "E2"]`, `waitlist ["A", "B", "C", "D"]`. A and B have not completed `CS101`. C and D have.
- When: `drop("E2")`.
- Then: `dropped` with `promoted_learner_id "C"`. `enrolled ["E1", "C"]`. `waitlist ["A", "B", "D"]`. Capacity stays `2`. `seats_open 0`.

### DRP-2. One drop promotes only one waiter when several are eligible

- Given: DRP-1's offering before the drop.
- When: `drop("E1")`.
- Then: `promoted_learner_id` is `"C"`, not `"D"`. `waitlist` still contains `D`. `seats_open 0`.

### DRP-3. Drop with nobody eligible leaves the seat open

- Given: capacity `1`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["A", "B"]`. Neither A nor B has completed `CS101`.
- When: `drop("E1")`.
- Then: `dropped` with `promoted_learner_id` null. `enrolled []`. `waitlist ["A", "B"]`. `seats_open 1`.

### DRP-4. Drop with an empty waitlist

- Given: ENR-1.
- When: `drop("L1")`.
- Then: `dropped` with `promoted_learner_id` null. `enrolled []`. `waitlist []`. `seats_open 2`. L1's completion of `CS101` is still recorded.

### DRP-5. A drop runs one pass even if a seat was already open

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["W1"]`, `seats_open 1`. W1 has completed `CS101`.
- When: `drop("E1")`.
- Then: `dropped` with `promoted_learner_id "W1"`. `enrolled ["W1"]`. `waitlist []`. `seats_open 1`. W1 is promoted once, not twice.

### DRP-6. Drop by a waitlisted learner

- Given: ENR-3.
- When: `drop("A")`.
- Then: `waitlisted`. `enrolled ["L1", "L2"]`. `waitlist ["A", "B"]`. Capacity unchanged. Nobody is promoted.

### DRP-7. Duplicate drop

- Given: DRP-4, so L1 was enrolled and has already been dropped. L1's learner record still exists.
- When: `drop("L1")` again.
- Then: `not_enrolled`. `enrolled []`. `waitlist []`. `seats_open 2`.

### DRP-8. Unknown learner

- Given: CFG-1.
- When: `drop("nobody")`.
- Then: `unknown_learner`. Both lists stay empty. Capacity stays `2`.

### DRP-9. Known only through a completed course

- Given: CFG-1, and `record_completed_course("L1", "CS101")` returned `recorded`. L1 is on neither list.
- When: `drop("L1")`.
- Then: `not_enrolled`. Lists unchanged. L1's completed courses stay `{"CS101"}`.

### DRP-10. Blank id

- Given: no offering.
- When: `drop("")` or `drop(" ")`.
- Then: `invalid_request`. `inspect()` is still `not_configured`.
- Given instead: CFG-1 with L1 enrolled.
- When: `drop(" ")`.
- Then: `invalid_request`. L1 stays enrolled.

## 5. Concurrent enroll and drop

Threads call public methods on one `RegistrationService` and start together. The service lock is the only synchronization. After every thread joins, the invariants hold: `len(enrolled) <= capacity`, each learner id appears at most once across both lists, and never in both.

### CON-1. Two enrolls race for one open seat

- Given: capacity `1`, prerequisite `CS101`, both lists empty. P and Q have both completed `CS101`.
- When: two threads call `enroll("P")` and `enroll("Q")`.
- Then: the two results are `enrolled` and `waitlisted`, one each. One of P or Q is the sole enrolled learner. The other is the sole waitlist entry. Which one enrolled is not asserted. Capacity stays `1`. `seats_open 0`.

### CON-2. Two drops race for the same enrolled learner

- Given: capacity `1`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist ["W1"]`. W1 has completed `CS101`.
- When: two threads call `drop("E1")`.
- Then: one result is `dropped` with `promoted_learner_id "W1"`. The other is `not_enrolled`. Final `enrolled` is `["W1"]`. Final `waitlist` is `[]`. E1 is on neither list. Capacity stays `1`.

### CON-3. Two drops of different learners promote in FIFO order

- Given: capacity `2`, prerequisite `CS101`, `enrolled ["E1", "E2"]`, `waitlist ["A", "W1", "W2"]`. A has not completed `CS101`. W1 and W2 have.
- When: one thread calls `drop("E1")` and the other calls `drop("E2")`.
- Then: both results are `dropped`. Final `enrolled` is `["W1", "W2"]`. Final `waitlist` is `["A"]`. The enrolled order does not depend on which drop acquires the lock first, because each pass takes the earliest eligible waiter. Capacity stays `2`.

### CON-4. An enroll racing a drop ends in one of two serial results

- Given: capacity `1`, prerequisite `CS101`, `enrolled ["E1"]`, `waitlist []`. L2 has completed `CS101`.
- When: one thread calls `drop("E1")` and the other calls `enroll("L2")`.
- Then: final `enrolled` is `["L2"]` and final `waitlist` is `[]`. The returned pair is one of these, and no other:
  - drop's `promoted_learner_id` is null, and enroll returned `enrolled`
  - enroll returned `waitlisted`, and drop's `promoted_learner_id` is `"L2"`
- E1 is on neither list. Capacity stays `1`.
