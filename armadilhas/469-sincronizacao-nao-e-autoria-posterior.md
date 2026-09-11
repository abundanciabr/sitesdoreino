---
schema_version: 2
armadilha: 469
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/fila.py
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
  detector: test_medir_linhagem_separa_sincronizacao_de_autoria
  motivo: sincronizar a base e escrever codigo depois da prova exigem vereditos distintos
licao: Percorra first-parent e confira a ancestralidade do pai lateral contra a base da integracao. Para sincronizacao de dois pais, remerge diff preserva a autoria da resolucao; diff final ou exclusao por arquivo esconde alteracoes revertidas.
---

# 469: Sincronização não é autoria posterior

## Sintoma

A reconciliação de TAR-332 e TAR-325 recusava código recebido da main como
alteração posterior à revisão submetida, nos PRs 1549 e 1533.

## Causa

`--diff-merges=first-parent` escolhe o diff do merge, mas não restringe a
travessia do histórico. Sem `--first-parent`, os commits laterais também eram
medidos. Mesmo limitando a travessia, o diff contra o primeiro pai inclui o
código sincronizado.

## Lição

O pai lateral só representa base quando é ancestral do primeiro pai da
integração final. Nesse caso, o remerge diff de dois pais mede o que a
resolução acrescentou. Outros merges permanecem medidos contra o primeiro
pai. Git não oferece remerge diff para merges com mais de dois pais, então
esses também conservam a medição contra o primeiro pai.

## Evidência

O cenário de sincronização reprovou antes da correção. Sete cenários em Git
real passaram depois. Remover first-parent reprovou a sincronização;
desligar o diff reprovou as duas resoluções; ignorar ancestralidade reprovou
o ramo lateral. Autoria posterior no próprio arquivo sincronizado e sua
reversão continuam recusadas. Forçar remerge em três pais perdeu o diagnóstico
do código e reprovou a guarda. As duas linhagens reais passaram sem eventos
de reconciliação.
