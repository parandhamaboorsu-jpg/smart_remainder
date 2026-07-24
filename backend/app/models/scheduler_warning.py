"""
models/scheduler_warning.py — Proactive Scheduler Warnings

Tracks warnings about overload, conflicts, streak breaks, etc.
Enables the scheduler to warn users BEFORE problems occur.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from app.core.database import Base
from sqlalchemy.orm import relationship


class SchedulerWarning(Base):
    __tablename__ = "scheduler_warnings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Warning types:
    # - "overloaded_week" — too many tasks in one week
    # - "conflicting_deadlines" — multiple exams same day
    # - "streak_break" — no study session for 2+ days
    # - "weak_subject_falling_behind" — low mastery in weak subject
    # - "long_project_not_started" — large project with 0 progress
    warning_type = Column(String, nullable=False, index=True)

    # Human-readable warning message
    message = Column(Text, nullable=False)

    # Severity: "low" | "medium" | "high"
    severity = Column(String, default="medium")

    # Is this warning still active?
    is_active = Column(Boolean, default=True)

    # When was this warning dismissed by user?
    dismissed_at = Column(DateTime, nullable=True)

    # Related task IDs (JSON: [1, 3, 5])
    related_task_ids = Column(String, default="")

    # Suggested action
    suggested_action = Column(Text, default="")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="scheduler_warnings")
