from telegram import User as TelegramUser

from app.db.session import SessionLocal
from app.services.repository import Repository


class StatsService:
    async def touch_user(self, user: TelegramUser | None) -> None:
        if not user:
            return
        async with SessionLocal() as session:
            repo = Repository(session)
            await repo.upsert_user(user.id, user.username, user.first_name)

    async def event(self, user_id: int | None, event_type: str, payload: dict | None = None) -> None:
        async with SessionLocal() as session:
            repo = Repository(session)
            await repo.add_event(user_id, event_type, payload)
