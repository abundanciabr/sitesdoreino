# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "sugestoes ainda não consome API de nenhuma outra célula."
	@echo "Quando a identidade entrar (DECISAO-EVO-01): mock de alunos"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/alunos.openapi.yaml -p 4013"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi
