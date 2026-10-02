# Atalhos da raiz. `python`, nunca `python3`; sobrescreva com PYTHON=... se o
# seu ambiente chamar o interpretador de outro jeito.
PYTHON ?= python

.PHONY: ajuda testes celula esqueleto

ajuda:          ## lista os alvos (é o alvo padrão)
	@echo "Alvos da raiz:"
	@echo "  make testes            os testes de ci/ e de infra/ (publicação, recuperação, operação)"
	@echo "  make celula CELULA=x   testes pytest de services/x"
	@echo "  make esqueleto         o caminho inteiro de ponta a ponta, em compose local"

testes:         ## os testes de ci/ e de infra/, direto no pytest
	$(PYTHON) -m pytest -q ci/tests infra

celula:         ## make celula CELULA=pagamentos
	@test -n "$(CELULA)" || { echo "ERROR: informe CELULA=<nome>"; exit 2; }
	$(MAKE) -C services/$(CELULA) test

esqueleto:      ## sobe o compose de dev do caminho e percorre a transacao inteira via curl
	bash e2e/esqueleto.sh
