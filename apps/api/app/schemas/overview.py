from pydantic import BaseModel
from typing import List

class Component(BaseModel):
    name: str
    files: List[str]

class RepoOverview(BaseModel):
    repo_id: str
    summary: str
    components: List[Component]
    data_flow: List[str]
    tech_stack: List[str]
    confidence: str