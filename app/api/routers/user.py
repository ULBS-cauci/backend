import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.admin_schemas import SystemPrompt, SystemPromptSummary
from app.schemas.user_schemas import (
    User,
    UserSetting,
    UserSettingPublic,
    UserSettingUpdate,
)

router = APIRouter()


@router.get("/system-prompts", response_model=List[SystemPromptSummary])
async def list_system_prompts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.exec(
        select(SystemPrompt.id, SystemPrompt.title).order_by(SystemPrompt.title)
    )
    return [SystemPromptSummary(id=row.id, title=row.title) for row in result.all()]


@router.get("/settings", response_model=UserSettingPublic)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    row = await db.get(UserSetting, current_user.id)
    if row is None:
        return UserSettingPublic(
            user_id=current_user.id,
            custom_system_prompt=None,
            selected_system_prompt_id=None,
            updated_at=None,
        )
    return row


@router.put("/settings", response_model=UserSettingPublic)
async def update_settings(
    payload: UserSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    updates = payload.model_dump(exclude_unset=True)

    selected_id = updates.get("selected_system_prompt_id")
    if selected_id is not None:
        prompt = await db.get(SystemPrompt, selected_id)
        if prompt is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown system prompt.",
            )

    row = await db.get(UserSetting, current_user.id)
    if row is None:
        row = UserSetting(user_id=current_user.id)

    for field, value in updates.items():
        setattr(row, field, value)
    row.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
