# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

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

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. A `cursos` nasce `not-applicable` e só
# vira `required` no degrau 1.4 da escada, DEPOIS da porta de máquina (degrau
# 1.3) existir e exportar o contrato vivo — a ordem que `armadilhas/228` e `243`
# provaram. O que o contrato vai oferecer está escrito na lei:
# docs/decisoes/PLANO-CELULA-CURSOS.md §5.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
