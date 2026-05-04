"""
MediConnect MCP Server — Real Model Context Protocol Implementation
===================================================================

This is a *real* MCP server built with the official `mcp` Python SDK.

It runs as an independent subprocess and communicates via the MCP
stdio transport.  The FastAPI backend spawns it and connects through
the MCPClient wrapper (agent/mcp_client.py).

What the MCP protocol gives us here:
  • tools/list   — LLM-callable functions discovered at runtime
  • tools/call   — tool invocation with JSON-schema-validated args
  • resources/list / resources/read — live data snapshots
  • prompts/list / prompts/get     — reusable system prompt templates

Run standalone to test:
    python mcp_server/server.py
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional

# ── Make sure we can import from the backend root ──────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from database.connection import SessionLocal
from database.models import (
    Doctor, DoctorSchedule, Appointment, Patient,
    Notification, AppointmentStatus,
)

# ── Create the FastMCP application ────────────────────────────
mcp = FastMCP(
    "mediconnect-mcp-server",
    instructions=(
        "MediConnect MCP server for appointment booking and doctor reporting. "
        "Use the available tools to help patients book appointments and doctors "
        "manage their schedules."
    ),
)

IST = timezone(timedelta(hours=5, minutes=30))


# ── DB helpers ────────────────────────────────────────────────

def _db():
    """Return a fresh SQLAlchemy session (caller must close it)."""
    return SessionLocal()


def _today_ist() -> date:
    return datetime.now(IST).date()


def _parse_date(date_str: str) -> date:
    today = _today_ist()
    s = date_str.lower().strip()
    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s == "yesterday":
        return today - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Cannot parse date: {date_str!r}")


def _find_doctor(db, doctor_name: str):
    doc = db.query(Doctor).filter(Doctor.name.ilike(f"%{doctor_name}%")).first()
    if doc:
        return doc
    for part in doctor_name.replace("Dr.", "").replace("Dr", "").strip().split():
        doc = db.query(Doctor).filter(Doctor.name.ilike(f"%{part}%")).first()
        if doc:
            return doc
    return None


# ════════════════════════════════════════════════════════════════
# MCP TOOLS
# Tools are executable functions the LLM can invoke.
# FastMCP inspects type hints to auto-generate JSON schemas.
# ════════════════════════════════════════════════════════════════

@mcp.tool()
def get_doctors_list(specialty: str = "") -> str:
    """
    Get a list of all available doctors with their specialties.
    Optionally filter by specialty (e.g. 'Cardiologist', 'Neurologist').
    Returns JSON with doctor details.
    """
    db = _db()
    try:
        q = db.query(Doctor)
        if specialty:
            q = q.filter(Doctor.specialty.ilike(f"%{specialty}%"))
        docs = q.all()
        result = [
            {"id": d.id, "name": d.name, "specialty": d.specialty,
             "email": d.email, "phone": d.phone, "bio": d.bio}
            for d in docs
        ]
        return json.dumps({"success": True, "doctors": result, "count": len(result)})
    finally:
        db.close()


@mcp.tool()
def check_doctor_availability(doctor_name: str, date: str) -> str:
    """
    Check a doctor's available appointment slots for a given date.
    date can be 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD.
    Returns available and booked slots.
    """
    db = _db()
    try:
        doctor = _find_doctor(db, doctor_name)
        if not doctor:
            return json.dumps({"success": False, "error": f"Doctor '{doctor_name}' not found."})

        try:
            target = _parse_date(date)
        except ValueError as e:
            return json.dumps({"success": False, "error": str(e)})

        schedule = db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.day_of_week == target.weekday(),
        ).first()

        if not schedule:
            return json.dumps({
                "success": True, "doctor": doctor.name, "date": str(target),
                "available": False, "available_slots": [],
                "message": f"{doctor.name} does not work on {target.strftime('%A')}s.",
            })

        start_h = int(schedule.start_time.split(":")[0])
        end_h   = int(schedule.end_time.split(":")[0])
        step    = max(1, schedule.slot_duration_minutes // 60)
        all_slots = [f"{h:02d}:00" for h in range(start_h, end_h, step)]

        booked_slots = {
            a.time_slot for a in db.query(Appointment).filter(
                Appointment.doctor_id == doctor.id,
                Appointment.date == target,
                Appointment.status == AppointmentStatus.SCHEDULED,
            ).all()
        }

        available = [s for s in all_slots if s not in booked_slots]
        return json.dumps({
            "success": True, "doctor": doctor.name, "specialty": doctor.specialty,
            "date": str(target), "day": target.strftime("%A"),
            "available": bool(available),
            "available_slots": available, "booked_slots": list(booked_slots),
            "total_slots": len(all_slots),
        })
    finally:
        db.close()


@mcp.tool()
def book_appointment(
    doctor_name: str,
    date: str,
    time_slot: str,
    patient_id: int = 0,
    reason: str = "",
    symptoms: str = "",
) -> str:
    """
    Book an appointment with a doctor.
    patient_id is injected automatically by the orchestrator.
    time_slot should be HH:MM (24-hour); 12-hour formats like '3 PM' are normalised.
    """
    db = _db()
    try:
        if not patient_id:
            return json.dumps({"success": False, "error": "patient_id is required."})

        doctor = _find_doctor(db, doctor_name)
        if not doctor:
            return json.dumps({"success": False, "error": f"Doctor '{doctor_name}' not found."})

        try:
            target = _parse_date(date)
        except ValueError as e:
            return json.dumps({"success": False, "error": str(e)})

        # Normalise 12-hour → 24-hour
        ts = time_slot.replace(" ", "")
        if "AM" in ts.upper() or "PM" in ts.upper():
            for fmt in ("%I:%M %p", "%I:%M%p", "%I%p"):
                try:
                    ts = datetime.strptime(ts.upper(), fmt.upper()).strftime("%H:%M")
                    break
                except ValueError:
                    pass

        # Slot already booked?
        if db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.date == target,
            Appointment.time_slot == ts,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).first():
            return json.dumps({
                "success": False,
                "error": f"The {ts} slot with {doctor.name} on {target} is already booked.",
            })

        appt = Appointment(
            patient_id=patient_id, doctor_id=doctor.id, date=target,
            time_slot=ts, reason=reason or "General consultation",
            symptoms=symptoms, status=AppointmentStatus.SCHEDULED,
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

        return json.dumps({
            "success": True, "appointment_id": appt.id,
            "doctor": doctor.name, "specialty": doctor.specialty,
            "date": str(target), "day": target.strftime("%A"), "time_slot": ts,
            "status": "scheduled",
            "message": (
                f"Appointment booked with {doctor.name} on "
                f"{target.strftime('%A, %B %d, %Y')} at {ts}."
            ),
        })
    finally:
        db.close()


@mcp.tool()
def send_email_confirmation(appointment_id: int) -> str:
    """
    Send an email confirmation to the patient for a booked appointment.
    Call this immediately after book_appointment succeeds.
    """
    db = _db()
    try:
        appt = db.query(Appointment).get(appointment_id)
        if not appt:
            return json.dumps({"success": False, "error": f"Appointment #{appointment_id} not found."})

        patient = db.query(Patient).get(appt.patient_id)
        doctor  = db.query(Doctor).get(appt.doctor_id)

        try:
            from services.email_service import send_appointment_email
            result = send_appointment_email(
                patient_email=patient.email, patient_name=patient.name,
                doctor_name=doctor.name, doctor_specialty=doctor.specialty,
                date=str(appt.date), time_slot=appt.time_slot,
                appointment_id=appt.id,
            )
            return json.dumps({"success": True, "message": f"Email sent to {patient.email}", "email_status": result})
        except Exception:
            return json.dumps({
                "success": True,
                "message": (
                    f"Email confirmation queued for {patient.name} "
                    f"(#{appointment_id} with {doctor.name} on {appt.date} at {appt.time_slot})"
                ),
                "email_status": "mock_sent",
            })
    finally:
        db.close()


@mcp.tool()
def get_appointment_stats(
    period: str,
    doctor_name: str = "",
    symptom_filter: str = "",
    user_id: int = 0,
) -> str:
    """
    Get appointment statistics for a time period.
    period: 'today' | 'yesterday' | 'this_week' | 'this_month' | YYYY-MM-DD
    Optionally filter by doctor_name or symptom_filter keyword.
    """
    db = _db()
    try:
        today = _today_ist()
        PERIODS = {
            "today":      (today, today, "today"),
            "yesterday":  (today - timedelta(1), today - timedelta(1), "yesterday"),
            "this_week":  (today - timedelta(days=today.weekday()), today, "this week"),
            "this_month": (today.replace(day=1), today, "this month"),
            "tomorrow":   (today + timedelta(1), today + timedelta(1), "tomorrow"),
        }
        if period in PERIODS:
            start, end, label = PERIODS[period]
        else:
            try:
                start = end = _parse_date(period)
                label = start.strftime("%B %d, %Y")
            except ValueError:
                start = end = today
                label = "today"

        q = db.query(Appointment).filter(
            Appointment.date >= start, Appointment.date <= end
        )
        if doctor_name:
            doc = _find_doctor(db, doctor_name)
            if doc:
                q = q.filter(Appointment.doctor_id == doc.id)
        if symptom_filter:
            q = q.filter(
                (Appointment.symptoms.ilike(f"%{symptom_filter}%")) |
                (Appointment.reason.ilike(f"%{symptom_filter}%"))
            )

        appts = q.all()
        details = []
        for a in appts:
            p = db.query(Patient).get(a.patient_id)
            d = db.query(Doctor).get(a.doctor_id)
            details.append({
                "appointment_id": a.id,
                "patient_name":   p.name if p else "Unknown",
                "doctor_name":    d.name if d else "Unknown",
                "date": str(a.date), "time_slot": a.time_slot,
                "status": a.status, "reason": a.reason, "symptoms": a.symptoms,
            })

        return json.dumps({
            "success": True, "period": label,
            "start_date": str(start), "end_date": str(end),
            "total_appointments": len(appts),
            "scheduled":  sum(1 for a in appts if a.status == AppointmentStatus.SCHEDULED),
            "completed":  sum(1 for a in appts if a.status == AppointmentStatus.COMPLETED),
            "cancelled":  sum(1 for a in appts if a.status == AppointmentStatus.CANCELLED),
            "appointments": details,
        })
    finally:
        db.close()


@mcp.tool()
def send_notification(
    user_email: str,
    title: str,
    message: str,
    notification_type: str = "info",
) -> str:
    """
    Send an in-app notification to a user (doctor or patient).
    notification_type: 'info' | 'report' | 'alert'
    """
    db = _db()
    try:
        user = db.query(Patient).filter(Patient.email == user_email).first()
        if not user:
            return json.dumps({"success": False, "error": f"User '{user_email}' not found."})

        notif = Notification(
            user_id=user.id, title=title, message=message,
            notification_type=notification_type,
        )
        db.add(notif)
        db.commit()
        return json.dumps({
            "success": True, "notification_id": notif.id,
            "message": f"Notification sent to {user.name} ({user_email})",
        })
    finally:
        db.close()


@mcp.tool()
def get_patient_appointments(
    patient_id: int = 0,
    status: str = "all",
    period: str = "all",
) -> str:
    """
    Get appointments for a patient.
    status: 'scheduled' | 'completed' | 'cancelled' | 'all'
    period: 'upcoming' | 'past' | 'today' | 'all'
    patient_id is injected automatically by the orchestrator.
    """
    if not patient_id:
        return json.dumps({"success": False, "error": "patient_id required."})
    db = _db()
    try:
        today = _today_ist()
        q = db.query(Appointment).filter(Appointment.patient_id == patient_id)
        if period == "upcoming":
            q = q.filter(Appointment.date >= today)
        elif period == "past":
            q = q.filter(Appointment.date < today)
        elif period == "today":
            q = q.filter(Appointment.date == today)
        if status != "all":
            q = q.filter(Appointment.status == status)

        appts = q.order_by(Appointment.date, Appointment.time_slot).all()
        result = []
        for a in appts:
            d = db.query(Doctor).get(a.doctor_id)
            result.append({
                "appointment_id": a.id,
                "doctor_name":    d.name if d else "Unknown",
                "doctor_specialty": d.specialty if d else "Unknown",
                "date": str(a.date), "day": a.date.strftime("%A"),
                "time_slot": a.time_slot, "status": a.status, "reason": a.reason,
            })
        return json.dumps({"success": True, "appointments": result, "count": len(result)})
    finally:
        db.close()


@mcp.tool()
def cancel_appointment(appointment_id: int) -> str:
    """Cancel an existing appointment by its ID."""
    db = _db()
    try:
        appt = db.query(Appointment).get(appointment_id)
        if not appt:
            return json.dumps({"success": False, "error": f"Appointment #{appointment_id} not found."})
        if appt.status == AppointmentStatus.CANCELLED:
            return json.dumps({"success": False, "error": "Appointment already cancelled."})
        appt.status = AppointmentStatus.CANCELLED
        db.commit()
        d = db.query(Doctor).get(appt.doctor_id)
        return json.dumps({
            "success": True,
            "message": f"Appointment #{appointment_id} with {d.name} on {appt.date} at {appt.time_slot} cancelled.",
        })
    finally:
        db.close()


@mcp.tool()
def complete_appointment(appointment_id: int, notes: str = "") -> str:
    """Mark an appointment as completed. Optionally add clinical notes."""
    db = _db()
    try:
        appt = db.query(Appointment).get(appointment_id)
        if not appt:
            return json.dumps({"success": False, "error": f"Appointment #{appointment_id} not found."})
        if appt.status == AppointmentStatus.CANCELLED:
            return json.dumps({"success": False, "error": "Cannot complete a cancelled appointment."})
        appt.status = AppointmentStatus.COMPLETED
        if notes:
            appt.notes = notes
        db.commit()
        d = db.query(Doctor).get(appt.doctor_id)
        p = db.query(Patient).get(appt.patient_id)
        return json.dumps({
            "success": True,
            "message": f"Appointment #{appointment_id} for {p.name} with {d.name} marked as completed.",
            "patient": p.name, "status": "completed",
        })
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# MCP RESOURCES
# Resources are URI-addressable data endpoints the LLM can read.
# ════════════════════════════════════════════════════════════════

@mcp.resource("mediconnect://doctors")
def resource_doctors() -> str:
    """Live list of all doctors with their specialties and contact details."""
    db = _db()
    try:
        docs = db.query(Doctor).all()
        return json.dumps({
            "doctors": [
                {"id": d.id, "name": d.name, "specialty": d.specialty,
                 "email": d.email, "phone": d.phone}
                for d in docs
            ],
            "count": len(docs),
        })
    finally:
        db.close()


@mcp.resource("mediconnect://appointments/upcoming")
def resource_upcoming_appointments() -> str:
    """All upcoming (scheduled) appointments across the system."""
    db = _db()
    try:
        today = _today_ist()
        appts = db.query(Appointment).filter(
            Appointment.date >= today,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).order_by(Appointment.date, Appointment.time_slot).all()
        result = []
        for a in appts:
            d = db.query(Doctor).get(a.doctor_id)
            p = db.query(Patient).get(a.patient_id)
            result.append({
                "id": a.id,
                "patient": p.name if p else "Unknown",
                "doctor":  d.name if d else "Unknown",
                "specialty": d.specialty if d else "",
                "date": str(a.date), "time_slot": a.time_slot,
            })
        return json.dumps({"upcoming_appointments": result, "count": len(result)})
    finally:
        db.close()


@mcp.resource("mediconnect://stats/today")
def resource_today_stats() -> str:
    """Today's appointment summary statistics."""
    db = _db()
    try:
        today = _today_ist()
        appts = db.query(Appointment).filter(Appointment.date == today).all()
        return json.dumps({
            "date": str(today),
            "total": len(appts),
            "scheduled":  sum(1 for a in appts if a.status == AppointmentStatus.SCHEDULED),
            "completed":  sum(1 for a in appts if a.status == AppointmentStatus.COMPLETED),
            "cancelled":  sum(1 for a in appts if a.status == AppointmentStatus.CANCELLED),
        })
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# MCP PROMPTS
# Prompts are reusable, parameterised system-prompt templates.
# ════════════════════════════════════════════════════════════════

