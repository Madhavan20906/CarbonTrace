.PHONY: install test e2e chain deploy api web build
install:
	cd contracts-pkg && npm ci || npm install
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	cd frontend && npm ci || npm install
test:
	cd contracts-pkg && npx hardhat test
	cd backend && . .venv/bin/activate && pytest -q
	cd frontend && npx tsc --noEmit && npx vitest run
e2e:
	./scripts/e2e.sh
chain:
	cd contracts-pkg && npx hardhat node
deploy:
	cd contracts-pkg && npx hardhat run scripts/deploy.js --network localhost
api:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000
web:
	cd frontend && npm run dev
build:
	cd frontend && npm run build
