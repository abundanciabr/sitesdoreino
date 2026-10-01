# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "gamificacao ainda não consome API de nenhuma outra célula."
	@echo "Quando o reconhecimento de sessão nascer (PR 7 da escada):"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/identidade.openapi.yaml -p 4014"

test:
	python -m pytest -q

lint:
	black --check .
	$(if $(wildcard .importlinter),lint-imports)

type:
	$(if $(wildcard mypy.ini),mypy .,@echo "ℹ sem mypy nesta célula")
