from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class RepoOut(BaseModel):
    repo_id: str
    repo_url: str
    canonical_repo_url: str
    provider: str
    default_branch: Optional[str] = None
    created_at: datetime

    latest_job_stats: Optional[Dict[str, Any]] = None
    latest_job_id: Optional[str] = None
    latest_job_status: Optional[str] = None
    latest_job_updated_at: Optional[datetime] = None
    latest_job_error: Optional[str] = None