# =============================================================================
# FACHADA — interface humana conveniente. A implementação canônica é Python.
#
#            ci/ci.py
#               ▲
#         ┌─────┼─────┐
#         │     │     │
#     Makefile  CI   Agentes
#
# Nenhum alvo aqui contém lógica: se `make` não existir numa máquina, os mesmos
# comandos rodam direto e com o mesmo resultado.
#
#     make ci       ==  python ci/ci.py
#     make doctor   ==  python ci/doctor.py
#     make freeze   ==  python ci/contract_freeze.py
#     make sessao   ==  python ci/sessao.py --celula <x> --tarefa <y>
#
# `sessao` é o ÚNICO alvo daqui que escreve no mundo (worktree, venv, container).
# Ele é explícito de propósito: nenhum outro alvo o chama, e rodar `make doctor`
# nunca cria nada.
#
# `python`, nunca `python3`: o shim de python3 desta máquina resolve um problema
# local e não pode virar requisito arquitetural. Sobrescreva com PYTHON=... se o
# seu ambiente chamar o interpretador de outro jeito.
# =============================================================================
PYTHON ?= python

.PHONY: ajuda ci doctor freeze muralhas testador celula mergear esqueleto indice sessao boletim reservar reservas pr

ajuda:          ## lista os alvos (é o alvo padrão)
	@echo "Alvos da raiz — fachada de ci/ci.py:"
	@echo "  make sessao CELULA=x TAREFA=y   abre a sessao inteira (RITOS.md §1)"
	@echo "  make pr TITULO=... MENSAGEM=... commit + push + PR + registro embarcado"
	@echo "  make boletim                    o que o mundo e AGORA (antes de decidir)"
	@echo "  make reservar SUP=registro      o servidor DA o numero (nao adivinhe)"
	@echo "  make doctor            o ambiente consegue executar o trabalho?"
	@echo "  make ci                a mudanca respeita as invariantes?"
	@echo "  make freeze            so o freeze de contrato (todas as celulas)"
	@echo "  make muralhas          so cerca + orcamento + segredos"
	@echo "  make testador          so a suite adversarial do proprio portao"
	@echo "  make celula CELULA=x   os portoes de repositorio + o make ci da celula"
	@echo "  make mergear PR=22     confere os checks no GitHub e mergeia com confirmacao"
	@echo "  make indice            regenera armadilhas/INDICE.md a partir das entradas"
	@echo "  make esqueleto         o esqueleto que anda (e2e local, ESQUELETO-QUE-ANDA.md)"
	@echo ""
	@echo ""
	@echo "O freeze roda o exportador de cada celula, entao 'make ci' espera o"
	@echo "mesmo ambiente que .github/workflows/ci-celula.yml declara (ARMADILHAS.md §2)."
	@echo "Sem essas variaveis o freeze devolve ERROR, nao PASS — de proposito."
	@echo ""
	@echo "Sem make na maquina? Os mesmos caminhos, oficiais e equivalentes:"
	@echo "  $(PYTHON) ci/doctor.py"
	@echo "  $(PYTHON) ci/ci.py"
	@echo "  $(PYTHON) ci/contract_freeze.py"

ci:             ## roda todos os portoes de repositorio
	$(PYTHON) ci/ci.py

doctor:         ## diagnostica o ambiente (read-only, idempotente)
	$(PYTHON) ci/doctor.py

freeze:         ## contrato vivo x contrato congelado, em todas as celulas
	$(PYTHON) ci/contract_freeze.py

muralhas:       ## cerca de celula + orcamento de mudanca + guarda de segredos
	$(PYTHON) ci/ci.py --apenas muralhas

testador:       ## a suite que prova que o freeze reprova quando deve
	$(PYTHON) ci/ci.py --apenas testador

boletim:        ## o que o mundo e AGORA (PRs abertos, o que pousou, lei que mudou)
	$(PYTHON) ci/boletim.py

reservar:       ## make reservar SUP=registro — o servidor DA o numero (nao adivinhe)
	@test -n "$(SUP)" || { echo "ERROR: informe SUP=registro|armadilha"; exit 2; }
	$(PYTHON) ci/reservar.py numero $(SUP)

reservas:       ## o que esta reservado agora, lido do servidor
	$(PYTHON) ci/reservar.py listar

indice:         ## regenera armadilhas/INDICE.md (rode ao criar uma entrada nova)
	$(PYTHON) ci/indice_de_armadilhas.py

celula:         ## make celula CELULA=pagamentos
	@test -n "$(CELULA)" || { echo "ERROR: informe CELULA=<nome>"; exit 2; }
	$(PYTHON) ci/ci.py --celula $(CELULA)

mergear:        ## make mergear PR=22 — recusa merge com check vermelho
	@test -n "$(PR)" || { echo "ERROR: informe PR=<numero>"; exit 2; }
	$(PYTHON) ci/mergear.py $(PR)

esqueleto:      ## sobe o compose de dev do caminho e percorre a transacao inteira via curl
	bash e2e/esqueleto.sh

pr:             ## make pr TITULO="ci: x" MENSAGEM=m.txt CORPO=c.md ARQUIVOS="a b" DETALHE=d.txt
	@test -n "$(TITULO)" || { echo "ERROR: informe TITULO=\"<celula>: o que muda, para leigo\""; exit 2; }
	@test -n "$(MENSAGEM)" || { echo "ERROR: informe MENSAGEM=<arquivo com a mensagem do commit>"; exit 2; }
	@test -n "$(CORPO)" || { echo "ERROR: informe CORPO=<arquivo com o corpo do PR>"; exit 2; }
	@test -n "$(ARQUIVOS)" || { echo "ERROR: informe ARQUIVOS=\"caminho1 caminho2\""; exit 2; }
	@test -n "$(DETALHE)" || { echo "ERROR: informe DETALHE=<arquivo com o que o mantenedor vai ler>"; exit 2; }
	$(PYTHON) ci/pr.py --titulo "$(TITULO)" --mensagem-arquivo "$(MENSAGEM)" --corpo-arquivo "$(CORPO)" --detalhe-arquivo "$(DETALHE)" $(if $(TIPO),--tipo $(TIPO)) $(if $(GRAVIDADE),--gravidade $(GRAVIDADE)) $(if $(FRENTE),--frente $(FRENTE)) $(if $(EVIDENCIA),--evidencia "$(EVIDENCIA)") $(if $(CONTINUAR),--continuar) --arquivos $(ARQUIVOS)

sessao:         ## make sessao CELULA=quiz TAREFA=fuso-horario [FRASE="..."]
	@test -n "$(CELULA)" || { echo "ERROR: informe CELULA=<nome>"; exit 2; }
	@test -n "$(TAREFA)" || { echo "ERROR: informe TAREFA=<slug>"; exit 2; }
	$(PYTHON) ci/sessao.py --celula $(CELULA) --tarefa $(TAREFA) --frase "$(FRASE)"
