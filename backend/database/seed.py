"""Seed the database with initial data."""

from sqlalchemy.orm import Session
from database.models import Doctor, DoctorSchedule, Patient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_database(db: Session):
    """Seed doctors and schedules if database is empty."""

    # Check if already seeded
    if db.query(Doctor).count() > 0:
        return

    # Create doctors
    doctors = [
        Doctor(
            name="Dr. Ahuja",
            specialty="General Physician",
            email="ahuja@mediconnect.com",
            phone="9876543210",
            bio="Dr. Ahuja is a highly experienced general physician with over 20 years of practice. Specializes in preventive medicine and comprehensive health assessments.",
            image_url="/images/doctor4.jpg"
        ),
        Doctor(
            name="Dr. Pyari",
            specialty="Cardiologist",
            email="pyari@mediconnect.com",
            phone="9876543211",
            bio="Dr. Pyari is a board-certified cardiologist with over 15 years of experience in treating cardiovascular diseases.",
            image_url="/images/doctor1.jpg"
        ),
        Doctor(
            name="Dr. Sendra",
            specialty="Neurologist",
            email="sendra@mediconnect.com",
            phone="9876543212",
            bio="Dr. Sendra is a renowned neurologist specializing in the diagnosis and treatment of nervous system disorders.",
            image_url="/images/doctor2.jpg"
        ),
        Doctor(
            name="Dr. Khushi",
            specialty="Pediatrician",
            email="khushi@mediconnect.com",
            phone="9876543213",
            bio="Dr. Khushi is a compassionate pediatrician dedicated to providing comprehensive healthcare for children.",
            image_url="/images/doctor3.jpg"
        ),
    ]

    for doc in doctors:
        db.add(doc)
    db.flush()

    # Create schedules for each doctor (Mon-Fri, 9 AM - 5 PM)
    for doc in doctors:
        for day in range(5):  # Monday=0 to Friday=4
            schedule = DoctorSchedule(
                doctor_id=doc.id,
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=60
            )
            db.add(schedule)

    # Create demo accounts
    demo_patient = Patient(
        name="Vinayak",
        email="vinayak@gmail.com",
        password_hash=pwd_context.hash("123"),
        phone="9999999999",
        role="patient"
    )
    db.add(demo_patient)

    demo_doctor = Patient(
        name="Dr. Ahuja",
        email="doctor@mediconnect.com",
        password_hash=pwd_context.hash("doctor123"),
        phone="9876543210",
        role="doctor"
    )
    db.add(demo_doctor)

    db.commit()
    print("✅ Database seeded with doctors, schedules, and demo accounts")
