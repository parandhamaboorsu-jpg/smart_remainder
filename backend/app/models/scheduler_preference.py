"""
models/scheduler_preference.py — Scheduler Preferences & Memory

Stores user's long-term study preferences and constraints.
Used by the Scheduler to make personalized decisions.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON
from app.core.database import Base
from sqlalchemy.orm import relationship


class SchedulerPreference(Base):
    __tablename__ = "scheduler_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Time preferences ─────────────────────────────────────────────────────
    # Days unavailable (JSON list: ["Sunday", "Monday", ...])
    unavailable_days = Column(JSON, default=[])

    # Preferred study time: "morning" | "afternoon" | "evening" | "flexible"
    preferred_study_time = Column(String, default="flexible")

    # Preferred session length in minutes: 30, 45, 60, 90, 120
    preferred_session_length_minutes = Column(Integer, default=60)

    # Busy hours (JSON: {"Monday": [{"start": "09:00", "end": "12:00"}]})
    busy_hours = Column(JSON, default={})

    # ── Study habits ─────────────────────────────────────────────────────────
    # Max sessions per day
    max_sessions_per_day = Column(Integer, default=6)

    # Break time between sessions (minutes)
    break_between_sessions = Column(Integer, default=15)

    # Long break after N sessions
    long_break_after_sessions = Column(Integer, default=4)

    # Long break duration (minutes)
    long_break_duration = Column(Integer, default=30)

    # ── Subject preferences ──────────────────────────────────────────────────
    # Weak subjects (JSON list: ["DBMS", "Networking", ...])
    weak_subjects = Column(JSON, default=[])

    # Strong subjects (JSON list)
    strong_subjects = Column(JSON, default=[])

    # Subject weightage preferences (JSON: {"DBMS": 1.5, "OS": 1.0})
    subject_weightage = Column(JSON, default={})

    # ── Reminders & notifications ───────────────────────────────────────────
    # How many days before deadline to start warning: 5, 3, 1
    deadline_warning_days = Column(Integer, default=3)

    # Reminder frequency: "daily", "weekly", "on_deadline_only"
    reminder_frequency = Column(String, default="daily")

    # ── Streak & motivation ──────────────────────────────────────────────────
    # Current study streak (days)
    current_streak = Column(Integer, default=0)

    # Last study session date
    last_study_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="scheduler_preferences")
