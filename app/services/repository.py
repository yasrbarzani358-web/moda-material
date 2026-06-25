import json

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event, Favorite, User
from app.services.schemas import MaterialResult


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        statement = insert(User).values(id=user_id, username=username, first_name=first_name)
        statement = statement.on_conflict_do_update(
            index_elements=[User.id],
            set_={"username": username, "first_name": first_name, "last_seen_at": func.now()},
        )
        await self.session.execute(statement)
        await self.session.commit()

    async def add_event(self, user_id: int | None, event_type: str, payload: dict | None = None) -> None:
        self.session.add(Event(user_id=user_id, event_type=event_type, payload=json.dumps(payload or {})))
        await self.session.commit()

    async def save_favorite(self, user_id: int, material: MaterialResult) -> bool:
        statement = insert(Favorite).values(
            user_id=user_id,
            material_key=material.key,
            material_name=material.name,
            category=material.category,
            source=material.source,
            preview_url=material.preview_url,
            download_url=material.download_url or material.page_url,
        )
        statement = statement.on_conflict_do_nothing(index_elements=["user_id", "material_key"])
        result = await self.session.execute(statement)
        await self.session.commit()
        return bool(result.rowcount)

    async def favorites_for_user(self, user_id: int, limit: int = 10) -> list[Favorite]:
        result = await self.session.execute(
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def stats(self) -> dict[str, int]:
        users = await self.session.scalar(select(func.count()).select_from(User))
        favorites = await self.session.scalar(select(func.count()).select_from(Favorite))
        events = await self.session.scalar(select(func.count()).select_from(Event))
        searches = await self.session.scalar(select(func.count()).select_from(Event).where(Event.event_type == "search"))
        generations = await self.session.scalar(
            select(func.count()).select_from(Event).where(Event.event_type == "generate")
        )
        return {
            "users": users or 0,
            "favorites": favorites or 0,
            "events": events or 0,
            "searches": searches or 0,
            "generations": generations or 0,
        }

    async def all_user_ids(self) -> list[int]:
        result = await self.session.execute(select(User.id))
        return [row[0] for row in result.all()]
