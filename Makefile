.PHONY: dev worker flower test clean setup

# Développement
dev:
	uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.worker worker -l info -Q celery -n worker1@%h

flower:
	celery -A app.worker flower --port=5555

# Setup
setup:
	pip install -r requirements.txt
	mkdir -p models outputs reference

# Tests
test:
	pytest tests/ -v --cov=app --cov-report=html

# Docker prod
up:
	docker-compose -f docker-compose.yml up -d

down:
	docker-compose -f docker-compose.yml down

# Maintenance
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf .coverage htmlcov

# Utilitaires
gpu:
	nvidia-smi

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker