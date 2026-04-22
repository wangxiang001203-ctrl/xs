from fastapi import APIRouter
from pydantic import BaseModel

from app.services.workflow_config_service import get_workflow_config, save_workflow_config

router = APIRouter(prefix="/api/admin", tags=["admin"])


class WorkflowConfigPayload(BaseModel):
    flow: list[dict]
    prompts: dict[str, str]


@router.get("/workflow-config")
def get_config():
    return get_workflow_config()


@router.put("/workflow-config")
def update_config(payload: WorkflowConfigPayload):
    data = {"flow": payload.flow, "prompts": payload.prompts}
    return save_workflow_config(data)

