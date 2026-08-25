# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco + mocks (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "mensageria não consome API de nenhuma outra célula (constituicoes/AGENTS.mensageria.md)"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. O `if [ -f ... ]` que morava aqui tratava
# "não achei o congelado" como "esta célula não tem contrato" — indistinguível de
# "o congelado sumiu", e apagar contracts/$(CELULA).openapi.yaml deixava este alvo
# VERDE. A `mensageria` é `not-applicable` no manifesto: o portão devolve SKIP
# declarado, com o motivo escrito — nunca silêncio.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
