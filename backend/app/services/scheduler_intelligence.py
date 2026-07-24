"""
services/scheduler_intelligence.py — Proactive Scheduler Intelligence

Monitors user's study habits and proactively generates warnings:
- Overloaded weeks (too many tasks)
- Conflicting deadlines (exams on same day)
- Streak breaks (no study sessions)
- Weak subject falling behind
- Large projects not started

All warnings are deterministic and based on real data.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.scheduler_warning import SchedulerWarning
from app.models.scheduler_preference import SchedulerPreference
from app.models.learning_profile import LearningProfile

logger = logging.getLogger(__name__)


class SchedulerIntelligence:
    """
    Proactive scheduler that generates warnings before problems occur.
    """

    @staticmethod
    def detect_overloaded_week(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Detect if any week has too many deadlines/tasks.
        Rule: >4 exams or >6 assignments in a single week = overload
        """
        warnings = []
        tasks = db.query(Task).filter(
            Task.user_id == user_id,
            Task.is_completed == False
        ).all()

        # Group by week
        weeks: Dict[str, List[Task]] = {}
        for task in tasks:
            week_start = (task.due_date - timedelta(days=task.due_date.weekday())).date()
            week_key = week_start.isoformat()
            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(task)

        # Check each week
        for week_key, week_tasks in weeks.items():
            exams = [t for t in week_tasks if t.task_type == "exam"]
            assignments = [t for t in week_tasks if t.task_type in ["assignment", "project"]]

            if len(exams) > 4 or len(assignments) > 6:
                msg = f"⚠️ **Overloaded Week**: {week_key} has {len(exams)} exams + {len(assignments)} assignments"
                action = "Consider rescheduling lower-priority assignments or requesting deadline extensions."
                task_ids = ",".join(str(t.id) for t in week_tasks)

                warning = SchedulerWarning(
                    user_id=user_id,
                    warning_type="overloaded_week",
                    message=msg,
                    severity="high" if len(exams) > 4 else "medium",
                    related_task_ids=task_ids,
                    suggested_action=action,
                )
                warnings.append(warning)

        return warnings

    @staticmethod
    def detect_conflicting_deadlines(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Detect multiple exams on the same day.
        Rule: >1 exam on same day = conflict
        """
        warnings = []
        exams = db.query(Task).filter(
            Task.user_id == user_id,
            Task.task_type == "exam",
            Task.is_completed == False
        ).all()

        # Group by date
        dates: Dict[str, List[Task]] = {}
        for exam in exams:
            date_key = exam.due_date.date().isoformat()
            if date_key not in dates:
                dates[date_key] = []
            dates[date_key].append(exam)

        # Check for conflicts
        for date_key, day_exams in dates.items():
            if len(day_exams) > 1:
                subjects = ", ".join(e.subject for e in day_exams)
                msg = f"⚠️ **Conflicting Deadlines**: {len(day_exams)} exams on {date_key}: {subjects}"
                action = "Contact your instructors to request a reschedule for one exam."
                task_ids = ",".join(str(t.id) for t in day_exams)

                warning = SchedulerWarning(
                    user_id=user_id,
                    warning_type="conflicting_deadlines",
                    message=msg,
                    severity="high",
                    related_task_ids=task_ids,
                    suggested_action=action,
                )
                warnings.append(warning)

        return warnings

    @staticmethod
    def detect_streak_break(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Warn if user hasn't studied in 2+ days.
        Rule: >2 days since last study session = streak at risk
        """
        warnings = []
        prefs = db.query(SchedulerPreference).filter(
            SchedulerPreference.user_id == user_id
        ).first()

        if not prefs or not prefs.last_study_date:
            # First time user or no recent study
            return warnings

        days_since_study = (datetime.now(timezone.utc) - prefs.last_study_date).days

        if days_since_study > 2:
            msg = f"🔥 **Streak at Risk**: No study session for {days_since_study} days. Current streak: {prefs.current_streak} days"
            action = "Start a study session today to maintain your streak!"

            warning = SchedulerWarning(
                user_id=user_id,
                warning_type="streak_break",
                message=msg,
                severity="medium",
                suggested_action=action,
            )
            warnings.append(warning)

        return warnings

    @staticmethod
    def detect_weak_subject_falling_behind(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Warn if weak subject has low mastery and upcoming deadlines.
        Rule: mastery <60% + deadline within 7 days = falling behind
        """
        warnings = []
        profiles = db.query(LearningProfile).filter(
            LearningProfile.user_id == user_id,
            LearningProfile.mastery < 60.0
        ).all()

        now = datetime.now(timezone.utc)
        for profile in profiles:
            # Find tasks for this subject
            tasks = db.query(Task).filter(
                Task.user_id == user_id,
                Task.subject == profile.subject,
                Task.is_completed == False,
            ).all()

            upcoming = [t for t in tasks if (t.due_date - now).days <= 7]

            if upcoming:
                msg = f"📉 **Weak Subject Alert**: {profile.subject} ({profile.topic}) has only {profile.mastery:.0f}% mastery with {len(upcoming)} deadline(s) coming up"
                action = f"Schedule a revision session for {profile.subject} in the next 24 hours."
                task_ids = ",".join(str(t.id) for t in upcoming)

                warning = SchedulerWarning(
                    user_id=user_id,
                    warning_type="weak_subject_falling_behind",
                    message=msg,
                    severity="high",
                    related_task_ids=task_ids,
                    suggested_action=action,
                )
                warnings.append(warning)

        return warnings

    @staticmethod
    def detect_large_project_not_started(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Warn if large project (>5 hours estimated) not started and deadline <7 days.
        Rule: estimated_hours >5 + 0% progress + <7 days = start now
        """
        warnings = []
        tasks = db.query(Task).filter(
            Task.user_id == user_id,
            Task.task_type.in_(["project", "assignment"]),
            Task.is_completed == False,
            Task.estimated_hours >= 5.0
        ).all()

        now = datetime.now(timezone.utc)
        for task in tasks:
            days_until_due = (task.due_date - now).days
            if 0 < days_until_due < 7:
                msg = f"⏰ **Large Project Not Started**: {task.title} ({task.estimated_hours:.1f}h estimated) due in {days_until_due} days"
                action = f"Start working on {task.title} today. With {task.estimated_hours:.1f} hours needed, you'll need ~{task.estimated_hours/days_until_due:.0f}h per day."

                warning = SchedulerWarning(
                    user_id=user_id,
                    warning_type="long_project_not_started",
                    message=msg,
                    severity="high",
                    related_task_ids=str(task.id),
                    suggested_action=action,
                )
                warnings.append(warning)

        return warnings

    @staticmethod
    def generate_all_warnings(user_id: int, db: Session) -> List[SchedulerWarning]:
        """
        Generate all proactive warnings for a user.
        Clear old dismissed warnings before generating new ones.
        """
        logger.info("SchedulerIntelligence: generating warnings for user %d", user_id)

        # Clear old dismissed warnings (older than 7 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        db.query(SchedulerWarning).filter(
            SchedulerWarning.user_id == user_id,
            SchedulerWarning.dismissed_at.isnot(None),
            SchedulerWarning.dismissed_at < cutoff
        ).delete()
        db.commit()

        # Collect all warning types
        all_warnings = []
        all_warnings.extend(SchedulerIntelligence.detect_overloaded_week(user_id, db))
        all_warnings.extend(SchedulerIntelligence.detect_conflicting_deadlines(user_id, db))
        all_warnings.extend(SchedulerIntelligence.detect_streak_break(user_id, db))
        all_warnings.extend(SchedulerIntelligence.detect_weak_subject_falling_behind(user_id, db))
        all_warnings.extend(SchedulerIntelligence.detect_large_project_not_started(user_id, db))

        # Persist new warnings
        for warning in all_warnings:
            existing = db.query(SchedulerWarning).filter(
                SchedulerWarning.user_id == user_id,
                SchedulerWarning.warning_type == warning.warning_type,
                SchedulerWarning.is_active == True,
            ).first()

            if not existing:
                db.add(warning)
                logger.info("SchedulerIntelligence: added warning %s for user %d", warning.warning_type, user_id)

        db.commit()
        return all_warnings
