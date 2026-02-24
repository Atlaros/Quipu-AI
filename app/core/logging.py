"""Configuración de logging estructurado con structlog.

Todos los módulos deben usar `structlog.get_logger()` en vez de `print()`.
Los logs salen en formato JSON para ser consumidos por herramientas de observabilidad.
"""

import structlog


def setup_logging(*, debug: bool = False) -> None:
    """Configura structlog para el proyecto.

    Args:
        debug: Si True, usa formato legible para consola.
               Si False, usa formato JSON para producción.
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
