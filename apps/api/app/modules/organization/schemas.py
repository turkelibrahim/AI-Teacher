from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List
from app.modules.identity.schemas import UserResponse

class OrganizationCreate(BaseModel):
    name: str

class OrganizationResponse(BaseModel):
    id: UUID4
    name: str
    slug: str
    organization_type: str
    is_active: bool
    
    class Config:
        from_attributes = True

class MemberRoleResponse(BaseModel):
    role_name: str
    
class OrganizationMemberResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    organization_id: UUID4
    status: str
    roles: List[str]
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True
