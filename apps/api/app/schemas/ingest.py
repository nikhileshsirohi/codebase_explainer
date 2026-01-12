from pydantic import BaseModel, HttpUrl, Field

class IngestRepoRequest(BaseModel):
    repo_url: HttpUrl = Field(..., description="Public GitHub repository URL")

class IngestRepoResponse(BaseModel):
    repo_id: str
    job_id: str
    status: str