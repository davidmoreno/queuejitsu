.PHONY: all makemigrations migrate

all:
	@echo "makemigrations - create new migrations based on the changes you have made to your models"
	@echo "migrate        - apply migrations to your database"
	@echo "run            - Run the server in develop mode. Use ./run.sh to run in prod."

makemigrations:
	@echo "Creating migrations..."
	uv run aerich migrate

migrate:
	@echo "Applying migrations..."
	uv run aerich upgrade
	@echo "Migrations applied successfully."

run:
	@echo "Run the server"
	./main.py

serve:
	@echo "Serving with uvicorn"
	uv run uvicorn main:app --host 0.0.0.0 --port 8000
