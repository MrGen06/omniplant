from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from core.database import Base

class PendingTip(Base):
    __tablename__ = "pending_tips"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True, nullable=False)
    employee_name = Column(String, nullable=False)
    tip_text = Column(String, nullable=False)
    approvals_count = Column(Integer, default=0, nullable=False)
    approved_by = Column(String, default="", nullable=False)  # Comma-separated list of employee IDs
    status = Column(String, default="Pending", index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
