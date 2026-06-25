# AI Material Assistant

Production-ready Telegram bot for architects, interior designers, and 3D artists. It behaves like a material consultant: it understands material names, descriptive prompts, architectural usage, and styles, then aggregates free PBR material sources and can generate procedural starter map packs.

## Features

- Telegram menu UX with material-name search, description search, usage search, AI generation, favorites, and help.
- Architectural intent parsing for terms such as minimalist, industrial, Scandinavian, brutalist, contemporary, luxury, and rustic.
- Free material aggregation from AmbientCG, Poly Haven, CGBookcase, TextureCan, and 3DTextures.
- Duplicate reduction and relevance ranking.
- Result cards with preview, category, usage, resolution, download/open links, save, similar search, and variant generation.
- SQLite persistence for users, events, favorites, and settings.
- Admin commands for statistics and broadcasts.
- Docker and docker-compose deployment.

## Quick Start

1. Create a Telegram bot with [BotFather](https://t.me/BotFather) and copy the token.
2. Copy the environment file:

```bash
cp .env.example .env
```

3. Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your-token
ADMIN_IDS=123456789
OPENAI_API_KEY=
ENABLE_AI_GENERATION=false
```

4. Run locally:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

## Docker Deployment

```bash
docker compose up --build -d
docker compose logs -f bot
```

The SQLite database is stored in `./data`, and generated material maps are stored in `./generated`.

## Telegram Commands

- `/start` opens the main menu.
- `/help` shows usage examples.
- `/stats` shows admin statistics.
- `/broadcast` starts an admin broadcast flow.
- `/cancel` cancels the current flow.

## How Search Works

The bot first parses the user prompt into a `MaterialIntent`:

- material type
- color
- finish
- style
- usage
- surface properties
- environment

It then queries multiple source adapters asynchronously. If a source API or page structure is unavailable, the adapter returns a useful source-specific search link instead of failing the conversation.

## AI Generation

The included generator creates procedural PBR starter maps:

- `albedo.png`
- `normal.png`
- `roughness.png`
- `height.png`
- `ambient_occlusion.png`
- `material_maps.zip`

This is production-safe as a default because it does not depend on a paid image API. You can extend `app/services/generator.py` to call your preferred image model when `ENABLE_AI_GENERATION=true`.

## Admin Setup

Set `ADMIN_IDS` to a comma-separated list of Telegram user IDs:

```env
ADMIN_IDS=111111111,222222222
```

Admins can view stats and broadcast messages. Regular users receive "Admin access required."

## Project Structure

```text
app/
  bot/              Telegram handlers and conversation flow
  core/             Settings and keyboards
  db/               SQLAlchemy models and async session
  services/         AI consultant, search orchestration, generation, stats
  sources/          Material website adapters
tests/              Focused unit tests
Dockerfile
docker-compose.yml
requirements.txt
```

## Production Notes

- For high traffic, replace polling with webhooks and move generated files to object storage.
- Add Redis if you need persistent result-card callback caches across restarts.
- SQLite is enough for small deployments; switch `DATABASE_URL` to Postgres for multi-instance scaling.
- Source websites can change markup. Keep adapters isolated and monitor search failure logs.
- Generated procedural maps are useful starters; inspect tileability and displacement strength before final production use.

## Testing

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest
```