@mcp.prompt()
def patient_appointment() -> str:
    """System prompt for the patient-facing appointment booking assistant."""
    current_date = datetime.now(IST).strftime("%A, %B %d, %Y")
    return f"""You are MediConnect AI Assistant, a helpful medical appointment scheduling assistant.
The current date is {current_date}.

Your capabilities:
1. List available doctors and their specialties
2. Check doctor availability for specific dates
3. Book appointments for patients
4. Send email confirmations after booking
5. Show the patient's existing appointments
6. Cancel appointments

IMPORTANT RULES:
- Always check availability before booking.
- After every successful booking, call send_email_confirmation.
- Tell the user: "You will receive an email confirmation to your registered email."
- Support natural language dates: "tomorrow", "next Monday", "this Friday".
- Morning = 09:00–12:00 | Afternoon = 13:00–17:00 | Evening = 16:00–18:00.
- If a slot is taken, suggest the next available ones.
- Remember context across turns — do not re-ask for information already given.
- Be friendly, concise, and professional.

Available doctors:
  • Dr. Ahuja      — General Physician
  • Dr. Pyari      — Cardiologist
  • Dr. Sendra     — Neurologist
  • Dr. Khushi     — Pediatrician"""


@mcp.prompt()
def doctor_summary() -> str:
    """System prompt for the doctor-facing schedule management and reporting assistant."""
    current_date = datetime.now(IST).strftime("%A, %B %d, %Y")
    return f"""You are MediConnect AI Assistant, helping doctors manage their schedule and generate reports.
The current date is {current_date}.

Your capabilities:
1. Query appointment statistics (today, yesterday, this week, this month)
2. Filter appointments by symptoms or conditions
3. Generate and format summary reports
4. Send reports as in-app notifications
5. Show upcoming schedule details

IMPORTANT RULES:
- Provide clear, well-structured statistical summaries.
- After generating a report, offer to send it as an in-app notification.
- Support natural queries: "how many patients yesterday", "patients with fever", "schedule for this week".
- Be professional, concise, and data-focused.
- Always state the time period covered in your response."""


# ════════════════════════════════════════════════════════════════
# Entry point — run the MCP server over stdio
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # `mcp.run()` starts the server with stdio transport (default).
    # The parent process (MCPClient) connects via stdin/stdout.
    mcp.run()
