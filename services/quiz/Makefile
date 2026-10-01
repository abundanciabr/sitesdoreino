# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type ci e2e

dev:            ## sobe SÓ esta célula + banco + mocks (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "quiz não consome API de nenhuma outra célula (constituicoes/AGENTS.quiz.md)"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi
