"""Insert ten validated sample requirements into the component database."""

from app.db import SessionLocal, init_models
from app.models import ValidatedRequirement


SAMPLE_REQUIREMENTS = [
    ("REQ-SAMPLE-0001", "education", "A learner can search for available tutors."),
    ("REQ-SAMPLE-0002", "education", "A learner can view a tutor's profile."),
    ("REQ-SAMPLE-0003", "education", "A learner can book an available tutoring slot."),
    ("REQ-SAMPLE-0004", "education", "A learner can cancel an upcoming tutoring session."),
    ("REQ-SAMPLE-0005", "education", "A tutor can publish available teaching slots."),
    ("REQ-SAMPLE-0006", "education", "A tutor can mark a booked session as completed."),
    ("REQ-SAMPLE-0007", "payments", "A learner can pay for a confirmed tutoring session."),
    ("REQ-SAMPLE-0008", "notifications", "A learner receives a reminder before a tutoring session."),
    ("REQ-SAMPLE-0009", "reporting", "An administrator can view tutoring session metrics."),
    ("REQ-SAMPLE-0010", "accessibility", "A learner can navigate the booking flow with a keyboard."),
]


def seed_sample_requirements() -> int:
    init_models()
    inserted = 0
    with SessionLocal() as session:
        existing_ids = {
            requirement_id
            for requirement_id, in session.query(ValidatedRequirement.id).filter(
                ValidatedRequirement.id.in_([item[0] for item in SAMPLE_REQUIREMENTS])
            )
        }
        for requirement_id, domain, text in SAMPLE_REQUIREMENTS:
            if requirement_id in existing_ids:
                continue
            session.add(
                ValidatedRequirement(
                    id=requirement_id,
                    project_id="PROJECT-SAMPLE",
                    domain=domain,
                    text=text,
                    context_text="Sample validated requirement for local development.",
                    validation_status="validated",
                )
            )
            inserted += 1
        session.commit()
    return inserted


if __name__ == "__main__":
    print(f"Inserted {seed_sample_requirements()} sample requirements.")
