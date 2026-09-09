schema_version: 2
armadilha: 428
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - services/pages/apps/core/clients.py
  - infra/provisionar-pages.sh
  - infra/provisionar-par-do-portfolio-com-a-admin.sh
  - infra/provisionar-admin.sh
  - ci/tests/test_nome_do_par_pages_admin.py
guarda:
  tipo: CI
  dono: ci/tests/test_nome_do_par_pages_admin.py
  detector: test_nomes_do_par_pages_admin_sao_iguais_em_todas_as_casas
sinal: 'o consumidor lê uma chave de ambiente que os roteiros de provisionamento não escrevem com o mesmo nome'
licao: 'Cópia consciente de nome entre consumidor, escritores e molde precisa de um teste textual com mutação; presença isolada em cada arquivo não prova que o par conversa.'
---

# 428: Cópia consciente de nome sem guarda

**Data:** 09/09/2026. **Onde:** o par `pages` e `admin` usado pela fila do
portfólio.

## Sintoma e causa

O consumidor lia `ADMIN_API_URL` e `ADMIN_API_TOKEN`, enquanto os roteiros e o
molde repetiam esses nomes à mão. A suíte podia ficar verde se apenas o
consumidor mudasse, deixando a fila fechada por uma chave que nenhum env
escrevia.

## Solução e evidência

O guarda novo extrai os nomes lidos pelo `AdminClient`, confere a lista, o
heredoc, o roteiro do par, os moldes e o prefixo aceito pelo provedor. A
mutação de cada casa reprova o teste; a fonte original passa.
