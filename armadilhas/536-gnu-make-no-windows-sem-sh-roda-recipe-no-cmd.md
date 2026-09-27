---
schema_version: 2
armadilha: 536
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_exit_do_make.py
sinal:
  - "'test' não é reconhecido como um comando interno"
  - "'{' não é reconhecido como um comando interno"
  - "CreateProcess.NULL, echo"
gatilho:
  - ci/sessao.py
  - ci/ci.py
  - services/*/Makefile
licao: "A armadilha/529 manda pôr o GNU Make antes da fachada no PATH, mas isso sozinho não basta no Windows. Sem sh.exe alcançável, o GNU Make roda cada recipe no cmd.exe e `test`/`{ }` (economia, pr, sessao, e Makefiles de célula com shell POSIX) reprovam; `e_gnu_make` só confere `--version` e `ci/ci.py` culpa a célula. Só `Git\\bin` também falha (falta echo.exe). A ordem verde: WinGet\\Links na frente, `Git\\usr\\bin` no FIM do PATH."
---

# 536: GNU Make no Windows sem sh roda recipe no cmd

**Data:** 27/09/2026 · **Onde:** alvos da raiz do `Makefile` (`economia`, `pr`, `sessao`) e Makefiles de célula (`ci/ci.py --celula`), medidos em bancada Windows nova · **Custo evitado:** achar que "GNU Make na frente do PATH" (armadilhas/529) já resolve, e só descobrir a quebra no meio de um rito, ou culpar a célula por uma reprovação que é do PATH

## Sintoma

Com GNU Make 4.4.1 (`%LOCALAPPDATA%\Microsoft\WinGet\Links\make.exe`) à frente do PATH e SEM
nenhum `sh.exe` alcançável (PATH restrito a WinGet\Links + `C:\WINDOWS\system32` + `C:\WINDOWS`):

```
$ env PATH="/c/Users/davia/AppData/Local/Microsoft/WinGet/Links:/c/WINDOWS/system32:/c/WINDOWS" make economia
'test' não é reconhecido como um comando interno
ou externo, um programa operável ou um arquivo em lotes.
'{' não é reconhecido como um comando interno
ou externo, um programa operável ou um arquivo em lotes.
make: *** [Makefile:83: economia] Error 1
```

Os alvos `pr` e `sessao` usam a mesma forma `test -n "..." || { echo ...; exit 2; }` (confirmável com
`make -n sessao CELULA=ci TAREFA=x SEM_CONTAINER=1`), então caem no mesmo erro.

## Causa

Sem `SHELL`/`sh.exe` localizável, o GNU Make do Windows executa cada linha de recipe via `cmd.exe`
em vez de um shell POSIX, e `test`, `{ }` e outras construções de shell não existem no `cmd`. Uma
correção parcial (só `C:\Program Files\Git\bin` no PATH, que tem `git.exe`, `bash.exe` e `sh.exe`
mas não os utilitários GNU) troca esse erro por outro: o make acha o `sh` mas ainda tenta rodar
comandos de uma linha só direto por `CreateProcess`, e falha por faltar `echo.exe` nessa pasta:

```
$ make -C services/falsa ci     # recipe: @echo tudo certo, com só Git\bin no PATH
process_begin: CreateProcess(NULL, echo tudo certo, ...) failed.
make (e=2): O sistema não pode encontrar o arquivo especificado.
```

`ci/tests/test_exit_do_make.py::test_receita_verde_e_PASS` reprova pelo mesmo motivo.

O problema não se limita aos alvos da raiz. Todo Makefile de célula usa shell POSIX (ex.:
`services/cursos/Makefile:20`, `@if [ -f .importlinter ]; then lint-imports; fi`). Nos dois modos
quebrados, `python ci/ci.py --celula <x>` roda `make ci`, quebra no shell e relata "make ci
reprovou", culpando a célula, porque `e_gnu_make()` só confere `make --version` e não confere se o
`sh` é alcançável. Sonda medida com um alvo `sonda:` de duas linhas (`@echo linha-simples` e
`@test -n x && echo linha-posix`), `make -C <pasta> sonda`:

```
fachada .codex\bin\make.CMD:           exit=2  ERROR: alvo desconhecido: -C
GNU Make sem sh:                       exit=2  'test' não é reconhecido como um comando interno
GNU Make + só Git\bin:                 exit=2  process_begin: CreateProcess(NULL, echo linha-simples, ...) failed
GNU Make na frente + Git\usr\bin fim:  exit=0  linha-simples / linha-posix
```

O conserto de código dessa porta (`e_gnu_make` também confirmar o `sh`) está em curso em outro PR;
esta entrada registra só a medição.

## Solução

Ordem de PATH medida e verde nesta máquina: `WinGet\Links` (só `make.exe`) na FRENTE, e
`C:\Program Files\Git\usr\bin` (que tem `sh.exe` e os utilitários GNU completos) no FIM do PATH —
nunca no meio, para não roubar `find`/`sort` do Windows que outras receitas podem esperar.

```
$ cmd //c "set PATH=C:\Users\davia\AppData\Local\Microsoft\WinGet\Links;C:\WINDOWS\system32;C:\WINDOWS;C:\Program Files\Git\usr\bin&& where find"
C:\Windows\System32\find.exe
C:\Program Files\Git\usr\bin\find.exe
$ cmd //c "set PATH=...&& where sort"
C:\Windows\System32\sort.exe
C:\Program Files\Git\usr\bin\sort.exe
$ cmd //c "set PATH=...&& where sh"
C:\Program Files\Git\usr\bin\sh.exe
$ cmd //c "set PATH=...&& where make"
C:\Users\davia\AppData\Local\Microsoft\WinGet\Links\make.exe

$ env PATH="...WinGet\Links:...system32:...WINDOWS:...Git/usr/bin" make economia
ERROR: informe TIPO=arquitetura|produto|contrato|revisao|escrita|diagnostico|teste|texto|espera
make: *** [Makefile:83: economia] Error 2

$ env PATH="...Git/usr/bin" make -C services/falsa ci
make: Entering directory '.../services/falsa'
tudo certo
make: Leaving directory '.../services/falsa'
```

Com essa ordem, a suíte inteira passa:

```
$ python -m pytest ci/tests/test_sessao.py ci/tests/test_sessao_persistente.py ci/tests/test_exit_do_make.py -q
195 passed in 92.19s
```

Origem: armadilha/529 mediu só a fachada `.codex\bin\make.CMD` contra o GNU Make; esta entrada mede
o GNU Make de verdade contra a ausência de `sh.exe`, o passo que a 529 recomenda mas não testa.
