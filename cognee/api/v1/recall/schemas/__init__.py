from typing import Optional

from pydantic import BaseModel


class RecommendJobPayloadDTO(BaseModel):
    app_user_id: Optional[str] = None
    desired_position: Optional[dict] = None
    resume: Optional[dict] = None
