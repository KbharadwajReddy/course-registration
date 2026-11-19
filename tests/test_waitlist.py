"""Pytest coverage for the CFG, REC, ENR, DRP, and CON intents."""

from __future__ import annotations

import io
import threading

from registration.cli import _format, run
from registration.models import (
    ConfigureCode,
    DropCode,
    EnrollCode,
    InspectCode,
    OfferingSnapshot,
    RecordCode,
)
from registration.service import RegistrationService


def assert_invariants(service: RegistrationService) -> None:
    inspected = service.inspect()
    if inspected.code == "not_configured":
        assert inspected.snapshot is None
        return
    snapshot = inspected.snapshot
    assert snapshot is not None
    assert 0 <= len(snapshot.enrolled) <= snapshot.capacity
    assert len(snapshot.enrolled) == len(set(snapshot.enrolled))
    assert len(snapshot.waitlist) == len(set(snapshot.waitlist))
    assert set(snapshot.enrolled).isdisjoint(snapshot.waitlist)
    assert snapshot.seats_open == snapshot.capacity - len(snapshot.enrolled)


def snapshot(service: RegistrationService) -> OfferingSnapshot:
    inspected = service.inspect()
    assert inspected.code == "ok"
    assert inspected.snapshot is not None
    assert_invariants(service)
    return inspected.snapshot


def complete(service: RegistrationService, learner_id: str, *course_codes: str) -> None:
    for course_code in course_codes:
        assert service.record_completed_course(learner_id, course_code).code == "recorded"


def configured(
    service: RegistrationService,
    capacity: int = 2,
    prerequisite: str = "CS101",
    offering_code: str = "CS200",
) -> RegistrationService:
    assert service.configure(offering_code, capacity, prerequisite).code == "configured"
    return service


# --- configure and inspect ---


def test_cfg_1_first_configure() -> None:
    service = RegistrationService()
    result = service.configure("CS200", 2, "CS101")
    assert result.code == "configured"
    state = snapshot(service)
    assert state.offering_code == "CS200"
    assert state.capacity == 2
    assert state.prerequisite_course_code == "CS101"
    assert state.enrolled == []
    assert state.waitlist == []
    assert state.seats_open == 2


def test_cfg_2_inspect_before_any_offering() -> None:
    inspected = RegistrationService().inspect()
    assert inspected.code == "not_configured"
    assert inspected.snapshot is None


def test_cfg_3_inspect_returns_a_copy() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    first = snapshot(service)
    first.enrolled.append("other")
    assert snapshot(service).enrolled == ["L1"]


def test_cfg_4_capacity_zero_is_valid() -> None:
    service = RegistrationService()
    assert service.configure("CS200", 0, "CS101").code == "configured"
    state = snapshot(service)
    assert state.capacity == 0
    assert state.seats_open == 0


def test_cfg_5_repeating_the_same_values() -> None:
    service = configured(RegistrationService())
    before = snapshot(service)
    result = service.configure("CS200", 2, "CS101")
    assert result.code == "updated"
    assert result.promoted_count == 0
    after = snapshot(service)
    assert after.capacity == before.capacity
    assert after.prerequisite_course_code == before.prerequisite_course_code
    assert after.enrolled == before.enrolled
    assert after.waitlist == before.waitlist


