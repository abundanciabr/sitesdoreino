---
schema_version: 2
armadilha: 495
estado: documentada
degrau: 8
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: distinguir "tarefa citada por engano no texto" de "tarefa de fato entregue" exige julgamento sobre o conteudo do PR; um teste de CI nao consegue provar que a TAR mencionada no corpo nao e a que o trabalho resolve sem reimplementar a leitura humana do diff.
sinal:
  - "_identificar_tarefa"
  - "apontou a tarefa errada"
gatilho:
  - ci/pr.py
licao: "Nunca cite TAR-NNN no corpo/mensagem de um PR salvo a TAR de fato entregue. Sem tarefa reivindicada pelo ramo, ci/pr.py::_identificar_tarefa (linha 663) varre o corpo por qualquer TAR-NNN citado e a adota como concluida; o pouso automatico fecha essa TAR mesmo aberta de verdade."
---

# 495: `ci/pr.py` fecha a TAR só citada no corpo do PR, não a entregue

## Sintoma

O PR #1774 ("funil: a vitrine reconhece o visitante que volta") entregava
TAR-512, mas o corpo do PR também mencionava TAR-508 em algum trecho de
contexto. O recibo embarcado deu TAR-508 por concluída. TAR-508 continuava
aberta de verdade, sem nenhum commit seu no PR. A correção exigiu um PR
inteiro à parte, o #1777 ("painel: corrigir a tarefa que o recibo do PR
1774 deu por resolvida"), com o registro `painel/registros/20260919-066`.
Nenhum comando falhou; `ci/pr.py` rodou limpo e publicou o PR normalmente.

## Causa

`ci/pr.py::_identificar_tarefa` (linha 645) resolve a tarefa entregue nesta
ordem: `--tarefa` explícito, tarefa da abertura de sessão, tarefa
reivindicada pelo ramo no estado calculado da fila e, **só se nada disso
existir**, varre o TÍTULO e o CORPO do PR por qualquer `TAR-\d{3,}` citado
(linhas 661 e 663, via `tarefas_citadas`). Esse último recurso existe para
não travar um fechamento legítimo sem vínculo formal, mas não distingue
"esta TAR é a que este PR resolve" de "esta TAR apareceu no texto por outro
motivo" (contexto, referência cruzada, exemplo). Qualquer menção solta
basta para fechar a tarefa errada.

## Solução

Nunca escreva `TAR-NNN` no corpo, na mensagem ou no detalhe de um PR a
menos que essa TAR seja exatamente a entregue por aquele PR. Se precisar
citar uma tarefa relacionada sem reivindicá-la (contexto, tarefa que gerou
a lição, tarefa corrigida por outro PR), escreva o número sem o prefixo
`TAR-` completo junto de dígitos que casem o padrão, ou descreva por extenso
("a tarefa que virou o PR #1774"). Depois de abrir ou continuar um PR com
`--tarefa` ausente, confira `gh pr view <N> --json body` procurando por
`TAR-\d+` inesperado antes de deixar o pouso automático rodar.

## Evidência

PR #1774 (entrega de TAR-512) e PR #1777 (conserto), registro
`painel/registros/20260919-066-o-recibo-do-pr-1774-apontou-a-tarefa-errada.js`.
`ci/pr.py` linhas 645-677, especialmente 661 e 663, conferidas nesta sessão.
