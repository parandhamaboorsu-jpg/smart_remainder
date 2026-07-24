"""
services/tutor_behavior_engine.py — 6-Control-Knob Tutor Behavior Engine

Implements the complete 6-dimensional tutor behavior system:
1. Personality (Socratic Tutor, Professor, Friendly Teacher, Interviewer, Exam Coach)
2. Learning Mode (Teach Me, Test Me, Challenge Me, Revise, Interview Me)
3. Assessment Format (Multiple Choice, True/False, Short Answer, Mixed)
4. Study Focus (GATE, Placement, Interview, College Exam, Semester, General Learning)
5. Difficulty Level (Beginner, Intermediate, Advanced, Adaptive)
6. Session Length (15 min, 30 min, 60 min, 90+ min)

Each configuration changes:
- Prompt instructions
- Tone & vocabulary
- Question difficulty & type
- Evaluation criteria
- Feedback style
- Response length
- Teaching methodology
"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TutorConfiguration:
    """Immutable 6-knob configuration."""
    personality: str  # "Socratic Tutor" | "Professor" | "Friendly Teacher" | "Interviewer" | "Exam Coach"
    learning_mode: str  # "Teach Me" | "Test Me" | "Challenge Me" | "Revise" | "Interview Me"
    assessment_format: str  # "Multiple Choice" | "True/False" | "Short Answer" | "Mixed"
    study_focus: str  # "GATE" | "Placement" | "Interview" | "College Exam" | "Semester" | "General Learning"
    difficulty_level: int  # 1-6 (Beginner to Advanced)
    session_length_minutes: int  # 15, 30, 60, 90+

    def to_dict(self) -> dict:
        return {
            "personality": self.personality,
            "learning_mode": self.learning_mode,
            "assessment_format": self.assessment_format,
            "study_focus": self.study_focus,
            "difficulty_level": self.difficulty_level,
            "session_length_minutes": self.session_length_minutes,
        }


class TutorBehaviorEngine:
    """
    Composes multi-dimensional tutor behavior from 6 independent knobs.
    Each configuration produces distinct prompt, tone, difficulty, and evaluation.
    """

    # ── Personality modifiers ────────────────────────────────────────────────
    PERSONALITY_PROFILES = {
        "Socratic Tutor": {
            "tone": "Questioning and exploratory",
            "vocabulary": "Moderate, accessible",
            "teaching_method": "Guide through questions, never directly answer",
            "opening": "Let's explore this together. What do you think happens when...",
            "evaluation_focus": "Conceptual understanding through reasoning",
            "hint_level": "Probing questions only, no direct hints",
            "correction_style": "Guide to correct answer through reflection",
            "feedback_tone": "Encouraging, thought-provoking",
        },
        "Professor": {
            "tone": "Formal and academic",
            "vocabulary": "Technical, precise terminology",
            "teaching_method": "Theory first, then practice",
            "opening": "Here's the formal definition and underlying theory:",
            "evaluation_focus": "Theoretical rigor and accuracy",
            "hint_level": "Textbook definitions, formal relationships",
            "correction_style": "Explain the correct theory and why student was wrong",
            "feedback_tone": "Objective, educationally thorough",
        },
        "Friendly Teacher": {
            "tone": "Warm and supportive",
            "vocabulary": "Simple, everyday language",
            "teaching_method": "Real-world examples first, then concepts",
            "opening": "Great question! Think of it like this everyday example...",
            "evaluation_focus": "Practical understanding and engagement",
            "hint_level": "Real-world analogies and relatable examples",
            "correction_style": "Celebrate effort, gently correct, provide alternatives",
            "feedback_tone": "Enthusiastic, supportive, celebratory",
        },
        "Interviewer": {
            "tone": "Professional and direct",
            "vocabulary": "Industry standard, precise",
            "teaching_method": "No teaching—only evaluation",
            "opening": "Tell me your understanding of this concept.",
            "evaluation_focus": "Can they communicate professional competence?",
            "hint_level": "Zero hints—must demonstrate readiness",
            "correction_style": "Provide structured feedback as interviewer would",
            "feedback_tone": "Professional, assessment-focused",
        },
        "Exam Coach": {
            "tone": "Focused and efficient",
            "vocabulary": "Exam-style, formula-based",
            "teaching_method": "Exam techniques and time management",
            "opening": "Here's the fastest way to solve this exam-style problem:",
            "evaluation_focus": "Marks, speed, exam technique",
            "hint_level": "Exam shortcuts and common answer patterns",
            "correction_style": "Show exam-winning approach and point allocation",
            "feedback_tone": "Direct, marks-focused, strategic",
        },
    }

    # ── Learning mode behaviors ──────────────────────────────────────────────
    LEARNING_MODE_PROFILES = {
        "Teach Me": {
            "sequence": ["explain", "example", "analogy", "checkpoint_q"],
            "explanation_depth": "Comprehensive with multiple perspectives",
            "starts_with": "Full explanation",
            "question_timing": "After explanation is complete",
            "pacing": "Thorough and detailed",
            "student_role": "Listener and responder",
        },
        "Test Me": {
            "sequence": ["question", "wait_for_answer", "evaluate", "explain"],
            "explanation_depth": "Provided only after answer submitted",
            "starts_with": "Direct question",
            "question_timing": "Immediately—no setup",
            "pacing": "Quick and active",
            "student_role": "Active problem solver",
        },
        "Challenge Me": {
            "sequence": ["complex_scenario", "multi_step_q", "evaluate", "explain"],
            "explanation_depth": "Minimal—student must reason deeply",
            "starts_with": "Real-world problem or edge case",
            "question_timing": "Immediately with context",
            "pacing": "Fast, demanding",
            "student_role": "Independent critical thinker",
        },
        "Revise": {
            "sequence": ["summary", "weak_q", "evaluate", "memory_refresh"],
            "explanation_depth": "Targeted to weak areas only",
            "starts_with": "Focused summary of topic",
            "question_timing": "On previously weak concepts",
            "pacing": "Medium—memory reinforcement",
            "student_role": "Active recaller and reinforcer",
        },
        "Interview Me": {
            "sequence": ["question", "wait_for_complete_answer", "evaluate", "structured_feedback"],
            "explanation_depth": "Professional feedback only",
            "starts_with": "Interview-style question",
            "question_timing": "One at a time, waiting for full response",
            "pacing": "Realistic interview pace",
            "student_role": "Professional candidate",
        },
    }

    # ── Assessment format profiles ───────────────────────────────────────────
    ASSESSMENT_FORMAT_PROFILES = {
        "Multiple Choice": {
            "format_instruction": "Q: [question]\nA) [plausible distractor]\nB) [plausible distractor]\nC) [correct]\nD) [plausible distractor]",
            "options_count": 4,
            "distractor_quality": "Pedagogically meaningful—target common misconceptions",
            "evaluation": "Option selection + reasoning for choice",
            "explanation": "Why correct? Why others wrong?",
        },
        "True/False": {
            "format_instruction": "Statement: [claim]\nTrue or False?\nWhy?",
            "options_count": 2,
            "distractor_quality": "Subtle reversal or edge case variation",
            "evaluation": "Boolean + reasoning",
            "explanation": "Precise boundary condition explanation",
        },
        "Short Answer": {
            "format_instruction": "[Open-ended question requiring 1-3 sentence answer]",
            "options_count": None,
            "distractor_quality": "N/A",
            "evaluation": "Key concepts present? Accuracy? Completeness?",
            "explanation": "Model answer + what was missing",
        },
        "Mixed": {
            "format_instruction": "Rotate: MCQ (40%), True/False (30%), Short Answer (30%)",
            "options_count": "Variable",
            "distractor_quality": "All applicable",
            "evaluation": "Format-specific rubric",
            "explanation": "Format-specific feedback",
        },
    }

    # ── Study focus profiles ──────────────────────────────────────────────────
    STUDY_FOCUS_PROFILES = {
        "GATE": {
            "difficulty_min": 4,
            "question_type": "Numerical, multi-step, edge cases",
            "rigor": "Very high—competitive difficulty",
            "question_source": "GATE previous years and mock papers",
            "evaluation_standard": "Exact answers, formula accuracy",
            "time_pressure": "Yes—simulate exam time limits",
            "feedback_focus": "Approach, time management, formula application",
        },
        "Placement": {
            "difficulty_min": 3,
            "question_type": "Real-world scenarios, system design, trade-offs",
            "rigor": "High—interview preparation",
            "question_source": "Top tech company interview patterns",
            "evaluation_standard": "Communication clarity, decision justification",
            "time_pressure": "Moderate—realistic interview pace",
            "feedback_focus": "Communication, technical depth, problem-solving process",
        },
        "Interview": {
            "difficulty_min": 3,
            "question_type": "Mix of HR and technical, behavioral questions",
            "rigor": "High—professional simulation",
            "question_source": "Realistic interview scenarios",
            "evaluation_standard": "Professionalism, communication, competence display",
            "time_pressure": "Yes—interview pace",
            "feedback_focus": "Professional communication, confidence, technical accuracy",
        },
        "College Exam": {
            "difficulty_min": 2,
            "question_type": "Unit-end problems, textbook-aligned",
            "rigor": "Medium—university curriculum",
            "question_source": "Course syllabus, previous year papers",
            "evaluation_standard": "Syllabus alignment, concept understanding",
            "time_pressure": "No—learning focus",
            "feedback_focus": "Conceptual gaps, course alignment, mastery",
        },
        "Semester": {
            "difficulty_min": 1,
            "question_type": "Concept understanding, foundational",
            "rigor": "Medium—semester progression",
            "question_source": "Lecture notes, textbook chapters",
            "evaluation_standard": "Learning objectives met?",
            "time_pressure": "No—thorough understanding",
            "feedback_focus": "Knowledge gaps, prerequisites to review",
        },
        "General Learning": {
            "difficulty_min": 1,
            "question_type": "Exploratory, discovery-based",
            "rigor": "Low—curiosity-driven",
            "question_source": "Any relevant material",
            "evaluation_standard": "Engagement and interest",
            "time_pressure": "No—relaxed",
            "feedback_focus": "Encouragement, interesting connections, curiosity",
        },
    }

    # ── Difficulty level scaling ─────────────────────────────────────────────
    DIFFICULTY_LEVELS = {
        1: {"name": "Beginner", "depth": "Definitions and basic recall", "context": "Isolated concepts"},
        2: {"name": "Beginner+", "depth": "Basic applications and examples", "context": "Single topic"},
        3: {"name": "Intermediate", "depth": "Problem-solving with multiple steps", "context": "Multiple related topics"},
        4: {"name": "Intermediate+", "depth": "Complex analysis and synthesis", "context": "Requires prior knowledge"},
        5: {"name": "Advanced", "depth": "Edge cases and non-standard scenarios", "context": "Cross-disciplinary"},
        6: {"name": "Advanced+", "depth": "Research-level insights and innovations", "context": "Novel applications"},
    }

    # ── Session length impact ────────────────────────────────────────────────
    SESSION_LENGTH_IMPACT = {
        15: {"questions_count": 1, "explanation_depth": "Minimal", "follow_ups": 0},
        30: {"questions_count": 2, "explanation_depth": "Brief", "follow_ups": 1},
        60: {"questions_count": 3, "explanation_depth": "Detailed", "follow_ups": 2},
        90: {"questions_count": 4, "explanation_depth": "Comprehensive", "follow_ups": 3},
    }

    @classmethod
    def compose_tutor_prompt(
        cls,
        config: TutorConfiguration,
        topic: str,
        user_answer: str = "",
    ) -> str:
        """
        Compose a multi-dimensional system prompt that respects all 6 knobs.
        Same configuration → same prompt every time (deterministic).
        """
        personality_profile = cls.PERSONALITY_PROFILES.get(config.personality, {})
        mode_profile = cls.LEARNING_MODE_PROFILES.get(config.learning_mode, {})
        format_profile = cls.ASSESSMENT_FORMAT_PROFILES.get(config.assessment_format, {})
        focus_profile = cls.STUDY_FOCUS_PROFILES.get(config.study_focus, {})
        difficulty_profile = cls.DIFFICULTY_LEVELS.get(config.difficulty_level, {})
        session_impact = cls.SESSION_LENGTH_IMPACT.get(config.session_length_minutes, {})

        prompt = f"""
