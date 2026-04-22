from pydantic import BaseModel
from typing import Optional


class WorldbuildingUpdate(BaseModel):
    power_system: Optional[list] = None
    factions: Optional[list] = None
    geography: Optional[list] = None
    core_rules: Optional[list] = None
    items: Optional[list] = None


class WorldbuildingOut(BaseModel):
    id: str
    novel_id: str
    power_system: Optional[list]
    factions: Optional[list]
    geography: Optional[list]
    core_rules: Optional[list]
    items: Optional[list]

    model_config = {"from_attributes": True}
