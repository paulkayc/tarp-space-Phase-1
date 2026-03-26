.PHONY: up down migrate seed test logs psql shell

up:
	docker-compose up --build

down:
	docker-compose down

migrate:
	docker-compose exec backend alembic upgrade head

seed:
	docker-compose exec backend python db/seeds/houston_furniture.py

test:
	docker-compose exec backend pytest

logs:
	docker-compose logs -f backend

psql:
	docker-compose exec postgres psql -U tarpspace tarpspace

shell:
	docker-compose exec backend bash
