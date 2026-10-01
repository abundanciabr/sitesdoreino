# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "cursos ainda não consome API de nenhuma outra célula."
	@echo "Quando a sessão repassada nascer (degrau 1.3) e a matrícula decidir o acesso (degrau 1.8):"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/identidade.openapi.yaml -p 4015"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/alunos.openapi.yaml -p 4016"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi
