# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "metricas não consome API de célula nenhuma, e isso é desenho:"
	@echo "ela recebe EVENTOS (contracts/eventos/*.json) e responde por API."
	@echo "Quem a consome é a admin, a partir do degrau 7.4."

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. A `metricas` nasce `not-applicable` e vira
# `required` no degrau 7.4, DEPOIS de a porta de leitura existir e exportar o
# contrato vivo — a ordem que `armadilhas/228` e `243` provaram.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
