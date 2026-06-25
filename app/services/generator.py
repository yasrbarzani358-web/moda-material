import io
import math
import random
import re
import zipfile
from pathlib import Path

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.core.config import settings
from app.services.ai import AIConsultant
from app.services.schemas import GeneratedMaterialPackage


class MaterialGenerator:
    def __init__(self, consultant: AIConsultant) -> None:
        self.consultant = consultant
        settings.generated_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, prompt: str, user_id: int) -> GeneratedMaterialPackage:
        slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:50] or "material"
        output_dir = settings.generated_dir / f"{user_id}-{slug}"
        output_dir.mkdir(parents=True, exist_ok=True)

        seed = abs(hash((prompt, user_id))) % (2**32)
        random.seed(seed)
        albedo, used_ai_image = await self._albedo(prompt)
        roughness = self._roughness(albedo)
        height = self._height(albedo)
        normal = self._normal_from_height(height)
        ao = self._ambient_occlusion(height)

        maps = {
            "albedo": str(output_dir / "albedo.png"),
            "normal": str(output_dir / "normal.png"),
            "roughness": str(output_dir / "roughness.png"),
            "height": str(output_dir / "height.png"),
            "ambient_occlusion": str(output_dir / "ambient_occlusion.png"),
        }
        albedo.save(maps["albedo"])
        normal.save(maps["normal"])
        roughness.save(maps["roughness"])
        height.save(maps["height"])
        ao.save(maps["ambient_occlusion"])

        archive = output_dir / f"{slug}_pbr_maps.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, path in maps.items():
                zf.write(path, arcname=f"{name}.png")

        maps["zip"] = str(archive)
        notes = self._notes(used_ai_image)
        return GeneratedMaterialPackage(prompt=prompt, directory=str(output_dir), maps=maps, notes=notes)

    def _notes(self, used_ai_image: bool) -> str:
        if used_ai_image:
            return (
                "Generated with your connected AI image API, then converted into starter PBR maps. "
                "For production renders, inspect tileability and tune normal/displacement strength."
            )
        return (
            "Generated local procedural PBR starter maps from your prompt because the external AI image API "
            "was unavailable or not configured. For production renders, inspect seams and tune scale."
        )

    def _palette(self, prompt: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        lowered = prompt.lower()
        if "oak" in lowered or "wood" in lowered:
            base = (73, 43, 25) if "dark" in lowered or "burned" in lowered else (142, 93, 52)
        elif "concrete" in lowered:
            base = (91, 91, 86)
        elif "marble" in lowered or "stone" in lowered:
            base = (210, 205, 195)
        elif "brick" in lowered:
            base = (142, 61, 43)
        else:
            base = (128, 118, 105)
        accent = (196, 151, 61) if "gold" in lowered else tuple(min(255, channel + 35) for channel in base)
        return base, accent

    async def _albedo(self, prompt: str, size: int = 1024) -> tuple[Image.Image, bool]:
        ai_image = await self._try_ai_image(prompt, size)
        if ai_image:
            return ai_image, True
        return self._procedural_albedo(prompt, size), False

    async def _try_ai_image(self, prompt: str, size: int) -> Image.Image | None:
        if not settings.ai_image_api_url or not settings.ai_image_api_key:
            return None
        material_prompt = (
            "seamless square PBR material texture, no objects, no perspective, no shadows, "
            f"top down flat surface, {prompt}"
        )
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    settings.ai_image_api_url,
                    headers={
                        "Authorization": f"Bearer {settings.ai_image_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"prompt": material_prompt},
                )
                response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGB").resize((size, size))
        except Exception:
            return None

    def _procedural_albedo(self, prompt: str, size: int = 1024) -> Image.Image:
        base, accent = self._palette(prompt)
        img = Image.new("RGB", (size, size), base)
        draw = ImageDraw.Draw(img)
        lowered = prompt.lower()

        for _ in range(5000):
            x = random.randrange(size)
            y = random.randrange(size)
            delta = random.randint(-28, 28)
            color = tuple(max(0, min(255, channel + delta)) for channel in base)
            draw.point((x, y), fill=color)

        if any(word in lowered for word in ["wood", "oak", "walnut"]):
            for y in range(0, size, 9):
                wave = int(math.sin(y / 35) * 18)
                color = tuple(max(0, channel - random.randint(5, 35)) for channel in base)
                draw.line([(0, y), (size, y + wave)], fill=color, width=random.randint(2, 5))
        if any(word in lowered for word in ["vein", "marble", "gold"]):
            for _ in range(24):
                points = []
                start_y = random.randrange(size)
                for x in range(-20, size + 20, 80):
                    points.append((x, start_y + int(math.sin(x / random.randint(45, 90)) * random.randint(20, 80))))
                draw.line(points, fill=accent, width=random.randint(2, 7), joint="curve")
        if "concrete" in lowered or "stone" in lowered:
            for _ in range(1200):
                r = random.randint(1, 3)
                x, y = random.randrange(size), random.randrange(size)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=tuple(max(0, c - random.randint(5, 50)) for c in base))

        return img.filter(ImageFilter.GaussianBlur(radius=0.35))

    def _roughness(self, albedo: Image.Image) -> Image.Image:
        grey = albedo.convert("L").filter(ImageFilter.GaussianBlur(radius=3))
        return ImageChops.invert(grey).point(lambda p: max(70, min(235, p + 35)))

    def _height(self, albedo: Image.Image) -> Image.Image:
        return albedo.convert("L").filter(ImageFilter.GaussianBlur(radius=1.2))

    def _normal_from_height(self, height: Image.Image) -> Image.Image:
        size = height.size[0]
        src = height.load()
        normal = Image.new("RGB", height.size)
        dst = normal.load()
        strength = 2.0
        for y in range(size):
            for x in range(size):
                left = src[max(x - 1, 0), y] / 255
                right = src[min(x + 1, size - 1), y] / 255
                up = src[x, max(y - 1, 0)] / 255
                down = src[x, min(y + 1, size - 1)] / 255
                dx = (left - right) * strength
                dy = (up - down) * strength
                dz = 1.0
                length = math.sqrt(dx * dx + dy * dy + dz * dz)
                dst[x, y] = (
                    int((dx / length * 0.5 + 0.5) * 255),
                    int((dy / length * 0.5 + 0.5) * 255),
                    int((dz / length * 0.5 + 0.5) * 255),
                )
        return normal

    def _ambient_occlusion(self, height: Image.Image) -> Image.Image:
        blurred = height.filter(ImageFilter.GaussianBlur(radius=8))
        return ImageChops.screen(height, blurred).point(lambda p: max(45, min(255, p)))
