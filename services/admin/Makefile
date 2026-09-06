# A Definição de Pronto local da célula: make ci
CELULA := $(notdir $(CURDIR))

.PHONY: dev mocks test lint type contrato-check ci

dev:            ## sobe SÓ esta célula + banco (isolamento real)
	docker compose -f docker-compose.dev.yml up

mocks:          ## dependências a partir dos CONTRATOS — nunca do código alheio
	@echo "admin ainda não consome API de nenhuma outra célula."
	@echo "Quando a porta nascer (PR 3): mock da identidade"
	@echo "  npx @stoplight/prism-cli mock ../../contracts/identidade.openapi.yaml -p 4014"

test:
	python -m pytest -q

lint:
	black --check .
	@if [ -f .importlinter ]; then lint-imports; fi

type:
	@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy nesta célula"; fi

# [INV-CI01] Quem decide se esta célula tem contrato é ci/manifesto-de-contratos.json,
# não a presença do arquivo em disco. Desde 06/09/2026 a `admin` FORNECE uma
# porta de máquina (`config/api.py`), e o congelamento dela viaja no PR do Rito
# de Contrato (#1238), que pousa logo depois deste. Enquanto aquela linha do
# manifesto ainda disser `not-applicable`, o portão devolve SKIP declarado;
# quando ela virar `required`, este mesmo alvo passa a comparar o congelado com
# o que `manage.py export_openapi` imprime.
contrato-check:
	bash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
	@echo "✅ $(CELULA): Definição de Pronto local atingida"
