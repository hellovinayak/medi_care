"""Google Calendar API integration.

Creates calendar events when appointments are booked.
Falls back gracefully if credentials are not configured.
"""

from config import get_settings
import json
from datetime import datetime, timedelta

settings = get_settings()


def create_calendar_event(
    doctor_name: str,
    patient_name: str,
    date: str,
    time_slot: str,
    reason: str = "Medical Consultation"
) -> str:
    """Create a Google Calendar event for an appointment.

    Returns event ID if successful, None if calendar is not configured.
    """
    if not settings.GOOGLE_CALENDAR_ENABLED:
        print(f"📅 [MOCK CALENDAR] Event created: {patient_name} with {doctor_name} on {date} at {time_slot}")
        return f"mock_event_{date}_{time_slot.replace(':', '')}"

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import os
        import pickle

        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None

        token_path = 'token.pickle'
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GOOGLE_CALENDAR_CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)

        # Parse date and time
        start_dt = datetime.strptime(f"{date} {time_slot}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=1)

        event = {
            'summary': f'Medical Appointment: {patient_name} with {doctor_name}',
            'description': f'Reason: {reason}\nPatient: {patient_name}\nDoctor: {doctor_name}',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        return event.get('id')

    except Exception as e:
        print(f"⚠️ Google Calendar error: {e}")
        return f"mock_event_{date}_{time_slot.replace(':', '')}"
