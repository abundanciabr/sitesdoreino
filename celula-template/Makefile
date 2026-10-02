# Comandos locais da célula.
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test ci

dev:            ## sobe SÓ esta célula + banco + redis + mocks (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "Exemplo (ajuste às dependências desta célula):"
	@echo "npx @stoplight/prism-cli mock ../../contracts/pagamentos.openapi.yaml -p 4010"

test:
	python -m pytest -q

ci: test
