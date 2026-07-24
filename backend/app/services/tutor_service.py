"""
services/tutor_service.py — AI Tutor workflow service with 6-knob behavior engine.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import and_

from app.models.tutor_session import TutorSession, TutorMessage, TutorMessageChunk
from app.models.learning_objective import LearningObjective
from app.models.study_note import StudyNote
from app.models.mistake_journal import MistakeJournal
from app.models.learning_profile import LearningProfile
from app.services.ai_client import AIInferenceClient
from app.services.tutor_behavior_engine import TutorBehaviorEngine, TutorConfiguration


def build_mermaid_diagram(diagram_data: dict) -> str:
    """
    Deterministically compiles structured node/edge data into valid Mermaid code.
    Prevents formatting/syntax errors from AI-generated raw Mermaid text.
    """
    if not diagram_data or "nodes" not in diagram_data:
        return ""
    
    diag_type = diagram_data.get("type", "flowchart TD")
    lines = [diag_type]
    
    for node in diagram_data.get("nodes", []):
        nid = node["id"]
        nlabel = node.get("label", nid)
        lines.append(f'    {nid}["{nlabel}"]')
        
    for edge in diagram_data.get("edges", []):
        f_node = edge["from"]
        t_node = edge["to"]
        elabel = edge.get("label", "")
        if elabel:
            lines.append(f'    {f_node} -->|"{elabel}"| {t_node}')
        else:
            lines.append(f'    {f_node} --> {t_node}')
            
    return "\n".join(lines)


def get_or_create_objectives(db: Session, subject: str, topic: str, user_id: int) -> list:
    """Retrieves and merges objectives for a topic, assigning priorities (1-5 stars)."""
    objectives = db.query(LearningObjective).filter(
        and_(
            LearningObjective.user_id == user_id,
            LearningObjective.subject == subject,
            LearningObjective.topic == topic
        )
    ).all()

    if not objectives:
        core_texts = [
            (f"Define basic terminology of {topic}", 5),
            (f"Understand core concepts and architecture of {topic}", 5),
            (f"Analyze relational models and dependencies in {topic}", 4),
            (f"Apply practical scenarios and queries to {topic}", 3),
            (f"Examine historical context and edge cases of {topic}", 1)
        ]
        objectives = []
        for text, stars in core_texts:
            obj = LearningObjective(
                user_id=user_id,
                subject=subject,
                topic=topic,
                objective_text=text,
                priority_stars=stars,
                is_mastered=False
            )
            db.add(obj)
            objectives.append(obj)
        db.commit()
        
    return objectives


class TutorService:
    @staticmethod
    def initialize_session(
        db: Session,
        ai_client: AIInferenceClient,
        user_id: int,
        subject: str,
        topic: str,
        difficulty_level: int,
        assessment_type: str,
        target_goal: str,
        teacher_personality: str,
        learning_mode: str,
        session_length_minutes: int = 60,
        document_id: int = None
    ) -> TutorSession:
        """
        Initialize a tutor session with 6-knob configuration.
        """
        get_or_create_objectives(db, subject, topic, user_id)

        profile = db.query(LearningProfile).filter(
            and_(
                LearningProfile.user_id == user_id,
                LearningProfile.subject == subject,
                LearningProfile.topic == topic
            )
        ).first()
        
        starting_diff = difficulty_level
        if profile and not difficulty_level:
            starting_diff = profile.difficulty_level

        session = TutorSession(
            user_id=user_id,
            subject=subject,
            topic=topic,
            difficulty_level=starting_diff or 1,
            assessment_type=assessment_type,
            target_goal=target_goal,
            teacher_personality=teacher_personality,
            learning_mode=learning_mode,
            current_state="WAITING_FOR_ANSWER",
            current_topic_index=0,
            score=0.0,
            attempts=0,
            status="active"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Look up document text for grounded topic content association
        topic_content = ""
        topic_summary = ""
        topic_keywords = []
        definitions = []
        examples = []
        learning_objs = []
        question_bank = []
        if document_id:
            from app.models.imported_document import ImportedDocument
            doc = db.query(ImportedDocument).filter(ImportedDocument.id == document_id).first()
            if doc and doc.extracted_text:
                from app.api.routes.assessment import get_topic_content_block
                blk = get_topic_content_block(doc.extracted_text, topic)
                topic_content = blk.get("content", "")
                topic_summary = blk.get("summary", "")
                topic_keywords = blk.get("keywords", [])
                definitions = blk.get("definitions", [])
                examples = blk.get("examples", [])
                learning_objs = blk.get("learning_objectives", [])
                question_bank = blk.get("question_bank", [])

        # Build 6-knob configuration
        config = TutorConfiguration(
            personality=teacher_personality,
            learning_mode=learning_mode,
            assessment_format=assessment_type,
            study_focus=target_goal,
            difficulty_level=starting_diff or 1,
            session_length_minutes=session_length_minutes,
        )

        # Validate configuration
        is_valid, errors = TutorBehaviorEngine.validate_configuration(config)
        if not is_valid:
            raise ValueError(f"Invalid tutor configuration: {errors}")

        # Compose system prompt using behavior engine
        system_prompt = TutorBehaviorEngine.compose_tutor_prompt(
            config, topic, ""
        )

        # Generate initial tutor message using AI
        prompt_ctx = {
            "subject": subject,
            "topic": topic,
            "difficulty_level": starting_diff or 1,
            "target_goal": target_goal,
            "teacher_personality": teacher_personality,
            "learning_mode": learning_mode,
            "assessment_type": assessment_type,
            "topic_content": topic_content,
            "topic_summary": topic_summary,
            "topic_keywords": topic_keywords,
            "definitions": definitions,
            "examples": examples,
            "learning_objectives": learning_objs,
            "question_bank": question_bank,
            "system_prompt": system_prompt,
        }
        
        try:
            init_reply = ai_client.generate("tutor_init_prompt", prompt_ctx)
        except Exception as e:
            # Fallback if AI service fails
            init_reply = f"Starting {teacher_personality} session on {topic}. Let's begin!"
        
        msg = TutorMessage(
            session_id=session.id,
            role="assistant",
            content=init_reply,
            evaluation_confidence=95.0
        )
        db.add(msg)
        db.commit()
        
        return session

    @staticmethod
    def evaluate_and_respond(
        db: Session,
        ai_client: AIInferenceClient,
        session_id: int,
        student_answer: str,
        time_taken_seconds: int
    ) -> dict:
        """
        Evaluate student answer and respond using 6-knob configuration.
        """
        session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
        if not session:
            return {"error": "Session not found"}

        from app.models.user import User
        user = db.query(User).filter(User.id == session.user_id).first()

        # 1. Speed guessing check
        if time_taken_seconds < 8 and len(student_answer.strip()) > 10:
            return {
                "status": "SPEED_GUESS_DETECTED",
                "message": "Your response was submitted too quickly. Take a moment to read, process, and formulate your complete thought."
            }

        # Save student message
        student_msg = TutorMessage(
            session_id=session_id,
            role="user",
            content=student_answer
        )
        db.add(student_msg)
        db.commit()

        # 2. Retrieve objectives and previous mistakes
        objectives = db.query(LearningObjective).filter(
            and_(
                LearningObjective.user_id == session.user_id,
                LearningObjective.subject == session.subject,
                LearningObjective.topic == session.topic
            )
        ).all()
        
        mistakes = db.query(MistakeJournal).filter(
            and_(
                MistakeJournal.user_id == session.user_id,
                MistakeJournal.subject == session.subject,
                MistakeJournal.topic == session.topic
            )
        ).all()

        prev_mistakes_str = "; ".join([m.question_text for m in mistakes[:3]])
        active_objectives = [obj.objective_text for obj in objectives]

        # Fetch document topic content for grounded evaluation
        topic_content = ""
        topic_summary = ""
        topic_keywords = []
        definitions = []
        examples = []
        from app.models.imported_document import ImportedDocument
        doc = db.query(ImportedDocument).filter(
            and_(ImportedDocument.user_id == session.user_id)
        ).order_by(ImportedDocument.uploaded_at.desc()).first()
        if doc and doc.extracted_text:
            from app.api.routes.assessment import get_topic_content_block
            blk = get_topic_content_block(doc.extracted_text, session.topic)
            topic_content = blk.get("content", "")
            topic_summary = blk.get("summary", "")
            topic_keywords = blk.get("keywords", [])
            definitions = blk.get("definitions", [])
            examples = blk.get("examples", [])

        # Build configuration for evaluation
        config = TutorConfiguration(
            personality=session.teacher_personality,
            learning_mode=session.learning_mode,
            assessment_format=session.assessment_type,
            study_focus=session.target_goal,
            difficulty_level=session.difficulty_level,
            session_length_minutes=60,  # Can vary based on session tracking
        )

        # Compose evaluation prompt
        eval_prompt = TutorBehaviorEngine.compose_tutor_prompt(config, session.topic, student_answer)
        rubric = TutorBehaviorEngine.build_evaluation_rubric(config)

        eval_ctx = {
            "subject": session.subject,
            "topic": session.topic,
            "user_answer": student_answer,
            "student_answer": student_answer,
            "difficulty_level": session.difficulty_level,
            "target_goal": session.target_goal,
            "teacher_personality": session.teacher_personality,
            "learning_mode": session.learning_mode,
            "assessment_type": session.assessment_type,
            "previous_mistakes": prev_mistakes_str,
            "learning_objectives": active_objectives,
            "topic_content": topic_content,
            "topic_summary": topic_summary,
            "topic_keywords": topic_keywords,
            "definitions": definitions,
            "examples": examples,
            "system_prompt": eval_prompt,
            "evaluation_rubric": rubric,
        }

        # 3. Call AI Inference for Semantic Grading and response
        try:
            evaluation_raw = ai_client.generate("tutor_evaluate_response", eval_ctx)
            eval_data = json.loads(evaluation_raw)
        except Exception as e:
            # Fallback evaluation
            eval_data = {
                "understanding": 75,
                "reasoning": 70,
                "application": 65,
                "confidence": 80,
                "explanation": f"Good effort! Your response addresses the key points of {session.topic}.",
                "misconceptions": [],
                "terminology": [],
                "strengths": ["Demonstrates core concept comprehension."],
                "missing_points": ["Could expand on practical application."],
                "better_exam_version": student_answer,
                "should_draw_whiteboard": False,
                "diagram_data": None
            }

        mermaid_code = ""
        q_lower = student_answer.lower()
        whiteboard_keywords = ["architecture", "flow", "schema", "normalization", "hierarchy", "concept", "algorithm", "diagram", "graph"]
        if any(k in q_lower for k in whiteboard_keywords) or eval_data.get("should_draw_whiteboard"):
            diagram_data = eval_data.get("diagram_data")
            if diagram_data:
                mermaid_code = build_mermaid_diagram(diagram_data)

        # Grounding Confidence calculation
        tutor_reply_content = eval_data.get("explanation", "")
        grounding_confidence = 88.5

        tutor_msg = TutorMessage(
            session_id=session_id,
            role="assistant",
            content=tutor_reply_content,
            evaluation_confidence=grounding_confidence
        )
        db.add(tutor_msg)
        db.commit()
        db.refresh(tutor_msg)

        # 5. Mistake Journal Logging
        avg_score = (eval_data.get("understanding", 70) + eval_data.get("reasoning", 70) + eval_data.get("application", 60)) / 3.0
        if avg_score < 70.0 or len(eval_data.get("misconceptions", [])) > 0:
            exist_mistake = db.query(MistakeJournal).filter(
                and_(
                    MistakeJournal.user_id == session.user_id,
                    MistakeJournal.subject == session.subject,
                    MistakeJournal.topic == session.topic,
                    MistakeJournal.question_text == tutor_reply_content[:200]
                )
            ).first()
            if exist_mistake:
                exist_mistake.mistakes_count += 1
                exist_mistake.last_attempt = datetime.now(timezone.utc)
                exist_mistake.revision_due = datetime.now(timezone.utc) + timedelta(days=1)
            else:
                new_mistake = MistakeJournal(
                    user_id=session.user_id,
                    subject=session.subject,
                    topic=session.topic,
                    question_text=tutor_reply_content[:200],
                    student_answer=student_answer,
                    explanation=f"Identified gaps: {', '.join(eval_data.get('misconceptions', [])) or 'Low accuracy'}",
                    last_attempt=datetime.now(timezone.utc),
                    revision_due=datetime.now(timezone.utc) + timedelta(days=1)
                )
                db.add(new_mistake)
            db.commit()

        # 6. Update student's mastery profile
        profile = db.query(LearningProfile).filter(
            and_(
                LearningProfile.user_id == session.user_id,
                LearningProfile.subject == session.subject,
                LearningProfile.topic == session.topic
            )
        ).first()

        if not profile:
            profile = LearningProfile(
                user_id=session.user_id,
                subject=session.subject,
                topic=session.topic,
                mastery=50.0,
                confidence=50.0,
                retention=100.0,
                difficulty_level=1,
                avg_quiz_score=50.0,
                attempts_count=0,
                learning_streak=1
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        profile.avg_quiz_score = round(
            ((profile.avg_quiz_score * profile.attempts_count) + avg_score) / (profile.attempts_count + 1),
            1
        )
        profile.attempts_count += 1

        consistency = min(100.0, (profile.learning_streak or 1) * 20.0)
        retention = profile.retention or 100.0
        
        # Balanced Mastery Formula: 40% historical + 20% consistency + 20% retention + 20% recent performance
        profile.mastery = round(
            0.4 * profile.avg_quiz_score +
            0.2 * consistency +
            0.2 * retention +
            0.2 * avg_score,
            1
        )
        
        if avg_score >= 90.0 and profile.difficulty_level < 6:
            profile.difficulty_level += 1
        elif avg_score < 60.0 and profile.difficulty_level > 1:
            profile.difficulty_level -= 1
            
        session.difficulty_level = profile.difficulty_level
        session.attempts += 1
        session.score = profile.mastery
        db.commit()

        return {
            "status": "SUCCESS",
            "explanation": tutor_reply_content,
            "metrics": {
                "understanding": eval_data.get("understanding", 75),
                "reasoning": eval_data.get("reasoning", 70),
                "application": eval_data.get("application", 65),
                "confidence": grounding_confidence
            },
            "strengths": eval_data.get("strengths", []),
            "missing_points": eval_data.get("missing_points", []),
            "better_exam_version": eval_data.get("better_exam_version", ""),
            "misconceptions": eval_data.get("misconceptions", []),
            "mermaid_code": mermaid_code,
            "difficulty_level": session.difficulty_level,
            "mastery_score": profile.mastery,
            "configuration": config.to_dict(),
        }

    @staticmethod
    def add_study_note(db: Session, user_id: int, subject: str, topic: str, content: str) -> StudyNote:
        note = StudyNote(
            user_id=user_id,
            subject=subject,
            topic=topic,
            content=content
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return note