### TUTOR BEHAVIOR CONFIGURATION (6-KNOB SYSTEM)

**Personality**: {config.personality}
- Tone: {personality_profile.get('tone', 'N/A')}
- Vocabulary Level: {personality_profile.get('vocabulary', 'N/A')}
- Teaching Method: {personality_profile.get('teaching_method', 'N/A')}
- Opening Style: {personality_profile.get('opening', 'N/A')}
- Feedback Tone: {personality_profile.get('feedback_tone', 'N/A')}

**Learning Mode**: {config.learning_mode}
- Sequence: {' → '.join(mode_profile.get('sequence', []))}
- Explanation Depth: {mode_profile.get('explanation_depth', 'N/A')}
- Starts With: {mode_profile.get('starts_with', 'N/A')}
- Pacing: {mode_profile.get('pacing', 'N/A')}

**Assessment Format**: {config.assessment_format}
- Format: {format_profile.get('format_instruction', 'N/A')}
- Evaluation Focus: {format_profile.get('evaluation', 'N/A')}

**Study Focus**: {config.study_focus}
- Difficulty Floor: Level {focus_profile.get('difficulty_min', 'N/A')}
- Question Type: {focus_profile.get('question_type', 'N/A')}
- Evaluation Standard: {focus_profile.get('evaluation_standard', 'N/A')}
- Time Pressure: {focus_profile.get('time_pressure', 'N/A')}

