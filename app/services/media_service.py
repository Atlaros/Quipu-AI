"""Service de procesamiento de media — Audio e Imágenes (vía Groq).

Transcribe audio usando Whisper v3 y procesa imágenes con Llama 3.2 Vision.
Mucho más rápido y estable que Gemini Free Tier.
"""

import base64
import tempfile
from pathlib import Path

import structlog
from groq import Groq
from google import genai

from app.core.config import settings

logger = structlog.get_logger()


class MediaService:
    """Procesa audio e imágenes con Groq Cloud."""

    def __init__(self) -> None:
        if not settings.groq_api_key:
            logger.warning("groq_api_key_missing")
            self._client = None
        else:
            self._client = Groq(api_key=settings.groq_api_key)
            
        if settings.google_api_keys:
            self._gemini_client = genai.Client(api_key=settings.google_api_keys[0])
            self._has_gemini = True
        else:
            self._gemini_client = None
            self._has_gemini = False

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Transcribe audio usando Whisper-large-v3 en Groq.

        Args:
            audio_bytes: Bytes del archivo de audio.
            mime_type: Ignorado por Groq (auto-detect), pero usado para extensión temporal.

        Returns:
            Texto transcrito.
        """
        if not self._client:
            return ""

        suffix = ".ogg" if "ogg" in mime_type else ".mp3"
        tmp_path = Path(tempfile.mkdtemp()) / f"audio{suffix}"
        
        try:
            tmp_path.write_bytes(audio_bytes)
            
            with open(tmp_path, "rb") as file:
                transcription = self._client.audio.transcriptions.create(
                    file=(tmp_path.name, file.read()),
                    model="whisper-large-v3",
                    prompt="Transcribe el siguiente audio en español.",
                    response_format="json",
                    language="es",
                    temperature=0.0
                )
            
            text = transcription.text.strip()
            logger.info("audio_transcribed_groq", length=len(text))
            return text

        except Exception as exc:
            logger.error("audio_transcription_failed", error=str(exc))
            return ""
        finally:
            tmp_path.unlink(missing_ok=True)
            if tmp_path.parent.exists():
                try:
                    tmp_path.parent.rmdir()
                except OSError:
                    pass

    async def process_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Describe una imagen usando Gemini 1.5 Flash (Groq deprecó sus modelos de visión).

        Args:
            image_bytes: Bytes de la imagen.
            mime_type: Tipo MIME.

        Returns:
            Descripción de la imagen.
        """
        if not self._has_gemini:
            logger.warning("gemini_api_key_missing_for_vision")
            return ""

        try:
            prompt = "Eres un experto en inventario de ropa. Describe esta imagen brevemente (Producto, Color, Marca estimada). Responde en español."
            
            image_part = {
                "inline_data": {
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                    "mime_type": mime_type
                }
            }
            
            response = self._gemini_client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=[prompt, image_part]
            )
            
            description = response.text.strip()
            logger.info("image_processed_gemini", length=len(description))
            return description

        except Exception as exc:
            logger.error("image_processing_failed", error=str(exc))
            return ""
