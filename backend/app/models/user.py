"""
models/user.py — User account model.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Extended profile fields
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    custom_college = Column(String, nullable=True)
    department = Column(String, nullable=True)
    year = Column(String, nullable=True)
    preferences = Column(String, nullable=True)  # JSON-encoded user preferences
    date_of_birth = Column(Date, nullable=True)

    college_rel = relationship("College", foreign_keys=[college_id], lazy="joined")

    # Cascade relationships for clean deletion
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")
    learning_profiles = relationship("LearningProfile", back_populates="user", cascade="all, delete-orphan")
    imported_documents = relationship("ImportedDocument", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    tutor_sessions = relationship("TutorSession", back_populates="user", cascade="all, delete-orphan")
    question_citations = relationship("QuestionCitation", back_populates="user", cascade="all, delete-orphan")
    mistake_journals = relationship("MistakeJournal", back_populates="user", cascade="all, delete-orphan")
    study_notes = relationship("StudyNote", back_populates="user", cascade="all, delete-orphan")
    tutor_bookmarks = relationship("TutorBookmark", back_populates="user", cascade="all, delete-orphan")
    scheduler_preferences = relationship("SchedulerPreference", back_populates="user", cascade="all, delete-orphan")
    scheduler_warnings = relationship("SchedulerWarning", back_populates="user", cascade="all, delete-orphan")
    learning_objectives = relationship("LearningObjective", back_populates="user", cascade="all, delete-orphan")

    @property
    def college(self) -> str:
        if self.college_rel:
            return self.college_rel.college_name
        if self.custom_college:
            return self.custom_college
        return ""

