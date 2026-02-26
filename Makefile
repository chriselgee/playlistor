.PHONY: build run stop clean logs shell

# Docker image and container names
IMAGE_NAME = playlistor
CONTAINER_NAME = playlistor-app

# Build the Docker image
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) .
	@echo "Build complete!"

# Run the container
run:
	@echo "Starting Playlistor container..."
	@if [ ! -f .env ]; then \
		echo "Warning: .env file not found. Copying from .env.example..."; \
		cp .env.example .env; \
		echo "Please edit .env with your Spotify credentials before the app will work!"; \
	fi
	docker run \
		--name $(CONTAINER_NAME) \
		-p 5000:5000 \
		-v $(PWD)/.env:/app/.env \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/.spotify_cache:/app/.spotify_cache \
		$(IMAGE_NAME)
	@echo "Playlistor is running at http://localhost:5000"
	@echo "Use 'make logs' to view logs or 'make stop' to stop the container"

# Stop and remove the container
stop:
	@echo "Stopping container..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@echo "Container stopped and removed"

# Clean up container and image
clean: stop
	@echo "Removing Docker image..."
	@docker rmi $(IMAGE_NAME) 2>/dev/null || true
	@echo "Cleanup complete!"

# View container logs
logs:
	@docker logs -f $(CONTAINER_NAME)

# Open a shell in the running container
shell:
	@docker exec -it $(CONTAINER_NAME) /bin/bash

# Restart the container
restart: stop run

# Show status
status:
	@docker ps -a | grep $(CONTAINER_NAME) || echo "Container not running"

# Help
help:
	@echo "Available commands:"
	@echo "  make build   - Build the Docker image"
	@echo "  make run     - Start the application container"
	@echo "  make stop    - Stop and remove the container"
	@echo "  make clean   - Stop container and remove image"
	@echo "  make logs    - View container logs"
	@echo "  make restart - Restart the container"
	@echo "  make shell   - Open shell in running container"
	@echo "  make status  - Show container status"
