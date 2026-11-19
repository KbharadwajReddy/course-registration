"""Records and result objects for one course offering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConfigureCode(StrEnum):
    CONFIGURED = "configured"
    UPDATED = "updated"
    OFFERING_MISMATCH = "offering_mismatch"
    CAPACITY_BELOW_ENROLLMENT = "capacity_below_enrollment"
    INVALID_REQUEST = "invalid_request"


class EnrollCode(StrEnum):
    ENROLLED = "enrolled"
    WAITLISTED = "waitlisted"
    ALREADY_ENROLLED = "already_enrolled"
    ALREADY_WAITLISTED = "already_waitlisted"
    INELIGIBLE = "ineligible"
    NOT_CONFIGURED = "not_configured"
    INVALID_REQUEST = "invalid_request"


class DropCode(StrEnum):
    DROPPED = "dropped"
    WAITLISTED = "waitlisted"
    NOT_ENROLLED = "not_enrolled"
    UNKNOWN_LEARNER = "unknown_learner"
    INVALID_REQUEST = "invalid_request"


class RecordCode(StrEnum):
    RECORDED = "recorded"
    ALREADY_RECORDED = "already_recorded"
    INVALID_REQUEST = "invalid_request"


class InspectCode(StrEnum):
    OK = "ok"
    NOT_CONFIGURED = "not_configured"


@dataclass
class Offering:
    offering_code: str
    capacity: int
    prerequisite_course_code: str
    enrolled: list[str]
    waitlist: list[str]


@dataclass
class LearnerRecord:
    learner_id: str
    completed_courses: set[str]


@dataclass(frozen=True)
class ConfigureResult:
    code: ConfigureCode
    promoted_count: int | None = None


@dataclass(frozen=True)
class EnrollResult:
    code: EnrollCode


@dataclass(frozen=True)
class DropResult:
    code: DropCode
    promoted_learner_id: str | None = None


@dataclass(frozen=True)
class RecordResult:
    code: RecordCode


@dataclass(frozen=True)
class OfferingSnapshot:
    offering_code: str
    capacity: int
    prerequisite_course_code: str
    enrolled: list[str]
    waitlist: list[str]
    seats_open: int


@dataclass(frozen=True)
class InspectResult:
    code: InspectCode
    snapshot: OfferingSnapshot | None = None
