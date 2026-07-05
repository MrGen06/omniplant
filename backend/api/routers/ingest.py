from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from services.ingest_synthetic_pdfs import ingest_uploaded_pdf


router = APIRouter()







@router.post("/pdf", )
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

    chunks_ingested = ingest_uploaded_pdf(file_bytes, file.filename or "upload.pdf")

    return {
        "filename": file.filename or "upload.pdf",
        "chunks_ingested": chunks_ingested,
      
    }