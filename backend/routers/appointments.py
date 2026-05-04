"""Appointment routes - CRUD operations for appointments."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database.connection import get_db
from database.models import Patient, Appointment, Doctor, AppointmentStatus
from routers.auth import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


class AppointmentCreate(BaseModel):
    doctor_id: int
    date: str  # YYYY-MM-DD
    time_slot: str  # HH:MM
    reason: str = ""
    symptoms: str = ""


@router.get("")
def get_appointments(
    status: Optional[str] = None,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get appointments for the current user."""
    query = db.query(Appointment)

    if current_user.role == "doctor":
        # Doctors see all appointments (or filter by their doctor record)
        doctor = db.query(Doctor).filter(Doctor.name == current_user.name).first()
        if doctor:
            query = query.filter(Appointment.doctor_id == doctor.id)
    else:
        query = query.filter(Appointment.patient_id == current_user.id)

    if status:
        query = query.filter(Appointment.status == status)

    appointments = query.order_by(Appointment.date.desc(), Appointment.time_slot).all()

    result = []
    for appt in appointments:
        doctor = db.query(Doctor).get(appt.doctor_id)
        patient = db.query(Patient).get(appt.patient_id)
        result.append({
            "id": appt.id,
            "doctor_name": doctor.name if doctor else "Unknown",
            "doctor_specialty": doctor.specialty if doctor else "",
            "patient_name": patient.name if patient else "Unknown",
            "date": str(appt.date),
            "time_slot": appt.time_slot,
            "status": appt.status,
            "reason": appt.reason,
            "symptoms": appt.symptoms,
            "created_at": appt.created_at.isoformat() if appt.created_at else None
        })

    return {"appointments": result, "count": len(result)}


@router.post("")
def create_appointment(
    request: AppointmentCreate,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Book an appointment (non-AI path)."""
    from datetime import datetime

    target_date = datetime.strptime(request.date, "%Y-%m-%d").date()

    # Check for conflicts
    existing = db.query(Appointment).filter(
        Appointment.doctor_id == request.doctor_id,
        Appointment.date == target_date,
        Appointment.time_slot == request.time_slot,
        Appointment.status == AppointmentStatus.SCHEDULED
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="This time slot is already booked")

    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=request.doctor_id,
        date=target_date,
        time_slot=request.time_slot,
        reason=request.reason,
        symptoms=request.symptoms,
        status=AppointmentStatus.SCHEDULED
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    doctor = db.query(Doctor).get(request.doctor_id)
    return {
        "success": True,
        "appointment_id": appointment.id,
        "doctor_name": doctor.name if doctor else "",
        "date": str(appointment.date),
        "time_slot": appointment.time_slot
    }


@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an appointment."""
    appointment = db.query(Appointment).get(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.patient_id != current_user.id and current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Not authorized")

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()

    return {"success": True, "message": "Appointment cancelled"}
@router.put("/{appointment_id}/status")
def update_appointment_status(
    appointment_id: int,
    status: str,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update appointment status (e.g., mark as completed)."""
    appointment = db.query(Appointment).get(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Only the doctor assigned to the appointment or the patient themselves can update status
    # In this app, we check if current user is a doctor
    if current_user.role != "doctor":
        # If not a doctor, check if it's the patient themselves (though usually doctors complete appointments)
        if appointment.patient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    if status not in [s.value for s in AppointmentStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")

    appointment.status = status
    db.commit()

    return {"success": True, "message": f"Appointment status updated to {status}"}
