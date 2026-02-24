# ============================================
# Stage 1: Builder — Instala dependencias con uv
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Instalar uv (gestor de paquetes Rust-backed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copiar solo archivos de dependencias para cache de Docker
COPY pyproject.toml uv.lock ./

# Instalar dependencias (sin dev) en un venv aislado
RUN uv sync --no-dev --frozen --no-install-project

# Copiar código fuente
COPY . .

# ============================================
# Stage 2: Runtime — Imagen mínima (~80MB)
# ============================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Crear usuario no-root (seguridad)
RUN groupadd -r quipu && useradd -r -g quipu quipu

# Copiar venv y código desde builder
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/app ./app
COPY --from=builder /build/main.py ./main.py

# Directorios escribibles para reportes y archivos temporales
RUN mkdir -p /app/reports /tmp/matplotlib && \
    chown -R quipu:quipu /app/reports /tmp/matplotlib

# Usar el venv del builder
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
ENV MPLCONFIGDIR=/tmp/matplotlib

# Puerto de la API
EXPOSE 8000

# Cambiar a usuario no-root
USER quipu

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

# Ejecutar con uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
