# Course registration

In-memory Python service and command-line prototype for one course offering. A learner enrolls once when a seat is open and they have completed the offering's required course. When the offering is full, an eligible learner joins the waitlist once. Dropping an enrolled learner frees a seat and promotes the earliest eligible waiter. An ineligible waiter is skipped and keeps their FIFO place.

No starter repository was provided, and `Course-Registration-Rubric-Score.md` was not included. This prototype was implemented against the assessment acceptance criteria. There is no frontend, catalog, payments, identity integration, multi-term registration, external database, or configurable policy engine.

## Documents

- [Charter and personas](specs/charter-and-persona.md)
- [Architecture](specs/architecture.md)
- [Behavioral intents](specs/intent.md)
- [Runbook](RUNBOOK.md)
- [AI usage log](AI_USAGE_LOG.md)

Setup, the REPL, and pytest are in the runbook. From the repository root:

```powershell
python -m pip install pytest
python -m pytest tests/test_waitlist.py
python -m registration.cli
```

## Self-evaluation

| # | Acceptance criterion | Implementation | Tests |
|---|---|---|---|
| 1 | Enroll when a seat is open and the learner has completed the required course. | `RegistrationService.enroll` checks the prerequisite, then appends the learner when `seats_open > 0`. | `test_enr_1_eligible_learner_takes_an_open_seat`, `test_enr_2_second_eligible_learner_keeps_enrollment_order`, `test_enr_12_a_course_recorded_before_configure_counts` |
| 2 | A full offering waitlists an eligible learner once. A duplicate enroll does not create a second record. | Full capacity appends to the FIFO waitlist. Repeat calls return `already_enrolled` or `already_waitlisted` and leave both lists unchanged. | `test_enr_3_full_offering_waitlists_in_arrival_order`, `test_enr_4_duplicate_enroll_of_an_enrolled_learner`, `test_enr_5_duplicate_enroll_of_a_waitlisted_learner`, `test_enr_11_capacity_zero_waitlists_an_eligible_learner` |
| 3 | Dropping an enrolled learner opens a seat and promotes the earliest eligible waiter. | `drop` removes the learner and runs one private FIFO pass. Ineligible waiters stay in order. A capacity increase runs that pass once per new seat. | `test_drp_1_drop_skips_ineligible_learners_and_keeps_fifo_order`, `test_drp_2_one_drop_promotes_only_one_waiter`, `test_drp_5_a_drop_runs_one_pass_when_a_seat_is_already_open`, `test_cfg_6_capacity_increase_skips_ineligible_learners` |
| 4 | An ineligible learner is not enrolled or promoted. The skip-and-retain policy is consistent. | An ineligible enroll returns `ineligible` and writes neither list. Promotion skips an ineligible waiter and leaves them in FIFO order. Recording the prerequisite does not promote. | `test_enr_6_prerequisite_failure_with_seats_open`, `test_enr_7_prerequisite_failure_when_full`, `test_rec_4_completing_the_prerequisite_does_not_promote`, `test_rec_5_an_unrelated_course_does_not_make_a_learner_eligible`, `test_drp_3_drop_with_nobody_eligible_leaves_the_seat_open` |
| 5 | Invalid requests and duplicate drops return a clear result and do not corrupt state. | Refusals return result codes such as `invalid_request`, `waitlisted`, `not_enrolled`, `unknown_learner`, `offering_mismatch`, and `capacity_below_enrollment`. Those paths do not change enrollment, capacity, or the waitlist. | `test_cfg_14_invalid_configure_wins_over_a_mismatched_code`, `test_cfg_15_mismatch_wins_over_capacity_below_enrollment`, `test_drp_6_drop_by_a_waitlisted_learner`, `test_drp_7_duplicate_drop`, `test_drp_8_unknown_learner`, `test_drp_10_blank_id`, `test_enr_9_blank_id_after_configure`, `test_rec_6_blank_arguments_do_not_create_a_learner` |
| 6 | Tests cover open seats, a full offering, duplicates, FIFO promotion, prerequisite failure, invalid or repeated drops, and the lock. | `tests/test_waitlist.py` calls the in-memory service directly. No starter concurrency pattern existed, so the service uses one `threading.Lock` and the concurrency tests race public methods. | `CFG-*`, `REC-*`, `ENR-*`, and `DRP-*` tests, plus `test_con_1_two_enrolls_race_for_one_open_seat`, `test_con_2_two_drops_race_for_the_same_learner`, `test_con_3_two_drops_promote_in_fifo_order`, `test_con_4_enroll_racing_a_drop`, and `test_core_invariants_hold_across_a_mixed_sequence` |
| 7 | Use AI for at least one engineering activity and record the prompts, what was accepted, edited, or rejected, and how it was verified. | Charter, architecture, intents, and implementation were AI-assisted. Policy forks were answered before the specs were written. | [AI_USAGE_LOG.md](AI_USAGE_LOG.md) records each prompt, decision, and file. It includes the pytest run (54 passed) and the CLI checks (exit 0 and exit 2). |
