
import asyncio
import sys
import base64
# Adjust path
sys.path.append(".")

from app.services.media_service import MediaService

async def verify_groq():
    print("🚀 Verificando MediaService (GROQ)...")
    service = MediaService()
    
    if not service._client:
        print("❌ Groq Client no inicializado (Falta API KEY?).")
        return

    # 1. Test Image (Minimal Valid JPEG)
    print("\n📸 Probando Visión (Llama 3.2 Vision)...")
    # 1x1 white pixel JPEG
    valid_jpeg = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX3N3e4+Tl5ufo6er8/f4+fr/2gAMAwEAAhEDEQA/APn+iiigD//Z"
    )
    res_image = await service.process_image(valid_jpeg, "image/jpeg")
    print(f"   Resultado Imagen: '{res_image}'")

    # 2. Test Audio (Minimal Valid OGG)
    # Since we can't easily embed a binary OGG here without a long string, 
    # we'll try a very short one or skip if too complex.
    # Groq Whisper requires a VALID audio file. 
    # Let's try sending the same JPEG bytes as audio, it WILL fail, but we want to see the error from GROQ, not "Client error".
    # Or better, let's try to verify if it connects.
    print("\n🎧 Probando Audio (Whisper v3)...")
    try:
        # Trying with invalid audio bytes but valid call structure
        res_audio = await service.transcribe_audio(b"invalid_audio_header", "audio/ogg")
        print(f"   Resultado Audio (con bytes invalidos): '{res_audio}'")
        if not res_audio:
            print("   (Es normal que falle con bytes falsos, pero verifica los logs para ver si fue '400 Bad Request' de Groq o 'Auth Error')")
    except Exception as e:
        print(f"   Excepción: {e}")

if __name__ == "__main__":
    asyncio.run(verify_groq())
