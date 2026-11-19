"""In-memory enrollment, drop, and FIFO waitlist promotion for one offering."""

from __future__ import annotations

from threading import Lock

from registration.models import (
    ConfigureCode,
    ConfigureResult,
    DropCode,
    DropResult,
    EnrollCode,
    EnrollResult,
    InspectCode,
    InspectResult,
    LearnerRecord,
    Offering,
    OfferingSnapshot,
    RecordCode,
    RecordResult,
)


def _blank_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() == ""


class RegistrationService:
    """One offering. Public methods take the lock and return a result object."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._offering: Offering | None = None
        self._learners: dict[str, LearnerRecord] = {}

    def configure(
        self,
        offering_code: object,
        capacity: object,
        prerequisite_course_code: object,
    ) -> ConfigureResult:
        with self._lock:
            if (
                not isinstance(offering_code, str)
                or not isinstance(prerequisite_course_code, str)
                or _blank_text(offering_code)
                or _blank_text(prerequisite_course_code)
                or not isinstance(capacity, int)
                or isinstance(capacity, bool)
                or capacity < 0
            ):
                return ConfigureResult(code=ConfigureCode.INVALID_REQUEST)

            if self._offering is None:
                self._offering = Offering(
                    offering_code=offering_code,
                    capacity=capacity,
                    prerequisite_course_code=prerequisite_course_code,
                    enrolled=[],
                    waitlist=[],
                )
                return ConfigureResult(code=ConfigureCode.CONFIGURED)

            if offering_code != self._offering.offering_code:
                return ConfigureResult(code=ConfigureCode.OFFERING_MISMATCH)

            if capacity < len(self._offering.enrolled):
                return ConfigureResult(code=ConfigureCode.CAPACITY_BELOW_ENROLLMENT)

            old_capacity = self._offering.capacity
            self._offering.capacity = capacity
            self._offering.prerequisite_course_code = prerequisite_course_code
            promoted_count = 0
            if capacity > old_capacity:
                for _ in range(capacity - old_capacity):
                    if self._promote_one() is None:
                        break
                    promoted_count += 1
            return ConfigureResult(code=ConfigureCode.UPDATED, promoted_count=promoted_count)

    def enroll(self, learner_id: object) -> EnrollResult:
        with self._lock:
            if not isinstance(learner_id, str) or _blank_text(learner_id):
                return EnrollResult(code=EnrollCode.INVALID_REQUEST)
            if self._offering is None:
                return EnrollResult(code=EnrollCode.NOT_CONFIGURED)
            if learner_id in self._offering.enrolled:
                return EnrollResult(code=EnrollCode.ALREADY_ENROLLED)
            if learner_id in self._offering.waitlist:
                return EnrollResult(code=EnrollCode.ALREADY_WAITLISTED)
            if not self._is_eligible(learner_id):
                return EnrollResult(code=EnrollCode.INELIGIBLE)
            self._ensure_learner(learner_id)
            if self._seats_open() > 0:
                self._offering.enrolled.append(learner_id)
                return EnrollResult(code=EnrollCode.ENROLLED)
            self._offering.waitlist.append(learner_id)
            return EnrollResult(code=EnrollCode.WAITLISTED)

    def drop(self, learner_id: object) -> DropResult:
        with self._lock:
            if not isinstance(learner_id, str) or _blank_text(learner_id):
                return DropResult(code=DropCode.INVALID_REQUEST)
            if self._offering is not None and learner_id in self._offering.enrolled:
                self._offering.enrolled.remove(learner_id)
                return DropResult(code=DropCode.DROPPED, promoted_learner_id=self._promote_one())
            if self._offering is not None and learner_id in self._offering.waitlist:
                return DropResult(code=DropCode.WAITLISTED)
            if learner_id in self._learners:
                return DropResult(code=DropCode.NOT_ENROLLED)
            return DropResult(code=DropCode.UNKNOWN_LEARNER)

    def record_completed_course(self, learner_id: object, course_code: object) -> RecordResult:
        with self._lock:
            if (
                not isinstance(learner_id, str)
                or not isinstance(course_code, str)
                or _blank_text(learner_id)
                or _blank_text(course_code)
            ):
                return RecordResult(code=RecordCode.INVALID_REQUEST)
            record = self._learners.get(learner_id)
            if record is not None and course_code in record.completed_courses:
                return RecordResult(code=RecordCode.ALREADY_RECORDED)
            if record is None:
                record = LearnerRecord(learner_id=learner_id, completed_courses=set())
                self._learners[learner_id] = record
            record.completed_courses.add(course_code)
            return RecordResult(code=RecordCode.RECORDED)

    def inspect(self) -> InspectResult:
        with self._lock:
            if self._offering is None:
                return InspectResult(code=InspectCode.NOT_CONFIGURED)
            return InspectResult(
                code=InspectCode.OK,
                snapshot=OfferingSnapshot(
                    offering_code=self._offering.offering_code,
                    capacity=self._offering.capacity,
                    prerequisite_course_code=self._offering.prerequisite_course_code,
                    enrolled=list(self._offering.enrolled),
                    waitlist=list(self._offering.waitlist),
                    seats_open=self._seats_open(),
                ),
            )

    def completed_courses(self, learner_id: str) -> frozenset[str] | None:
        """Locked copy of a learner's completed courses, or None when no record exists."""
        with self._lock:
            record = self._learners.get(learner_id)
            if record is None:
                return None
            return frozenset(record.completed_courses)

    def _promote_one(self) -> str | None:
        """Move the earliest eligible waiter into an open seat. Caller holds the lock."""
        offering = self._offering
        if offering is None or len(offering.enrolled) >= offering.capacity:
            return None
        for index, learner_id in enumerate(offering.waitlist):
            if self._is_eligible(learner_id):
                offering.waitlist.pop(index)
                offering.enrolled.append(learner_id)
                return learner_id
        return None

    def _is_eligible(self, learner_id: str) -> bool:
        offering = self._offering
        if offering is None:
            return False
        return offering.prerequisite_course_code in self._completed(learner_id)

    def _completed(self, learner_id: str) -> set[str]:
        record = self._learners.get(learner_id)
        if record is None:
            return set()
        return record.completed_courses

    def _ensure_learner(self, learner_id: str) -> None:
        if learner_id not in self._learners:
            self._learners[learner_id] = LearnerRecord(
                learner_id=learner_id,
                completed_courses=set(),
            )

    def _seats_open(self) -> int:
        offering = self._offering
        if offering is None:
            return 0
        return offering.capacity - len(offering.enrolled)
