from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


class ImageMaterialAnalyzer:
    def analyze(self, image_path: str | Path) -> str:
        image = Image.open(image_path).convert("RGB").resize((256, 256))
        stat = ImageStat.Stat(image)
        r, g, b = stat.mean
        brightness = (r + g + b) / 3
        saturation = max(r, g, b) - min(r, g, b)

        tone = "dark" if brightness < 85 else "light" if brightness > 180 else "medium"
        color = self._color_name(r, g, b, brightness, saturation)
        material = self._material_hint(r, g, b, brightness, saturation)
        finish = self._finish_hint(image)
        texture = self._texture_hint(image)

        return " ".join([tone, color, material, finish, texture])

    def _color_name(self, r: float, g: float, b: float, brightness: float, saturation: float) -> str:
        if saturation < 18:
            return "gray" if brightness < 210 else "white"
        if r > g + 25 and r > b + 25:
            return "brown" if g > b else "red"
        if g > r + 20 and g > b + 20:
            return "green"
        if b > r + 20 and b > g + 20:
            return "blue"
        if r > 150 and g > 120 and b < 90:
            return "gold"
        return "neutral"

    def _material_hint(self, r: float, g: float, b: float, brightness: float, saturation: float) -> str:
        if r > 95 and g > 55 and b < 80 and saturation > 25:
            return "wood"
        if saturation < 25 and brightness < 170:
            return "concrete"
        if brightness > 165 and saturation < 40:
            return "stone"
        return "architectural material"

    def _finish_hint(self, image: Image.Image) -> str:
        edges = image.filter(ImageFilter.FIND_EDGES).convert("L")
        edge_mean = ImageStat.Stat(edges).mean[0]
        return "rough" if edge_mean > 25 else "smooth"

    def _texture_hint(self, image: Image.Image) -> str:
        grey = image.convert("L")
        stddev = ImageStat.Stat(grey).stddev[0]
        if stddev > 55:
            return "high contrast texture"
        if stddev > 30:
            return "subtle texture"
        return "plain surface"
