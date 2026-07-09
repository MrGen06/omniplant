from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from services.ingest_synthetic_pdfs import ingest_uploaded_pdf
from services.query_pipeline import pipeline


router = APIRouter()


class IngestResponse(BaseModel):
    filename: str
    chunks_ingested: int


class QueryRequest(BaseModel):
    query: str
    role: str = "Field Technician"







@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf_from_frontend(
    file: UploadFile = File(...),

):
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
    
    
    

@router.post("/query")
async def query_pdf_from_frontend(request: QueryRequest = Body(...)):
    """Accept a query from the frontend and return the answer."""
    try:
        answer = await pipeline(request.query, request.role)

        if answer is None:
            raise HTTPException(
                status_code=404,
                detail="No answer could be generated."
            )

        return {"answer": answer}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the query: {str(e)}"
        )

  