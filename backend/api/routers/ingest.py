from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from services.ingest_synthetic_pdfs import ingest_uploaded_pdf


router = APIRouter()


class IngestResponse(BaseModel):
    filename: str
    chunks_ingested: int
    authenticated_user: str | None = None
    role_tier: int | None = None


def require_authenticated_request(request: Request) -> dict:
    """Return JWT claims injected by middleware or reject the request."""
    auth_context = getattr(request.state, "auth_context", None)
    if not auth_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_context


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf_from_frontend(
    request: Request,
    file: UploadFile = File(...),
    auth_context: dict = Depends(require_authenticated_request),
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
        "authenticated_user": auth_context.get("sub"),
        "role_tier": auth_context.get("role"),
    }