**Difficulty**: Level {config.difficulty_level} ({difficulty_profile.get('name', 'N/A')})
- Depth: {difficulty_profile.get('depth', 'N/A')}
- Context: {difficulty_profile.get('context', 'N/A')}

**Session Length**: {config.session_length_minutes} minutes
- Target Questions: {session_impact.get('questions_count', 'N/A')}
- Explanation Depth: {session_impact.get('explanation_depth', 'N/A')}
- Follow-up Depth: {session_impact.get('follow_ups', 'N/A')}

---

### TOPIC
{topic}

### STUDENT INPUT
{user_answer if user_answer else "[Awaiting student response]"}

### INSTRUCTION
Based on the 6-knob configuration above:
1. Generate response matching EXACTLY the personality, mode, format, and focus specified
2. Ensure tone and vocabulary match the personality profile
3. Follow the learning mode sequence
4. Adjust difficulty to Level {config.difficulty_level}
5. Allocate explanation depth based on session length
6. Evaluate using the study focus standard
7. Provide feedback in the personality's feedback tone

NEVER deviate from this configuration. Every dimension MUST be visible in your response.
"""
        return prompt

    @classmethod
    def build_evaluation_rubric(cls, config: TutorConfiguration) -> Dict[str, str]:
        """
        Build evaluation criteria based on study focus and personality.
        """
        focus_profile = cls.STUDY_FOCUS_PROFILES.get(config.study_focus, {})
        personality_profile = cls.PERSONALITY_PROFILES.get(config.personality, {})

        return {
            "evaluation_standard": focus_profile.get("evaluation_standard", "Concept understanding"),
            "feedback_focus": focus_profile.get("feedback_focus", "General feedback"),
            "evaluation_approach": personality_profile.get("evaluation_focus", "Comprehensive"),
            "correction_style": personality_profile.get("correction_style", "Neutral"),
        }

    @classmethod
    def validate_configuration(cls, config: TutorConfiguration) -> tuple[bool, List[str]]:
        """
        Validate that configuration uses only valid values.
        """
        errors = []

        valid_personalities = list(cls.PERSONALITY_PROFILES.keys())
        if config.personality not in valid_personalities:
            errors.append(f"Invalid personality: {config.personality}. Must be one of {valid_personalities}")

        valid_modes = list(cls.LEARNING_MODE_PROFILES.keys())
        if config.learning_mode not in valid_modes:
            errors.append(f"Invalid learning mode: {config.learning_mode}. Must be one of {valid_modes}")

        valid_formats = list(cls.ASSESSMENT_FORMAT_PROFILES.keys())
        if config.assessment_format not in valid_formats:
            errors.append(f"Invalid assessment format: {config.assessment_format}. Must be one of {valid_formats}")

        valid_focuses = list(cls.STUDY_FOCUS_PROFILES.keys())
        if config.study_focus not in valid_focuses:
            errors.append(f"Invalid study focus: {config.study_focus}. Must be one of {valid_focuses}")

        if not (1 <= config.difficulty_level <= 6):
            errors.append(f"Invalid difficulty level: {config.difficulty_level}. Must be 1-6")

        valid_lengths = list(cls.SESSION_LENGTH_IMPACT.keys())
        if config.session_length_minutes not in valid_lengths:
            errors.append(f"Invalid session length: {config.session_length_minutes}. Must be one of {valid_lengths}")

        return len(errors) == 0, errors

    @classmethod
    def get_valid_values(cls) -> Dict[str, List[str]]:
        """Return all valid values for each knob (for frontend UI)."""
        return {
            "personalities": list(cls.PERSONALITY_PROFILES.keys()),
            "learning_modes": list(cls.LEARNING_MODE_PROFILES.keys()),
            "assessment_formats": list(cls.ASSESSMENT_FORMAT_PROFILES.keys()),
            "study_focuses": list(cls.STUDY_FOCUS_PROFILES.keys()),
            "difficulty_levels": list(range(1, 7)),
            "session_lengths": list(cls.SESSION_LENGTH_IMPACT.keys()),
        }
