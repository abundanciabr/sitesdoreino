# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "pages ainda não consome API de nenhuma outra célula."
	@echo "Quando a porta nascer (degrau 06 da escada do PLANO-PORTFOLIO-DO-ALUNO §5):"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/identidade.openapi.yaml -p 4017"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/alunos.openapi.yaml -p 4018"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. A `pages` nasce `not-applicable` e só vira
# `required` no degrau 03 da escada, DEPOIS de a porta de máquina existir e
# exportar o contrato vivo — a ordem que `armadilhas/228` e `243` provaram, e
# que o `armadilhas/304` documenta como o erro clássico de plano escrito fora
# desta casa.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
