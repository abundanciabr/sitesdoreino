# Atalho da raiz. `python`, nunca `python3`; sobrescreva com PYTHON=... se o
# seu ambiente chamar o interpretador de outro jeito.
PYTHON ?= python

.PHONY: ajuda celula

ajuda:          ## lista os alvos (é o alvo padrão)
	@echo "  make celula CELULA=x   testes pytest de services/x (cria o venv e o Postgres de teste sozinho; ARGS=... vai ao pytest)"

celula:         ## make celula CELULA=pagamentos [ARGS="-k nome -x"]
	@test -n "$(CELULA)" || { echo "ERROR: informe CELULA=<nome>"; exit 2; }
	$(PYTHON) ci/testar_celula.py $(CELULA) $(ARGS)
