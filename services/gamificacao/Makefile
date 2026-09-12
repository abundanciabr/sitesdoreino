# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

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

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. A `gamificacao` nasce `not-applicable` e
# vira `required` no PR 4 da escada (RITOS §3), quando o contrato existir.
contrato-check:
	python ../../ci/contract_freeze.py $(CELULA) && echo "✅ ci/contract_freeze.py: portão verificado (adaptador: ci/freeze-de-contrato.sh)"

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
