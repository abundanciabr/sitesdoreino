---
schema_version: 2
armadilha: 529
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_sessao_persistente.py
sinal:
  - "alvo desconhecido: -C"
  - make local do Codex para sitesdoreino
  - "o `make` do PATH não é GNU Make"
gatilho:
  - ci/sessao.py
  - ci/ci.py
  - ci/tests/test_sessao_persistente.py
  - ci/tests/test_exit_do_make.py
licao: "Um `make` no PATH não prova GNU Make. A fachada `.codex/bin/make.CMD` do clone principal não entende `-C` e sai 2, e o baseline lia isso como `BASE REPROVOU` e mandava reportar a base. Hoje `ci/sessao.py` e `ci/ci.py` conferem `make --version` e param como erro de instrumento. Para medir, ponha o GNU Make antes da fachada no PATH."
---

# O `make` do PATH que não é GNU Make

**Data:** 27/09/2026 · **Onde:** passo de baseline de `ci/sessao.py`, `ci/ci.py --celula` e as suítes
`test_sessao_persistente.py -k baseline_real` e `test_exit_do_make.py` ·
**Custo evitado:** uma base verde presumida vermelha, com ordem de parar e reportar a falha dela

## Sintoma

No clone principal e em qualquer worktree novo de `origin/main`:

```
python -m pytest ci/tests/test_sessao_persistente.py -q -k baseline_real
```

```
[3/11] baseline: make ci da célula
        baseline sem evidência válida no cache; medindo a base
        `make ci`: C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\.codex\bin\make.CMD -C C:\Users\davia\AppData\Local\Temp\baseline-main-hcbfq9y2\arvore\services\quiz ci "SHELL=C:\Program Files\Git\usr\bin\sh.EXE" (cwd: ...)
E  sessao.ErroDeSessao: o baseline da BASE 46941524a3daffdb0d3efd5fb39fa90797744778 REPROVOU (exit 2)
FAILED ci/tests/test_sessao_persistente.py::test_baseline_real_de_duas_tarefas_usa_main_isolada[False]
FAILED ci/tests/test_sessao_persistente.py::test_baseline_real_de_duas_tarefas_usa_main_isolada[True]
```

Na mesma máquina, `python -m pytest ci/tests/test_exit_do_make.py -q` reprovava 6 testes pelo mesmo motivo.

## Causa

Não é o venv do quiz nem o teste. O `make` achado por `shutil.which("make")` é a fachada do Codex,
arquivo não rastreado em `.codex/bin/make.CMD` do clone principal, posta no PATH do usuário. Ela só
conhece os alvos da raiz (`ci`, `pr`, `sessao`...) e trata o primeiro argumento como alvo. A prova, com
um Makefile de uma linha:

```
make --version
make local do Codex para sitesdoreino
fachada para C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\.codex\bin\..\..\.venv\Scripts\python.exe

make -C <pasta-com-Makefile> ci "SHELL=C:\Program Files\Git\usr\bin\sh.EXE"
exit: 2
stdout: ERROR: alvo desconhecido: -C
stderr: Variável de ambiente <pasta-com-Makefile> não definida
        Variável de ambiente ci não definida
```

O exit 2 é o da fachada. O baseline lia como reprovação da base (`armadilhas/107`: 2 do GNU Make é
receita reprovada), e o erro mandava parar e reportar uma base que ninguém mediu. `where.exe make`
confirma que não há outro `make`, e `mingw32-make`/`gmake` também não existem.

## Solução

1. `ci/sessao.py` confere `make --version` antes de medir. Se não começa por `GNU Make`, para com
   `o make do PATH não é GNU Make: <caminho>`, código 2 (instrumento), sem criar a árvore da base.
2. `ci/ci.py` ganhou `e_gnu_make()`. `rodar_celula` devolve ERROR nomeando a fachada, e o
   `skipif` de `test_exit_do_make.py` usa a mesma função.
3. Para medir de verdade nesta máquina, o GNU Make precisa vir antes da fachada no PATH:

```
winget install ezwinports.make
```

O winget põe o atalho no fim do PATH do usuário, depois de `.codex\bin`. A ordem é decisão do
mantenedor, porque a fachada serve ao `make pr` do Codex.

Prova de que o teste está certo: com o GNU Make 4.4.1 portátil à frente do PATH só no processo,
a main sem mudança passa (`2 passed`) e as três suítes com o conserto passam (`195 passed`).
