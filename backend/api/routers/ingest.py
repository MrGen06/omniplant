from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from pydantic import BaseModel
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
async def add_tips_to_neo4j(request: dict = Body(...)):

    employee = request.get("employee")
    tip = request.get("tip")

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee information is required."
        )

    if not tip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tip is required."
        )

    try:
        result = process_tip(
            employee=employee,
            raw_tip=tip
        )

        return {
            "employee": employee.get("name"),
            "tip": tip,
            **result
        }

    except Exception as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            status_=False,
            detail=f"Failed to process tip: {str(e)}"
        )