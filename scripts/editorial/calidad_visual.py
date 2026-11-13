"""Controles semánticos y editoriales locales para el flujo de fotografías."""
import io
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from PIL import Image, ImageChops, ImageOps

VISUAL_POLICY_VERSION = "2"
ERROR_HEADING = re.compile(
    r"^(?:performing security verification|verify (?:that )?you are human|just a moment|"
    r"access denied|content blocked|calculation error|making sure you.re not a bot|"
    r"(?:http )?[45]\d\d(?:\s|$)|page not found|service unavailable|enable javascript)",
    re.I,
)


@dataclass(frozen=True)
class VisualCheck:
    status: str
    reason: str

    @property
    def valid(self):
        return self.status == "VALID"



def current_visual_approval(row):
    return row.get("media_visual_policy_version") == VISUAL_POLICY_VERSION and all(
        row.get(field) == "VALID" for field in ("media_semantic_status", "media_editorial_status")
    )


def normalized(value):
    text = unicodedata.normalize("NFKD", value or "").casefold()
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in text if not unicodedata.combining(c))))


def contains_title(text, title):
    expected = normalized(title)
    return len(expected) >= 8 and f" {expected} " in f" {normalized(text)} "


def document_check(evidence, expected_title):
    if not evidence or evidence.get("status") is None:
        return VisualCheck("UNCERTAIN", "sin evidencia de navegación")
    if evidence["status"] >= 400 or evidence.get("challenge"):
        return VisualCheck("INVALID", "respuesta HTTP de error o estructura de verificación")
    final = urlsplit(evidence["url"])
    if final.scheme != "https" or evidence.get("mime") not in {"text/html", "application/xhtml+xml"}:
        return VisualCheck("UNCERTAIN", "destino final sin documento HTML HTTPS")
    headings = [evidence.get("title", ""), *evidence.get("headings", [])]
    if any(ERROR_HEADING.search(heading.strip()) for heading in headings):
        return VisualCheck("INVALID", "encabezado de error")
    if not evidence.get("ready") or not contains_title(" ".join(headings), expected_title):
        return VisualCheck("UNCERTAIN", "documento incompleto o título sin correspondencia")
    return VisualCheck("VALID", "título visible y navegación comprobada")


def raster_check(content, *, capture_title=None, expected_size=None):
    """Decodifica la imagen, comprueba área útil y lee capturas a escala móvil."""
    try:
        with Image.open(io.BytesIO(content)) as image:
            if expected_size and image.size != expected_size:
                return VisualCheck("INVALID", "dimensiones distintas del plan de rasterización")
            if image.width < 320 or image.height < 240 or image.width * image.height > 24_000_000:
                return VisualCheck("INVALID", "dimensiones fuera del rango editorial")
            if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                return VisualCheck("INVALID", "formato final no admitido o animado")
            image.load()
            canvas = Image.new("RGBA", image.size, "white")
            canvas.alpha_composite(image.convert("RGBA"))
            gray = ImageOps.grayscale(canvas)
    except (OSError, ValueError, Image.DecompressionBombError):
        return VisualCheck("INVALID", "imagen no decodificable")
    gray.thumbnail((360, 450))
    midpoint = gray.width * gray.height // 2
    for background, count in enumerate(gray.histogram()):
        midpoint -= count
        if midpoint < 0:
            break
    difference = ImageChops.difference(gray, Image.new("L", gray.size, background))
    useful = sum(difference.histogram()[36:]) / (gray.width * gray.height)
    if useful < 0.012:
        return VisualCheck("INVALID", "área visual útil insuficiente")
    if capture_title is not None:
        if not shutil.which("tesseract"):
            return VisualCheck("UNCERTAIN", "OCR local no disponible")
        buffer = io.BytesIO()
        gray.resize((gray.width * 2, gray.height * 2)).save(buffer, format="PNG")
        try:
            result = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "11"],
                input=buffer.getvalue(), capture_output=True, check=True, timeout=12,
            )
        except (OSError, subprocess.SubprocessError):
            return VisualCheck("UNCERTAIN", "OCR local falló")
        lines = result.stdout.decode(errors="replace").splitlines()
        if any(ERROR_HEADING.search(line.strip()) for line in lines if line.strip()):
            return VisualCheck("INVALID", "OCR detectó un encabezado de error")
        if not contains_title(" ".join(lines), capture_title):
            return VisualCheck("UNCERTAIN", "la obra no se identifica en la captura a escala móvil")
    return VisualCheck("VALID", "raster decodificado con área útil")
