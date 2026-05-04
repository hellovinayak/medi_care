"""Script to delete ALL appointments from the database."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database.connection import SessionLocal
from database.models import Appointment

def clear_all_appointments():
    db = SessionLocal()
    try:
        count = db.query(Appointment).count()
        db.query(Appointment).delete()
        db.commit()
        print(f"✅ Successfully deleted {count} appointment(s) from the database.")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_appointments()
