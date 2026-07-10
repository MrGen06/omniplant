from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from pydantic import BaseModel
import traceback  # <--- Added to reveal hidden errors!

from services.ingest_synthetic_pdfs import ingest_uploaded_pdf
from services.query_pipeline import pipeline

router = APIRouter()

class IngestResponse(BaseModel):
    filename: str
    chunks_ingested: int

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

    ingest_result = await ingest_uploaded_pdf(file_bytes, file.filename or "upload.pdf")

    return {
        "filename": file.filename or "upload.pdf",
        "chunks_ingested": ingest_result.get("count", 0),
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
        answer = await pipeline(request.query, role_name)

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