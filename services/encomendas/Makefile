# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "encomendas ainda não consome API de nenhuma outra célula."
	@echo "Quando o reconhecimento de sessão nascer (degrau 2.7 da escada, lei §7):"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/identidade.openapi.yaml -p 4015"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/alunos.openapi.yaml -p 4016"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. A `encomendas` nasce `not-applicable` e só
# vira `required` no degrau 2.8 da escada, DEPOIS da porta de máquina (degrau
# 2.7) existir e exportar o contrato vivo — a ordem que `armadilhas/228` e `243`
# provaram. O contrato em papel, até lá:
# docs/decisoes/CONTRATO-encomendas-v1-rascunho.md.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
