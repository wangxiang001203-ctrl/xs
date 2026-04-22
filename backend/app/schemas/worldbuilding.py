from pydantic import BaseModel
from typing import Optional


class WorldbuildingUpdate(BaseModel):
    realm_system: Optional[dict] = None
    currency: Optional[dict] = None
    artifacts: Optional[list] = None
    techniques: Optional[list] = None
    factions: Optional[list] = None
    geography: Optional[list] = None
    custom_rules: Optional[list] = None


class WorldbuildingOut(BaseModel):
    id: str
    novel_id: str
    realm_system: Optional[dict]
    currency: Optional[dict]
    artifacts: Optional[list]
    techniques: Optional[list]
    factions: Optional[list]
    geography: Optional[list]
    custom_rules: Optional[list]

    model_config = {"from_attributes": True}
