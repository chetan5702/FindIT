.PHONY: setup up down logs migrate seed admin test test-backend test-frontend install-e2e test-e2e

setup:
	@test -f .env || (cp .env.example .env && printf '%s\n' 'Created .env; replace all CHANGE_ME values before starting.')

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs --follow --tail=200

migrate:
	docker compose run --rm backend alembic upgrade head

seed:
	docker compose exec backend python -m app.seed

admin:
	docker compose exec backend python -m app.cli create-admin

test: test-backend test-frontend

test-backend:
	docker compose run --rm backend pytest -q

test-frontend:
	docker compose run --rm frontend npm test -- --run

install-e2e:
	cd frontend && npm install && npx playwright install chromium

test-e2e:
	cd frontend && npm run test:e2e

