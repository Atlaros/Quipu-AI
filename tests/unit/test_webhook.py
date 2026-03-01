"""Tests para la verificación de firma HMAC del webhook.

Verifica que solo requests firmados correctamente son aceptados.
"""

import hashlib
import hmac

from app.api.v1.webhook import _verify_signature


class TestVerifySignature:
    """Tests para _verify_signature."""

    def test_firma_valida(self) -> None:
        """Firma HMAC correcta → True."""
        secret = "mi_app_secret"
        payload = b'{"entry": []}'

        # Generar firma correcta
        expected_hash = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_hash}"

        # Mockear settings con monkeypatch
        from unittest.mock import patch

        with patch("app.api.v1.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = secret
            result = _verify_signature(payload, signature)

        assert result is True

    def test_firma_invalida(self) -> None:
        """Firma HMAC incorrecta → False."""
        from unittest.mock import patch

        with patch("app.api.v1.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = "mi_app_secret"
            result = _verify_signature(b'{"data": "test"}', "sha256=firma_falsa_123")

        assert result is False

    def test_firma_formato_invalido(self) -> None:
        """Firma sin prefijo sha256= → False."""
        from unittest.mock import patch

        with patch("app.api.v1.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = "mi_app_secret"
            result = _verify_signature(b'{"data": "test"}', "md5=abc123")

        assert result is False

    def test_firma_vacia(self) -> None:
        """Sin header de firma → False."""
        from unittest.mock import patch

        with patch("app.api.v1.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = "mi_app_secret"
            result = _verify_signature(b'{"data": "test"}', "")

        assert result is False

    def test_skip_sin_app_secret(self) -> None:
        """Sin app_secret configurado → True (modo desarrollo)."""
        from unittest.mock import patch

        with patch("app.api.v1.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = ""
            result = _verify_signature(b'{"data": "test"}', "sha256=cualquiera")

        assert result is True


class TestRetryConfig:
    """Tests para la configuración de retry del agente."""

    def test_is_rate_limit_error_detecta_resource_exhausted(self) -> None:
        """Detecta errores de rate limit de Gemini."""
        from app.agent.graph import _is_rate_limit_error

        assert _is_rate_limit_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded")) is True

    def test_is_rate_limit_error_ignora_otros_errores(self) -> None:
        """No reintenta errores que no son rate limit."""
        from app.agent.graph import _is_rate_limit_error

        assert _is_rate_limit_error(Exception("Invalid API key")) is False

    def test_is_rate_limit_error_detecta_429(self) -> None:
        """Detecta código 429."""
        from app.agent.graph import _is_rate_limit_error

        assert _is_rate_limit_error(Exception("Error 429: Too many requests")) is True
