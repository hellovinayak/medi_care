"""Doctor routes - list doctors and check availability."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from database.connection import get_db
from database.models import Doctor, DoctorSchedule, Appointment, AppointmentStatus
from datetime import datetime, date

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get("")
def get_doctors(
    specialty: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all doctors, optionally filtered by specialty."""
    query = db.query(Doctor)
    if specialty:
        query = query.filter(Doctor.specialty.ilike(f"%{specialty}%"))

    doctors = query.all()
    return {
        "doctors": [{
            "id": d.id,
            "name": d.name,
            "specialty": d.specialty,
            "email": d.email,
            "phone": d.phone,
            "bio": d.bio,
            "image_url": d.image_url
        } for d in doctors]
    }


@router.get("/{doctor_id}")
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get a specific doctor's details."""
    doctor = db.query(Doctor).get(doctor_id)
    if not doctor:
        return {"error": "Doctor not found"}

    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialty": doctor.specialty,
        "email": doctor.email,
        "phone": doctor.phone,
        "bio": doctor.bio,
        "image_url": doctor.image_url
    }


@router.get("/{doctor_id}/availability")
def get_availability(
    doctor_id: int,
    date_str: str,
    db: Session = Depends(get_db)
):
    """Get available time slots for a doctor on a specific date."""
    doctor = db.query(Doctor).get(doctor_id)
    if not doctor:
        return {"error": "Doctor not found"}

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

    day_of_week = target_date.weekday()

    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.day_of_week == day_of_week
    ).first()

    if not schedule:
        return {
            "doctor": doctor.name,
            "date": date_str,
            "available": False,
            "available_slots": [],
            "message": f"{doctor.name} does not work on {target_date.strftime('%A')}s"
        }

    # Generate slots
    start_hour = int(schedule.start_time.split(":")[0])
    end_hour = int(schedule.end_time.split(":")[0])
    all_slots = [f"{h:02d}:00" for h in range(start_hour, end_hour)]

    # Filter booked slots
    booked = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date == target_date,
        Appointment.status == AppointmentStatus.SCHEDULED
    ).all()
    booked_slots = {a.time_slot for a in booked}

    available = [s for s in all_slots if s not in booked_slots]

    return {
        "doctor": doctor.name,
        "date": date_str,
        "day": target_date.strftime("%A"),
        "available": len(available) > 0,
        "available_slots": available,
        "booked_slots": list(booked_slots)
    }
