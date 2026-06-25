import logging

from telegram.ext import Application

from app.bot.handlers import register_handlers
from app.core.config import settings
from app.db.session import create_schema
from app.services.ai import AIConsultant
from app.services.downloader import MaterialDownloader
from app.services.generator import MaterialGenerator
from app.services.image_similarity import ImageMaterialAnalyzer
from app.services.material_search import MaterialSearchService
from app.services.stats import StatsService
from app.sources.ambientcg import AmbientCGSource
from app.sources.cgbookcase import CGBookcaseSource
from app.sources.polyhaven import PolyHavenSource
from app.sources.texturecan import TextureCanSource
from app.sources.threedtextures import ThreeDTexturesSource


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def post_init(application: Application) -> None:
    await create_schema()
    logging.getLogger(__name__).info("Database schema ready")


async def post_shutdown(application: Application) -> None:
    search_service: MaterialSearchService = application.bot_data["search_service"]
    await search_service.aclose()


def build_application() -> Application:
    consultant = AIConsultant()
    sources = [
        AmbientCGSource(),
        PolyHavenSource(),
        CGBookcaseSource(),
        TextureCanSource(),
        ThreeDTexturesSource(),
    ]
    search_service = MaterialSearchService(sources=sources, consultant=consultant)
    generator = MaterialGenerator(consultant=consultant)
    image_analyzer = ImageMaterialAnalyzer()
    downloader = MaterialDownloader()
    stats = StatsService()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data.update(
        {
            "consultant": consultant,
            "search_service": search_service,
            "generator": generator,
            "image_analyzer": image_analyzer,
            "downloader": downloader,
            "stats": stats,
        }
    )
    register_handlers(application)
    return application


def main() -> None:
    configure_logging()
    application = build_application()
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        close_loop=False,
    )


if __name__ == "__main__":
    main()
