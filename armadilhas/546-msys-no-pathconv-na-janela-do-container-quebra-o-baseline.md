---
schema_version: 2
armadilha: 546
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/sessao.py
  - ci/freeze-de-contrato.sh
sinal:
  - "can't open file '/tmp/[^']*': \\[Errno 2\\]"
guarda:
  tipo: nenhum
  motivo: é ambiente de quem chama, não do repositório. `MSYS_NO_PATHCONV=1` é uma decisão da janela de shell que a sessão abre, e o mesmo Git Bash serve tanto para digitar `git`/`gh` quanto para lançar `ci/sessao.py` com contêiner. Nenhum portão do repositório enxerga variável de ambiente do terminal antes de o comando começar a rodar; a defesa é a disciplina descrita na solução, não um detector.
licao: "MSYS_NO_PATHCONV=1 na janela que abre ci/sessao.py com contêiner vaza para o contrato-check: sem a tradução do MSYS, python.exe recebe um /tmp/... ao pé da letra e não acha o arquivo. Exporte a variável só em git/gh digitados; a janela do sessao.py roda sem ela."
---

# `MSYS_NO_PATHCONV=1` exportado na janela do `ci/sessao.py` com contêiner derruba o baseline no `contrato-check`

**Data:** 27/09/2026 · **Onde:** `ci/sessao.py --celula admin ...` (com contêiner),
passo `contrato-check` do `make ci` da célula, via `ci/freeze-de-contrato.sh` ·
**Custo evitado:** uma prova real inteira com contêiner, medindo um defeito de
contrato que não existe

## Sintoma

Medido no PR #2250, célula `admin`, tarefa `prova-wheel-base`. Com
`MSYS_NO_PATHCONV=1` exportado na mesma janela Git Bash que rodou
`python ci/sessao.py --celula admin --tarefa prova-wheel-base` (com contêiner),
a abertura passou do venv e da wheel, mas o baseline reprovou dentro do
`contrato-check`:

```
python: can't open file '/tmp/sitesdoreino-sessoes/admin-prova-wheel-base/ci/contract_freeze.py': [Errno 2] No such file or directory
```

Repetida a MESMA abertura, na mesma máquina, sem a variável exportada, o
baseline passou inteiro:

```
Baseline da BASE origin/main: make ci da célula admin = 2451 passed
```

Nada no repositório mudou entre as duas tentativas. A única diferença foi a
variável de ambiente na janela.

## Causa

`ci/freeze-de-contrato.sh` calcula o próprio diretório com `pwd` (linha 37,
`AQUI="$(cd -- "$DIR_DO_SCRIPT" && pwd)"`) e depois chama
`exec "$PY" "$AQUI/contract_freeze.py" "$@"`. Dentro do Git Bash, `pwd`
devolve caminho POSIX, e a bancada da sessão vive sob
`%TEMP%\sitesdoreino-sessoes\<célula>-<tarefa>` — um diretório que o Git Bash
monta como `/tmp/sitesdoreino-sessoes/...`.

Em uso normal, o MSYS traduz esse `/tmp/...` para o caminho Windows
(`C:\Users\...\AppData\Local\Temp\...`) automaticamente, no instante em que o
argumento é entregue a um executável nativo como `python.exe`. É exatamente a
tradução que `MSYS_NO_PATHCONV=1` desliga — por bom motivo em outro contexto
(armadilhas 201 e 334: ela salva um `git show origin/main:<caminho>` de virar
`origin\main;<caminho>`). Só que a variável exportada na janela vale para
TODO subprocesso que essa janela lançar depois, inclusive o `ci/sessao.py`
com contêiner e tudo que ele chama por baixo — o `contrato-check` entre eles.
Sem tradução, `python.exe` recebe o argumento `/tmp/.../contract_freeze.py`
ao pé da letra, não encontra esse caminho no sistema de arquivos do Windows,
e morre com `[Errno 2] No such file or directory`. A mensagem cita
`contract_freeze.py`, então parece defeito do contrato ou do exportador; é
falha de instrumento, uma etapa antes de qualquer coisa ser medida.

## Solução

Não existe forma de o portão distinguir as duas janelas: a variável é
legítima para digitar `git`/`gh` à mão e destrutiva para a janela que abre
`ci/sessao.py` com contêiner. A disciplina é separar as janelas:

```bash
# janela A — só para os comandos git/gh que você digita
export MSYS_NO_PATHCONV=1
git show origin/main:.claude/settings.json

# janela B — abre a bancada com contêiner; NUNCA exporte a variável aqui
python ci/sessao.py --celula admin --tarefa prova-wheel-base
```

Se o `contrato-check` reprovar com `can't open file '/tmp/...'`, confira
primeiro `echo $MSYS_NO_PATHCONV` na janela que abriu a sessão: se estiver
`1`, abra uma janela nova sem a variável e repita a MESMA abertura antes de
suspeitar do contrato.

**Categoria** (`RETROSPECTIVA-FASE-D`): o instrumento de medição contamina a
medição — a mesma classe das armadilhas 201, 334 e 489, todas em cima de
`MSYS_NO_PATHCONV` ou da escolha de interpretador nesta cadeia de scripts.
