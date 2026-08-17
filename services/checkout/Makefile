# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco + redis + mocks (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "Exemplo (ajuste às dependências desta célula):"
	@echo "npx @stoplight/prism-cli mock ../../contracts/pagamentos.openapi.yaml -p 4010"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

contrato-check:
	@if [ -f ../../contracts/$(CELULA).openapi.yaml ]; then \
		python manage.py export_openapi > /tmp/$(CELULA).openapi.yaml && \
		bash ../../ci/freeze-de-contrato.sh $(CELULA) /tmp/$(CELULA).openapi.yaml; \
	else \
		echo "ℹ $(CELULA) não expõe contrato congelado"; \
	fi

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
