from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.workflow_config_service import get_workflow_config, save_workflow_config

router = APIRouter(prefix="/api/admin", tags=["admin"])


class WorkflowConfigPayload(BaseModel):
    flow: list[dict]
    prompts: dict[str, str]
    llm_settings: dict | None = Field(default=None, alias="model_config")

    model_config = {
        "populate_by_name": True,
        "protected_namespaces": (),
    }


@router.get("/workflow-config")
def get_config():
    return get_workflow_config()


@router.put("/workflow-config")
def update_config(payload: WorkflowConfigPayload):
    data = {
        "flow": payload.flow,
        "prompts": payload.prompts,
        "model_config": payload.llm_settings,
    }
    return save_workflow_config(data)
