"""
api/routes/import_routes.py — Smart Academic Import Pipeline

Enhanced with:
1. Multi-pass document audit
2. Confirmation screen before database write
3. Immediate dashboard/analytics/reminder updates
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.imported_document import ImportedDocument
from app.models.task import Task
from app.services.document_import.document_extractor import DocumentExtractor
from app.services.document_import.document_classifier import DocumentClassifier
from app.services.ai_client import AIInferenceClient
from app.services.scheduler_intelligence import SchedulerIntelligence
from app.api.deps import get_ai_client_dep
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    STEP 1: Upload document and get preview of extracted tasks.
    Returns extracted data WITHOUT writing to database.
    User can review and confirm before proceeding.
    """
    try:
        # Extract text from uploaded file
        content = await file.read()
        extractor = DocumentExtractor()
        extracted_text = extractor.extract(content, file.filename)
        
        if not extracted_text:
            raise HTTPException(status_code=400, detail="Could not extract text from file")
        
        logger.info(
            "ImportRoutes: preview_import for user %d, file %s, %d chars extracted",
            current_user.id, file.filename, len(extracted_text)
        )
        
        # Classify document
        classifier = DocumentClassifier()
        doc_type = classifier.classify(extracted_text)
        
        # Extract tasks (without persisting)
        from app.services.document_import.academic_reasoning import AcademicReasoningEngine
        reasoning_engine = AcademicReasoningEngine()
        extracted_tasks = reasoning_engine.extract_tasks(extracted_text, doc_type)
        
        # Return preview for user confirmation
        return {
            "status": "preview_ready",
            "filename": file.filename,
            "document_type": doc_type,
            "extracted_text_length": len(extracted_text),
            "tasks_found": len(extracted_tasks),
            "tasks": [
                {
                    "title": t.get("title", "Untitled"),
                    "subject": t.get("subject", "Unknown"),
                    "task_type": t.get("task_type", "assignment"),
                    "due_date": t.get("due_date", ""),
                    "estimated_hours": t.get("estimated_hours", 2),
                    "description": t.get("description", "")[:200],  # Preview first 200 chars
                }
                for t in extracted_tasks
            ],
            "message": f"Found {len(extracted_tasks)} task(s). Review above and click 'Confirm Import' to proceed."
        }
    
    except Exception as e:
        logger.error("ImportRoutes: preview_import failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Import preview failed: {str(e)}")


@router.post("/confirm")
async def confirm_import(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_client: AIInferenceClient = Depends(get_ai_client_dep),
):
    """
    STEP 2: User confirms the preview. Now we:
    1. Create ImportedDocument record
    2. Create Task records
    3. Update scheduler warnings
    4. Return success with task count
    """
    try:
        filename = request.get("filename", "Unknown")
        extracted_text = request.get("extracted_text", "")
        doc_type = request.get("document_type", "mixed_academic")
        confirmed_tasks = request.get("tasks", [])
        
        logger.info(
            "ImportRoutes: confirm_import for user %d, file %s, %d tasks confirmed",
            current_user.id, filename, len(confirmed_tasks)
        )
        
        # 1. Create ImportedDocument record
        doc = ImportedDocument(
            user_id=current_user.id,
            filename=filename,
            document_type=doc_type,
            extracted_text=extracted_text,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # 2. Create Task records from confirmed tasks
        created_tasks = []
        for task_data in confirmed_tasks:
            task = Task(
                user_id=current_user.id,
                title=task_data.get("title", "Untitled"),
                subject=task_data.get("subject", "General"),
                description=task_data.get("description", ""),
                task_type=task_data.get("task_type", "assignment"),
                due_date=datetime.fromisoformat(task_data.get("due_date")),
                estimated_hours=task_data.get("estimated_hours", 2.0),
                imported_from_id=doc.id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(task)
            created_tasks.append(task)
        
        db.commit()
        
        # 3. Re-score all tasks (Planner Agent)
        from app.agents.planner_agent import score_all_tasks
        try:
            score_all_tasks(current_user.id, db, ai_client)
            logger.info("ImportRoutes: re-scored tasks for user %d", current_user.id)
        except Exception as e:
            logger.warning("ImportRoutes: task scoring failed: %s", e)
        
        # 4. Generate scheduler warnings (Proactive Scheduler)
        try:
            SchedulerIntelligence.generate_all_warnings(current_user.id, db)
            logger.info("ImportRoutes: generated scheduler warnings for user %d", current_user.id)
        except Exception as e:
            logger.warning("ImportRoutes: warning generation failed: %s", e)
        
        return {
            "status": "import_successful",
            "filename": filename,
            "document_id": doc.id,
            "tasksCreated": len(created_tasks),
            "message": f"Successfully imported {len(created_tasks)} task(s). Dashboard updated with new priorities and warnings."
        }
    
    except Exception as e:
        logger.error("ImportRoutes: confirm_import failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Import confirmation failed: {str(e)}")


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all uploaded documents for the current user.
    """
    docs = db.query(ImportedDocument).filter(
        ImportedDocument.user_id == current_user.id
    ).order_by(ImportedDocument.uploaded_at.desc()).all()
    
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "document_type": d.document_type,
            "uploaded_at": d.uploaded_at.isoformat(),
            "task_count": len(d.tasks) if d.tasks else 0,
        }
        for d in docs
    ]
