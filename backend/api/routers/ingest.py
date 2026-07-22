from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from models.pending_tip import PendingTip
import traceback

from requests import request  # <--- Added to reveal hidden errors!

from services.ingest_synthetic_pdfs import ingest_uploaded_pdf
from services.query_pipeline import pipeline
from services.imagekit_client import upload_file_bytes
from services.ingest_tips import process_tip

router = APIRouter()

class IngestResponse(BaseModel):
    filename: str
    chunks_ingested: int
    url: str | None = None

class QueryRequest(BaseModel):
    query: str
    role: str | int = "Field Technician"

@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf_from_frontend(file: UploadFile = File(...)):
    """Accept a PDF upload from the frontend and ingest it into Neo4j."""
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # 1. Upload file to ImageKit
    try:
        print(f"Uploading {file.filename} to ImageKit...")
        ik_res = upload_file_bytes(file_bytes, file.filename or "upload.pdf")
        ik_url = ik_res.url
        print(f"Successfully uploaded to ImageKit. URL: {ik_url}")
    except Exception as e:
        print(f"Error uploading to ImageKit: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload PDF to ImageKit: {str(e)}"
        )

    # 2. Parse using LlamaParse and ingest into Neo4j
    ingest_result = await ingest_uploaded_pdf(file_bytes, file.filename or "upload.pdf", url=ik_url)

    return {
        "filename": file.filename or "upload.pdf",
        "chunks_ingested": ingest_result.get("count", 0),
        "url": ik_url,
    }
    
# FIX: Re-add async to the alias endpoint
@router.post("/ask_omniplant")
async def ask_omniplant(request: QueryRequest = Body(...)):
    """Backward-compatible alias for the chat endpoint."""
    return await query_pdf_from_frontend(request)

# FIX: Re-add async to the primary query endpoint
@router.post("/query")
async def query_pdf_from_frontend(request: QueryRequest = Body(...)):
    """Accept a query from the frontend and return the answer."""
    try:
        print(f"Executing pipeline for query: '{request.query}' with role: '{request.role}'")
        
        role_name = request.role if isinstance(request.role, str) else str(request.role)
        if role_name.isdigit():
            role_name = "Plant Manager" if int(role_name) >= 2 else "Field Technician"

        # FIX: Explicitly await the coroutine so it returns the actual string response!
        answer = pipeline(request.query, role_name)

        if answer is None:
            raise HTTPException(
                status_code=404,
                detail="No answer could be generated."
            )

        return {"answer": answer}

    except Exception as e:
        print("\n--- CRITICAL PIPELINE CRASH ---")
        traceback.print_exc()
        print("-------------------------------\n")
        
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the query: {str(e)}"
        )
        
        

from fastapi import APIRouter, Body, HTTPException, status
import traceback

@router.post("/add_tip")
async def add_tip_pending(request: dict = Body(...), db: Session = Depends(get_db)):
    employee = request.get("employee")
    tip = request.get("tip")

    if not employee or not employee.get("id") or not employee.get("name"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid employee information (id, name) is required."
        )

    if not tip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tip is required."
        )

    try:
        new_tip = PendingTip(
            employee_id=employee["id"],
            employee_name=employee["name"],
            tip_text=tip,
            status="Pending"
        )
        db.add(new_tip)
        db.commit()
        db.refresh(new_tip)

        return {
            "success": True,
            "message": "Tip submitted for approval",
            "tip_id": new_tip.id
        }
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add tip: {str(e)}"
        )

@router.get("/all_tips")
async def get_all_tips(db: Session = Depends(get_db)):
    tips = db.query(PendingTip).order_by(PendingTip.created_at.desc()).all()
    return [{
        "id": t.id,
        "employee_id": t.employee_id,
        "employee_name": t.employee_name,
        "tip_text": t.tip_text,
        "approvals_count": t.approvals_count,
        "approved_by": t.approved_by,
        "status": t.status,
        "created_at": t.created_at
    } for t in tips]

@router.get("/my_tips/{employee_id}")
async def get_my_tips(employee_id: str, db: Session = Depends(get_db)):
    tips = db.query(PendingTip).filter(PendingTip.employee_id == employee_id).order_by(PendingTip.created_at.desc()).all()
    return [{
        "id": t.id,
        "employee_id": t.employee_id,
        "employee_name": t.employee_name,
        "tip_text": t.tip_text,
        "approvals_count": t.approvals_count,
        "approved_by": t.approved_by,
        "status": t.status,
        "created_at": t.created_at
    } for t in tips]

@router.post("/approve_tip")
async def approve_tip(request: dict = Body(...), db: Session = Depends(get_db)):
    tip_id = request.get("tip_id")
    approver_id = request.get("approver_id")

    if not tip_id or not approver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tip_id and approver_id are required."
        )

    tip = db.query(PendingTip).filter(PendingTip.id == tip_id).first()
    if not tip:
        raise HTTPException(status_code=404, detail="Tip not found.")

    if tip.status != "Pending":
        raise HTTPException(status_code=400, detail="Tip is not pending.")

    approved_list = [x for x in tip.approved_by.split(",") if x]
    if str(approver_id) in approved_list:
        raise HTTPException(status_code=400, detail="You have already approved this tip.")

    approved_list.append(str(approver_id))
    tip.approved_by = ",".join(approved_list)
    tip.approvals_count += 1
    
    response_msg = "Approval recorded."
    processed_result = None

    if tip.approvals_count >= 2:
        tip.status = "Approved"
        response_msg = "Tip fully approved and pushed to Neo4j."
        # Push to Neo4j
        try:
            employee = {"id": tip.employee_id, "name": tip.employee_name}
            processed_result = process_tip(employee, tip.tip_text)
        except Exception as e:
            db.rollback()
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process tip into Neo4j: {str(e)}"
            )

    db.commit()

    return {
        "success": True,
        "message": response_msg,
        "tip_id": tip_id,
        "approvals_count": tip.approvals_count,
        "neo4j_result": processed_result
    }