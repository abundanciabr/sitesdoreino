---
schema_version: 2
armadilha: 473
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/mapa_de_execucao.py
guarda:
  tipo: CI
  dono: ci/tests/test_mapa_de_execucao.py
  detector: test_seletores_reconciliam_draft_fora_da_bancada_corrente
licao: A pasta que consulta um PR não identifica sua tentativa. Resolva a TAR pelo evento ou pelo ramo do dono, localize a worktree desse ramo e preserve como NÃO MEDIDO o que não foi localizado. Código local diferente do remoto exige reconciliar o fechamento antes da revisão final.
sinal:
  - consulta feita fora da bancada devolve o ramo corrente como dono do trabalho
---

# A consulta não é a bancada da tentativa

O mapa aceitava TAR, mas usava o checkout corrente para descrever a retomada.
Um draft ainda sem evento de submissão também não podia ser encontrado pelo
número. A consulta a partir do espelho passava a descrever outra bancada.

O vínculo agora vem da submissão explícita ou da combinação do ramo do PR com
o dono calculado pelos eventos. A worktree é localizada pelo ramo exato. Uma
referência textual à TAR não concede esse vínculo. Se a bancada não estiver
montada, seu caminho, SHA e alterações ficam desconhecidos.

Os testes consultam PR, ramo, caminho e sintoma a partir da main e conferem a
identidade original. Outro cenário prova que uma revisão local ainda não
enviada precisa passar pelo fechamento antes de pedir revisão do SHA remoto.
