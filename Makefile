# Makefile para Quipu AI

.PHONY: install run-local run-docker stop-docker ngrok clean help

# Variables
PORT=8000
DOCKER_IMAGE=quipu-ai
CONTAINER_NAME=quipu_container

help:
	@echo "Comandos disponibles:"
	@echo "  make install      - Instala dependencias con uv"
	@echo "  make run-local    - Corre el backend localmente (puerto $(PORT))"
	@echo "  make run-docker   - Construye y corre el contenedor Docker (puerto $(PORT))"
	@echo "  make stop-docker  - Detiene el contenedor Docker"
	@echo "  make ngrok        - Inicia el túnel Ngrok al puerto $(PORT)"
	@echo "  make clean        - Limpia archivos temporales y caches"

install:
	uv sync

run-local:
	uv run uvicorn main:app --reload --port $(PORT)

run-docker:
	docker build -t $(DOCKER_IMAGE) .
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)
	docker run --name $(CONTAINER_NAME) -p $(PORT):8000 --env-file .env --rm -d $(DOCKER_IMAGE)
	@echo "✅ Docker corriendo en segundo plano. Usa 'docker logs -f $(CONTAINER_NAME)' para ver logs."

stop-docker:
	docker stop $(CONTAINER_NAME)

ngrok:
	./ngrok http $(PORT)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
