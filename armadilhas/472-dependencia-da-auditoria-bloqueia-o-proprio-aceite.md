---
schema_version: 2
armadilha: 472
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `a fila impõe corretamente a dependência declarada, mas não consegue inferir que o aceite da predecessora será produzido pela tarefa sucessora; distinguir ordem técnica de relação histórica exige julgamento no despacho.`
sinal:
  - `está 'bloqueada' \(esperando TAR-[0-9]+\)`
gatilho:
  - fila/tarefas/
  - ci/fila.py
licao: `Uma auditoria que produz o aceite da entrega auditada não pode depender da conclusão administrativa dessa mesma entrega. Registre a filiação na origem e use depende_de somente quando a predecessora precisa estar concluída antes de o trabalho começar.`
---

# 472: A dependência da auditoria bloqueia o próprio aceite

## Sintoma

A entrega técnica já está integrada e publicada, mas a nova tarefa de auditoria
fica bloqueada esperando a tarefa auditada. O aceite que permitiria reconciliar
a predecessora faz parte da própria auditoria, então nenhuma das duas pode
avançar.

## Causa

Filiação histórica e ordem de execução foram representadas pelo mesmo campo.
`depende_de` significa que a predecessora precisa estar concluída antes de a
sucessora começar. Ele não significa apenas que uma tarefa nasceu de outra.
Quando a sucessora é quem produz o aceite final, essa aresta cria um ciclo
administrativo mesmo com o código já publicado.

## Lição

Em tarefa de auditoria, registre a entrega auditada em `origem`. Declare
`depende_de` somente quando a evidência necessária ainda não existe e precisa
ser produzida pela predecessora antes do início. Se a auditoria produz o aceite
que fecha a predecessora, a relação é histórica, não uma dependência de
execução.

## Evidência

TAR-348 nasceu com dependência de TAR-338 e `python ci/fila.py pegar TAR-348`
recusou a reivindicação porque TAR-338 aguardava reconciliação. A entrega de
TAR-338 já estava publicada no PR #1561, e o registro de aceite era um dos
resultados exigidos de TAR-348. Remover a aresta antes do primeiro commit,
preservando TAR-338 em `origem`, deixou a auditoria reivindicável sem duplicar
tarefa nem alterar a história publicada.