def test_cfg_6_capacity_increase_skips_ineligible_learners() -> None:
    service = configured(RegistrationService(), capacity=1, prerequisite="OLD")
    complete(service, "E1", "OLD")
    complete(service, "A", "OLD")
    complete(service, "B", "OLD", "CS101")
    complete(service, "C", "OLD", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    assert service.enroll("C").code == "waitlisted"
    switched = service.configure("CS200", 1, "CS101")
    assert switched.code == "updated"
    assert switched.promoted_count == 0
    given = snapshot(service)
    assert given.enrolled == ["E1"]
    assert given.waitlist == ["A", "B", "C"]
    assert "CS101" not in service.completed_courses("A")

    result = service.configure("CS200", 3, "CS101")
    assert result.code == "updated"
    assert result.promoted_count == 2
    state = snapshot(service)
    assert state.enrolled == ["E1", "B", "C"]
    assert state.waitlist == ["A"]
    assert state.capacity == 3
    assert state.seats_open == 0


def test_cfg_7_capacity_increase_does_not_fill_an_older_open_seat() -> None:
    service = configured(RegistrationService(), capacity=1, prerequisite="OLD")
    complete(service, "E1", "OLD")
    complete(service, "A", "OLD")
    complete(service, "B", "OLD")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    assert service.configure("CS200", 1, "CS999").promoted_count == 0
    opened = service.configure("CS200", 2, "CS999")
    assert opened.code == "updated"
    assert opened.promoted_count == 0
    assert service.record_completed_course("B", "CS999").code == "recorded"
    given = snapshot(service)
    assert given.capacity == 2
    assert given.enrolled == ["E1"]
    assert given.waitlist == ["A", "B"]
    assert given.seats_open == 1
    assert service.completed_courses("B") == frozenset({"OLD", "CS999"})
    assert "CS999" not in service.completed_courses("A")

    result = service.configure("CS200", 3, "CS999")
    assert result.code == "updated"
    assert result.promoted_count == 1
    state = snapshot(service)
    assert state.enrolled == ["E1", "B"]
    assert state.waitlist == ["A"]
    assert state.capacity == 3
    assert state.seats_open == 1


def test_cfg_8_capacity_decrease_does_not_promote() -> None:
    service = _eligible_waiter_with_open_seats()
    given = snapshot(service)
    assert given.capacity == 5
    assert given.seats_open == 3
    assert given.enrolled == ["E1", "E2"]
    assert given.waitlist == ["W1"]

    result = service.configure("CS200", 4, "CS101")
    assert result.code == "updated"
    assert result.promoted_count == 0
    state = snapshot(service)
    assert state.enrolled == ["E1", "E2"]
    assert state.waitlist == ["W1"]
    assert state.capacity == 4
    assert state.seats_open == 2


def test_cfg_9_decrease_down_to_current_enrollment() -> None:
    service = _eligible_waiter_with_open_seats()
    result = service.configure("CS200", 2, "CS101")
    assert result.code == "updated"
    assert result.promoted_count == 0
    state = snapshot(service)
    assert state.enrolled == ["E1", "E2"]
    assert state.waitlist == ["W1"]
    assert state.seats_open == 0


def test_cfg_10_capacity_below_enrollment_changes_nothing() -> None:
    service = configured(RegistrationService(), capacity=2)
    complete(service, "E1", "CS101")
    complete(service, "E2", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("E2").code == "enrolled"

    result = service.configure("CS200", 1, "CS201")
    assert result.code == "capacity_below_enrollment"
    state = snapshot(service)
    assert state.capacity == 2
    assert state.prerequisite_course_code == "CS101"
    assert state.enrolled == ["E1", "E2"]
    assert state.waitlist == []


def test_cfg_11_prerequisite_only_change_does_not_promote_or_remove() -> None:
    service = configured(RegistrationService(), capacity=1)
    complete(service, "E1", "CS101")
    complete(service, "W1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("W1").code == "waitlisted"

    result = service.configure("CS200", 1, "CS201")
    assert result.code == "updated"
    assert result.promoted_count == 0
    state = snapshot(service)
    assert state.prerequisite_course_code == "CS201"
    assert state.enrolled == ["E1"]
    assert state.waitlist == ["W1"]
    assert service.enroll("W1").code == "already_waitlisted"
    complete(service, "L9", "CS101")
    assert service.enroll("L9").code == "ineligible"
    assert snapshot(service).waitlist == ["W1"]
    assert snapshot(service).enrolled == ["E1"]


def test_cfg_12_capacity_increase_uses_the_new_prerequisite() -> None:
    service = configured(RegistrationService(), capacity=1, prerequisite="OLD")
    complete(service, "E1", "OLD", "CS101")
    complete(service, "W2", "OLD", "CS101")
    complete(service, "W1", "OLD", "CS201")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("W2").code == "waitlisted"
    assert service.enroll("W1").code == "waitlisted"
    assert service.configure("CS200", 1, "CS101").promoted_count == 0
    given = snapshot(service)
    assert given.enrolled == ["E1"]
    assert given.waitlist == ["W2", "W1"]

    result = service.configure("CS200", 2, "CS201")
    assert result.code == "updated"
    assert result.promoted_count == 1
    state = snapshot(service)
    assert state.prerequisite_course_code == "CS201"
    assert state.enrolled == ["E1", "W1"]
    assert state.waitlist == ["W2"]


def test_cfg_13_different_offering_code() -> None:
    service = configured(RegistrationService())
    complete(service, "E1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    before = snapshot(service)

    result = service.configure("CS300", 9, "CS201")
    assert result.code == "offering_mismatch"
    after = snapshot(service)
    assert after.offering_code == before.offering_code
    assert after.capacity == before.capacity
    assert after.prerequisite_course_code == before.prerequisite_course_code
    assert after.enrolled == before.enrolled
    assert after.waitlist == before.waitlist


def test_cfg_14_invalid_configure_wins_over_a_mismatched_code() -> None:
    service = configured(RegistrationService())
    complete(service, "E1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    before = snapshot(service)

    requests = [
        ("CS300", -1, "CS101"),
        ("", 2, "CS101"),
        ("CS200", -1, "CS101"),
        ("CS200", True, "CS101"),
        ("CS200", 1.5, "CS101"),
        ("CS200", 2, " "),
    ]
    for offering_code, capacity, prerequisite in requests:
        assert service.configure(offering_code, capacity, prerequisite).code == "invalid_request"
        after = snapshot(service)
        assert after.offering_code == before.offering_code
        assert after.capacity == before.capacity
        assert after.prerequisite_course_code == before.prerequisite_course_code
        assert after.enrolled == before.enrolled
        assert after.waitlist == before.waitlist


def test_cfg_15_mismatch_wins_over_capacity_below_enrollment() -> None:
    service = configured(RegistrationService(), capacity=2)
    complete(service, "E1", "CS101")
    complete(service, "E2", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("E2").code == "enrolled"
    before = snapshot(service)

    result = service.configure("OTHER", 0, "CS101")
    assert result.code == "offering_mismatch"
    assert result.code != "capacity_below_enrollment"
    after = snapshot(service)
    assert after.capacity == before.capacity
    assert after.enrolled == before.enrolled
    assert after.prerequisite_course_code == before.prerequisite_course_code


def test_cfg_16_first_configure_is_rejected_whole_when_invalid() -> None:
    service = RegistrationService()
    assert service.configure("", 2, "CS101").code == "invalid_request"
    assert service.configure("CS200", -1, "CS101").code == "invalid_request"
    inspected = service.inspect()
    assert inspected.code == "not_configured"
    assert inspected.snapshot is None


def _eligible_waiter_with_open_seats() -> RegistrationService:
    service = configured(RegistrationService(), capacity=2, prerequisite="OLD")
    complete(service, "E1", "OLD")
    complete(service, "E2", "OLD")
    complete(service, "W1", "OLD")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("E2").code == "enrolled"
    assert service.enroll("W1").code == "waitlisted"
    assert service.configure("CS200", 2, "CS101").promoted_count == 0
    opened = service.configure("CS200", 5, "CS101")
    assert opened.promoted_count == 0
    assert service.record_completed_course("W1", "CS101").code == "recorded"
    return service


# --- recording completed courses ---


def test_rec_1_record_before_an_offering_exists() -> None:
    service = RegistrationService()
    assert service.record_completed_course("L1", "CS101").code == "recorded"
    assert service.completed_courses("L1") == frozenset({"CS101"})
    assert service.inspect().code == "not_configured"


def test_rec_2_recording_again_is_a_no_op() -> None:
    service = RegistrationService()
    assert service.record_completed_course("L1", "CS101").code == "recorded"
    assert service.record_completed_course("L1", "CS101").code == "already_recorded"
    assert service.completed_courses("L1") == frozenset({"CS101"})


def test_rec_3_a_second_course_is_added() -> None:
    service = RegistrationService()
    assert service.record_completed_course("L1", "CS101").code == "recorded"
    assert service.record_completed_course("L1", "CS102").code == "recorded"
    assert service.completed_courses("L1") == frozenset({"CS101", "CS102"})


def test_rec_4_completing_the_prerequisite_does_not_promote() -> None:
    service = _waitlist_with_one_open_seat()
    given = snapshot(service)
    assert given.capacity == 2
    assert given.prerequisite_course_code == "CS101"
    assert given.enrolled == ["E1"]
    assert given.waitlist == ["W1", "W2"]
    assert given.seats_open == 1
    assert "CS101" not in service.completed_courses("W1")
    assert "CS101" in service.completed_courses("W2")

    result = service.record_completed_course("W1", "CS101")
    assert result.code == "recorded"
    assert "CS101" in service.completed_courses("W1")
    state = snapshot(service)
    assert state.enrolled == ["E1"]
    assert state.waitlist == ["W1", "W2"]
    assert state.seats_open == 1


def test_rec_5_an_unrelated_course_does_not_make_a_learner_eligible() -> None:
    service = configured(RegistrationService())
    assert service.record_completed_course("L1", "CS999").code == "recorded"
    assert service.enroll("L1").code == "ineligible"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert service.completed_courses("L1") == frozenset({"CS999"})


def test_rec_6_blank_arguments_do_not_create_a_learner() -> None:
    service = RegistrationService()
    assert service.record_completed_course("", "CS101").code == "invalid_request"
    assert service.record_completed_course("L1", "").code == "invalid_request"
    assert service.record_completed_course("L1", " ").code == "invalid_request"
    assert service.completed_courses("L1") is None
    assert service.drop("L1").code == "unknown_learner"


def _waitlist_with_one_open_seat() -> RegistrationService:
    service = configured(RegistrationService(), capacity=1, prerequisite="OLD")
    complete(service, "E1", "OLD")
    complete(service, "W1", "OLD")
    complete(service, "W2", "OLD")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("W1").code == "waitlisted"
    assert service.enroll("W2").code == "waitlisted"
    assert service.configure("CS200", 1, "CS101").promoted_count == 0
    assert service.drop("E1").promoted_learner_id is None
    opened = service.configure("CS200", 2, "CS101")
    assert opened.promoted_count == 0
    complete(service, "E1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    complete(service, "W2", "CS101")
    return service


# --- enroll ---


def test_enr_1_eligible_learner_takes_an_open_seat() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    state = snapshot(service)
    assert state.enrolled == ["L1"]
    assert state.waitlist == []
    assert state.seats_open == 1


def test_enr_2_second_eligible_learner_keeps_enrollment_order() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    complete(service, "L2", "CS101")
    assert service.enroll("L1").code == "enrolled"
    assert service.enroll("L2").code == "enrolled"
    state = snapshot(service)
    assert state.enrolled == ["L1", "L2"]
    assert state.waitlist == []
    assert state.seats_open == 0


def test_enr_3_full_offering_waitlists_in_arrival_order() -> None:
    service = _full_offering()
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    state = snapshot(service)
    assert state.enrolled == ["L1", "L2"]
    assert state.waitlist == ["A", "B"]
    assert state.seats_open == 0


def test_enr_4_duplicate_enroll_of_an_enrolled_learner() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    assert service.enroll("L1").code == "already_enrolled"
    state = snapshot(service)
    assert state.enrolled == ["L1"]
    assert state.waitlist == []


def test_enr_5_duplicate_enroll_of_a_waitlisted_learner() -> None:
    service = _full_offering()
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    assert service.enroll("A").code == "already_waitlisted"
    assert snapshot(service).waitlist == ["A", "B"]


def test_enr_6_prerequisite_failure_with_seats_open() -> None:
    service = configured(RegistrationService())
    assert service.enroll("L1").code == "ineligible"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert service.completed_courses("L1") is None
    assert service.drop("L1").code == "unknown_learner"


def test_enr_7_prerequisite_failure_when_full() -> None:
    service = _full_offering()
    assert service.enroll("L9").code == "ineligible"
    state = snapshot(service)
    assert state.waitlist == []
    assert state.enrolled == ["L1", "L2"]


def test_enr_8_enroll_before_configure() -> None:
    service = RegistrationService()
    missing = service.enroll("L1")
    assert missing.code is EnrollCode.NOT_CONFIGURED
    blank = service.enroll("")
    whitespace = service.enroll(" ")
    assert blank.code is EnrollCode.INVALID_REQUEST
    assert whitespace.code is EnrollCode.INVALID_REQUEST
    assert service.inspect().code is InspectCode.NOT_CONFIGURED


def test_enr_9_blank_id_after_configure() -> None:
    service = configured(RegistrationService())
    assert service.enroll("").code == "invalid_request"
    assert service.enroll(" ").code == "invalid_request"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []


def test_enr_10_open_seat_is_taken_by_the_caller_not_the_waitlist() -> None:
    service = _open_seat_with_eligible_waiter()
    given = snapshot(service)
    assert given.enrolled == ["E1"]
    assert given.waitlist == ["W1"]
    assert given.seats_open == 1
    complete(service, "L9", "CS101")

    assert service.enroll("L9").code == "enrolled"
    state = snapshot(service)
    assert state.enrolled == ["E1", "L9"]
    assert state.waitlist == ["W1"]
    assert state.seats_open == 0


def test_enr_11_capacity_zero_waitlists_an_eligible_learner() -> None:
    service = RegistrationService()
    assert service.configure("CS200", 0, "CS101").code == "configured"
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "waitlisted"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == ["L1"]
    assert state.seats_open == 0


def test_enr_12_a_course_recorded_before_configure_counts() -> None:
    service = RegistrationService()
    assert service.record_completed_course("L1", "CS101").code == "recorded"
    assert service.configure("CS200", 1, "CS101").code == "configured"
    assert service.enroll("L1").code == "enrolled"
    assert snapshot(service).enrolled == ["L1"]


def test_enr_13_after_a_drop_the_same_learner_may_enroll_again() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    dropped = service.drop("L1")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id is None
    assert service.completed_courses("L1") == frozenset({"CS101"})

    assert service.enroll("L1").code == "enrolled"
    assert snapshot(service).enrolled == ["L1"]


def _full_offering() -> RegistrationService:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    complete(service, "L2", "CS101")
    complete(service, "A", "CS101")
    complete(service, "B", "CS101")
    assert service.enroll("L1").code == "enrolled"
    assert service.enroll("L2").code == "enrolled"
    return service


def _open_seat_with_eligible_waiter() -> RegistrationService:
    service = configured(RegistrationService(), capacity=1)
    complete(service, "E1", "CS101")
    complete(service, "W1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("W1").code == "waitlisted"
    assert service.configure("CS200", 1, "CS999").promoted_count == 0
    assert service.configure("CS200", 2, "CS999").promoted_count == 0
    assert service.configure("CS200", 2, "CS101").promoted_count == 0
    return service


# --- drop ---


def test_drp_1_drop_skips_ineligible_learners_and_keeps_fifo_order() -> None:
    service = _two_enrolled_and_mixed_waitlist()
    dropped = service.drop("E2")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id == "C"
    state = snapshot(service)
    assert state.enrolled == ["E1", "C"]
    assert state.waitlist == ["A", "B", "D"]
    assert state.capacity == 2
    assert state.seats_open == 0


def test_drp_2_one_drop_promotes_only_one_waiter() -> None:
    service = _two_enrolled_and_mixed_waitlist()
    dropped = service.drop("E1")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id == "C"
    state = snapshot(service)
    assert "D" in state.waitlist
    assert state.seats_open == 0
    assert state.enrolled == ["E2", "C"]


def test_drp_3_drop_with_nobody_eligible_leaves_the_seat_open() -> None:
    service = configured(RegistrationService(), capacity=1, prerequisite="OLD")
    complete(service, "E1", "OLD")
    complete(service, "A", "OLD")
    complete(service, "B", "OLD")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    assert service.configure("CS200", 1, "CS101").promoted_count == 0

    dropped = service.drop("E1")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id is None
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == ["A", "B"]
    assert state.seats_open == 1


def test_drp_4_drop_with_an_empty_waitlist() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    dropped = service.drop("L1")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id is None
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert state.seats_open == 2
    assert service.completed_courses("L1") == frozenset({"CS101"})


def test_drp_5_a_drop_runs_one_pass_when_a_seat_is_already_open() -> None:
    service = _open_seat_with_eligible_waiter()
    dropped = service.drop("E1")
    assert dropped.code == "dropped"
    assert dropped.promoted_learner_id == "W1"
    state = snapshot(service)
    assert state.enrolled == ["W1"]
    assert state.waitlist == []
    assert state.seats_open == 1


def test_drp_6_drop_by_a_waitlisted_learner() -> None:
    service = _full_offering()
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    before = snapshot(service)
    dropped = service.drop("A")
    assert dropped.code == "waitlisted"
    assert dropped.promoted_learner_id is None
    state = snapshot(service)
    assert state.enrolled == ["L1", "L2"]
    assert state.waitlist == ["A", "B"]
    assert state.capacity == before.capacity


def test_drp_7_duplicate_drop() -> None:
    service = configured(RegistrationService())
    complete(service, "L1", "CS101")
    assert service.enroll("L1").code == "enrolled"
    assert service.drop("L1").code == "dropped"
    assert service.drop("L1").code == "not_enrolled"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert state.seats_open == 2
    assert service.completed_courses("L1") == frozenset({"CS101"})


def test_drp_8_unknown_learner() -> None:
    service = configured(RegistrationService())
    assert service.drop("nobody").code == "unknown_learner"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert state.capacity == 2


def test_drp_9_known_only_through_a_completed_course() -> None:
    service = configured(RegistrationService())
    assert service.record_completed_course("L1", "CS101").code == "recorded"
    assert service.drop("L1").code == "not_enrolled"
    state = snapshot(service)
    assert state.enrolled == []
    assert state.waitlist == []
    assert service.completed_courses("L1") == frozenset({"CS101"})


def test_drp_10_blank_id() -> None:
    service = RegistrationService()
    assert service.drop("").code == "invalid_request"
    assert service.drop(" ").code == "invalid_request"
    assert service.inspect().code == "not_configured"

    enrolled = configured(RegistrationService())
    complete(enrolled, "L1", "CS101")
    assert enrolled.enroll("L1").code == "enrolled"
    assert enrolled.drop(" ").code == "invalid_request"
    assert snapshot(enrolled).enrolled == ["L1"]


def _two_enrolled_and_mixed_waitlist() -> RegistrationService:
    service = configured(RegistrationService(), capacity=2, prerequisite="OLD")
    complete(service, "E1", "OLD", "CS101")
    complete(service, "E2", "OLD", "CS101")
    complete(service, "A", "OLD")
    complete(service, "B", "OLD")
    complete(service, "C", "OLD", "CS101")
    complete(service, "D", "OLD", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("E2").code == "enrolled"
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("B").code == "waitlisted"
    assert service.enroll("C").code == "waitlisted"
    assert service.enroll("D").code == "waitlisted"
    assert service.configure("CS200", 2, "CS101").promoted_count == 0
    state = snapshot(service)
    assert state.enrolled == ["E1", "E2"]
    assert state.waitlist == ["A", "B", "C", "D"]
    return service


# --- concurrency ---


def _race(calls: list[tuple[str, object]]) -> dict[str, object]:
    barrier = threading.Barrier(len(calls))
    results: dict[str, object] = {}

    def _call(name: str, action) -> None:
        barrier.wait()
        try:
            results[name] = action()
        except Exception as exc:
            results[name] = exc

    threads = [
        threading.Thread(target=_call, args=(name, action)) for name, action in calls
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    for result in results.values():
        if isinstance(result, Exception):
            raise result
    return results


def test_con_1_two_enrolls_race_for_one_open_seat() -> None:
    service = configured(RegistrationService(), capacity=1)
    complete(service, "P", "CS101")
    complete(service, "Q", "CS101")
    results = _race(
        [
            ("P", lambda: service.enroll("P")),
            ("Q", lambda: service.enroll("Q")),
        ]
    )
    codes = {results["P"].code, results["Q"].code}
    assert codes == {"enrolled", "waitlisted"}
    state = snapshot(service)
    assert state.capacity == 1
    assert state.seats_open == 0
    assert len(state.enrolled) == 1
    assert len(state.waitlist) == 1
    assert set(state.enrolled + state.waitlist) == {"P", "Q"}


def test_con_2_two_drops_race_for_the_same_learner() -> None:
    service = configured(RegistrationService(), capacity=1)
    complete(service, "E1", "CS101")
    complete(service, "W1", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("W1").code == "waitlisted"
    results = _race(
        [
            ("first", lambda: service.drop("E1")),
            ("second", lambda: service.drop("E1")),
        ]
    )
    dropped = [result for result in results.values() if result.code == "dropped"]
    refused = [result for result in results.values() if result.code == "not_enrolled"]
    assert len(dropped) == 1
    assert len(refused) == 1
    assert dropped[0].promoted_learner_id == "W1"
    state = snapshot(service)
    assert state.enrolled == ["W1"]
    assert state.waitlist == []
    assert "E1" not in state.enrolled
    assert "E1" not in state.waitlist
    assert state.capacity == 1


def test_con_3_two_drops_promote_in_fifo_order() -> None:
    service = _con_3_service()
    results = _race(
        [
            ("E1", lambda: service.drop("E1")),
            ("E2", lambda: service.drop("E2")),
        ]
    )
    assert results["E1"].code == "dropped"
    assert results["E2"].code == "dropped"
    state = snapshot(service)
    assert state.enrolled == ["W1", "W2"]
    assert state.waitlist == ["A"]
    assert state.capacity == 2


def _con_3_service() -> RegistrationService:
    service = configured(RegistrationService(), capacity=2, prerequisite="OLD")
    complete(service, "E1", "OLD", "CS101")
    complete(service, "E2", "OLD", "CS101")
    complete(service, "A", "OLD")
    complete(service, "W1", "OLD", "CS101")
    complete(service, "W2", "OLD", "CS101")
    assert service.enroll("E1").code == "enrolled"
    assert service.enroll("E2").code == "enrolled"
    assert service.enroll("A").code == "waitlisted"
    assert service.enroll("W1").code == "waitlisted"
    assert service.enroll("W2").code == "waitlisted"
    assert service.configure("CS200", 2, "CS101").promoted_count == 0
    state = snapshot(service)
    assert state.enrolled == ["E1", "E2"]
    assert state.waitlist == ["A", "W1", "W2"]
    assert "CS101" not in service.completed_courses("A")
    return service


def test_con_4_enroll_racing_a_drop() -> None:
    service = configured(RegistrationService(), capacity=1)
    complete(service, "E1", "CS101")
    complete(service, "L2", "CS101")
    assert service.enroll("E1").code == "enrolled"
    results = _race(
        [
            ("drop", lambda: service.drop("E1")),
            ("enroll", lambda: service.enroll("L2")),
        ]
    )
    state = snapshot(service)
    assert state.enrolled == ["L2"]
    assert state.waitlist == []
    assert "E1" not in state.enrolled
    assert "E1" not in state.waitlist
    assert state.capacity == 1
    drop_result = results["drop"]
    enroll_result = results["enroll"]
    serial_drop_first = drop_result.promoted_learner_id is None and enroll_result.code == "enrolled"
    serial_enroll_first = (
        enroll_result.code == "waitlisted" and drop_result.promoted_learner_id == "L2"
    )
    assert serial_drop_first or serial_enroll_first


def test_core_invariants_hold_across_a_mixed_sequence() -> None:
    service = RegistrationService()
    assert_invariants(service)
    configured(service, capacity=1)
    assert_invariants(service)
    complete(service, "L1", "CS101")
    complete(service, "L2", "CS101")
    assert service.enroll("L1").code == "enrolled"
    assert service.enroll("L2").code == "waitlisted"
    assert service.enroll("L1").code == "already_enrolled"
    assert service.enroll("L3").code == "ineligible"
    assert service.drop("L2").code == "waitlisted"
    assert service.drop("nobody").code == "unknown_learner"
    dropped = service.drop("L1")
    assert dropped.promoted_learner_id == "L2"
    assert service.record_completed_course("L2", "CS101").code == "already_recorded"
    assert service.configure("CS200", 1, "CS999").promoted_count == 0
    assert service.configure("OTHER", 0, "CS101").code == "offering_mismatch"
    assert service.configure("CS200", 0, "CS101").code == "capacity_below_enrollment"
    assert_invariants(service)
    state = snapshot(service)
    assert state.enrolled == ["L2"]
    assert state.waitlist == []
    assert state.prerequisite_course_code == "CS999"


def test_result_codes_are_enum_members() -> None:
    service = RegistrationService()
    assert service.configure("", 1, "CS101").code is ConfigureCode.INVALID_REQUEST
    assert service.record_completed_course("L1", "CS101").code is RecordCode.RECORDED
    assert service.drop("L1").code is DropCode.NOT_ENROLLED
    assert service.inspect().code is InspectCode.NOT_CONFIGURED
    configured(service, capacity=1)
    assert service.enroll("L1").code is EnrollCode.ENROLLED
    assert service.enroll("L1").code is EnrollCode.ALREADY_ENROLLED


def test_cli_format_uses_enum_value_not_qualified_name() -> None:
    class _QualifiedCode:
        value = "enrolled"

        def __str__(self) -> str:
            return "EnrollCode.ENROLLED"

    class _Result:
        code = _QualifiedCode()

    assert _format(_Result()) == "enrolled"
    assert "EnrollCode" not in _format(_Result())


def test_cli_prints_business_results_and_exits_0() -> None:
    stdin = io.StringIO(
        "\n".join(
            [
                "configure CS200 1 CS101",
                "complete L1 CS101",
                "enroll L1",
                "complete L2 CS101",
                "enroll L2",
                "drop L1",
                "inspect",
                "quit",
            ]
        )
        + "\n"
    )
    stdout = io.StringIO()
    assert run(stdin=stdin, stdout=stdout) == 0
    assert stdout.getvalue().splitlines() == [
        "configured",
        "recorded",
        "enrolled",
        "recorded",
        "waitlisted",
        "dropped promoted_learner_id=L2",
        "ok offering=CS200 capacity=1 prerequisite=CS101 enrolled=[L2] waitlist=[] seats_open=0",
    ]


def test_cli_exits_2_on_unparseable_input_without_calling_the_service() -> None:
    service = RegistrationService()
    stdout = io.StringIO()
    assert run(stdin=io.StringIO("enroll\n"), stdout=stdout, service=service) == 2
    assert stdout.getvalue().splitlines() == ["unparseable"]
    assert service.inspect().code == "not_configured"

    refused = io.StringIO()
    configured(service, capacity=1)
    assert run(stdin=io.StringIO("configure CS200 nope CS101\n"), stdout=refused, service=service) == 2
    assert refused.getvalue().splitlines() == ["unparseable"]
    assert snapshot(service).capacity == 1
    assert snapshot(service).enrolled == []
