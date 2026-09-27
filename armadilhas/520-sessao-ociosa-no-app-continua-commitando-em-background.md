---
schema_version: 2
armadilha: 520
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nao ha sinal de erro para uma sessao que esta viva e funcionando; o que evita a queda e conferir processo e reflog antes de tocar bancada alheia, e isso e leitura, nao maquina.
sinal:
  - "Unable to create .*index\\.lock"
gatilho:
  - "wt-*/"
licao: "Uma sessao ociosa no app do Claude nao esta morta: o despacho em background dela continua rodando (ci/pr.py, pytest, sessao.py) e commitando na propria bancada wt-* minutos depois de parecer parada. Antes de tocar bancada alheia: Get-CimInstance Win32_Process filtrando pr.py|pytest|sessao.py, e git reflog -4 --date=format:%H:%M para ver o horario do ultimo commit."
---

# 520: Sessão ociosa no app não está morta; o despacho em background segue commitando

## Sintoma

Às 01h25 de 27/09/2026, uma bancada `wt-*` que parecia ociosa (nenhuma
mensagem nova no app havia 17 minutos) recebeu um commit novo às 01h25,
gerado por um `ci/pr.py` da TAR-801 que estava rodando desde 01h08. Tocar
essa bancada no meio desse despacho arriscava conflito de índice do git ou
leitura de um estado a meio caminho.

## Causa

O app do Claude mostra a sessão como "ociosa" pela ausência de mensagem
nova na conversa, não pelo estado do processo que ela despachou. Um
`ci/pr.py` (ou `pytest`, ou `ci/sessao.py`) iniciado por essa sessão continua
rodando no sistema operacional depois que a conversa parou de escrever,
porque o despacho é assíncrono em relação à interface.

## Solução

Antes de tocar (editar, resetar, ou reabrir) uma bancada `wt-*` que não é a
sua, confira se algo ainda está vivo nela:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pr\.py|pytest|sessao\.py' } | Select-Object ProcessId, CommandLine
git reflog -4 --date=format:%H:%M
```

Um processo listado, ou um commit no reflog com horário recente, é sinal de
despacho vivo: espere terminar antes de mexer naquela árvore.

## Evidência

Bancada da TAR-801, 27/09/2026 01h08 a 01h25, relatado pela sessão que
fechou o sistema de experimentos.
