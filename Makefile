.PHONY: all makemigrations migrate

all:
	@echo "makemigrations - create new migrations based on the changes you have made to your models"
	@echo "migrate - apply migrations to your database"


makemigrations:
	@echo "Creating migrations..."
	uv run aerich migrate

migrate:
	@echo "Applying migrations..."
	uv run aerich upgrade
	@echo "Migrations applied successfully."
