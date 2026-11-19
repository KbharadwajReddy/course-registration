# Charter and Personas

Minimal in-memory Python service and command-line prototype for one course offering. This slice covers enrollment, drop, and FIFO waitlist promotion.

## Product Charter

### Objective

Give a learner a correct enroll and drop path for a single offering, and give an operator a correct capacity and waitlist outcome. When the offering is full, an eligible learner waits in arrival order. When a seat opens because a learner drops or the operator adds capacity, the earliest eligible waiter takes it.

The service keeps enrollment, capacity, and waitlist state in memory. The command-line interface is the way a person invokes those operations and reads the result.

### In-scope workflows

1. **Enroll.** A learner enrolls at most once. Enrollment succeeds when a seat is free and the learner has completed the offering's required course. When the offering is full, an eligible learner joins the waitlist once. A repeated enroll request leaves the existing enrollment or waitlist entry as it is.
2. **Drop.** An enrolled learner drops the offering. That frees one seat. A drop for anyone who is not enrolled returns a clear invalid result and changes nothing.
3. **FIFO promotion.** After a successful drop, the service offers that open seat to the earliest eligible learner on the waitlist. When the operator raises capacity, the service does the same once for each new seat. Promotion preserves arrival order among the people who remain waiting. Recording a completed course does not promote anyone.

### Out of scope

- Frontend
- Course catalog
- Payments
- Identity integrations
- Multi-term registration
- External database
- Configurable policy engine
- A second offering, or separate greenfield, brownfield, and ambiguous implementations

### Assumptions

- No starter repository was provided. The prototype is a small Python service with an in-memory store and a command-line interface.
- `Course-Registration-Rubric-Score.md` was not included. Acceptance checks follow the assessment statement. A scorecard rating is added only if that file arrives.
- There is one offering. The operator sets its capacity and its single required course code.
- The operator records which courses a learner has completed. Those records are the only input to the prerequisite rule.
- Promotion runs after a successful drop (one seat) and after a capacity increase (once per new seat). Completing the prerequisite does not by itself enroll a waiting learner. A seat that was already open stays open when a completion is recorded.
- Suggested effort for the whole assessment is 7–8 hours. This charter covers the behavior of the slice, not the later design spec, tests, or AI-use record.

## Personas

### Learner

A learner wants a seat in this offering, or wants to give one up.

- Enrolls when a seat is free and they have completed the required course.
- Joins the waitlist when the offering is full and they are eligible.
- Drops an enrollment they already hold.
- Receives a clear result when the request is a duplicate, they are ineligible, they are only waitlisted, or they are not enrolled.

A learner does not set capacity, change the required course, or edit another learner's completed courses.

### Course Coordinator / Operator

An operator is responsible for this offering's rules and for seeing what the service did.

- Sets the offering's capacity and its one required course code.
- Records a learner's completed courses, including the later completion that makes a waiting learner eligible.
- Inspects enrollment, remaining seats, and waitlist order, and reads the result of each enroll, drop, and promotion.

An operator does not enroll or drop on a learner's behalf in this slice. Those actions belong to the learner.

## Prerequisite and Waitlist Policy

### Prerequisite

The offering has one required course code. A learner is eligible only when that code is among their completed courses.

An ineligible learner is refused at enroll time. They do not take a seat, and they do not join the waitlist, whether or not the offering is full.

### Waitlist

The waitlist is a FIFO queue. Position follows the order in which eligible learners joined. Each learner occupies at most one waitlist entry.

A learner who is already enrolled, or already waiting, and asks to enroll again keeps that single record. The request does not add a second one.

### Ineligible learner at the front

When a seat opens, promotion walks the waitlist from the front:

- The earliest learner who has completed the required course is promoted into the seat and leaves the waitlist.
- A learner who has not completed the required course is skipped and stays waiting, in the same FIFO position.
- Learners behind a skipped learner are still considered. An ineligible learner does not block the queue.
- If nobody waiting is eligible, the seat stays open and every waiting learner stays in place.

The same rule applies if several ineligible learners are ahead of the first eligible one: each of them stays waiting, in order, and the first eligible learner is promoted.

### Becoming eligible while waiting

If the operator later records that a waiting learner has completed the required course, that learner becomes eligible and keeps their current FIFO position. That recording does not promote them, even if a seat is already open. They are promoted only on a later drop, or when the operator adds capacity, and only if they are then the earliest eligible person on the waitlist.

### Drop

Drop succeeds only for a learner who is currently enrolled. The enrollment is removed, one seat opens, and promotion runs once under the rule above.

A learner who is only on the waitlist is not enrolled. Dropping that learner is invalid: the waitlist entry stays, and capacity stays the same. A repeated drop, or a drop for an unknown learner, is also invalid and changes nothing.
