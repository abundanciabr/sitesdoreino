---
schema_version: 2
armadilha: 334
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
  motivo: o erro nasce no shell do agente e não deixa diff; o sino reconhece a assinatura (a barra invertida com ponto-e-vírgula que o MSYS fabrica) e aponta para cá. A 201 também toca nessa hora, porque a assinatura dela é mais larga; esta entrada diz como distinguir
sinal:
  - `\\[A-Za-z0-9_-]+;\.[A-Za-z0-9_-]+`
---

# 334 — `git show origin/main:.claude/...` quebra no Git Bash do Windows, e só quando o caminho começa com ponto

**Data:** 05/09/2026 · **Onde:** qualquer sessão no Windows que leia do
`origin/main` pela ferramenta Bash (Git Bash, MSYS) um caminho cujo primeiro
segmento começa com ponto: `.claude/`, `.github/`, `.gitignore`, `.githooks/` ·
**Custo evitado:** uma rodada de diagnóstico errado, porque o sino aponta a
armadilha 201 e ela não é

## Sintoma

```
$ git show origin/main:.claude/settings.json
fatal: ambiguous argument 'origin\main;.claude\settings.json': unknown revision or path not in the working tree.

$ git cat-file -p origin/main:.claude/settings.json
fatal: Not a valid object name origin\main;.claude\settings.json
```

O mesmo comando com `origin/main:RUNBOOK-LOTES.md`, `origin/main:ci/fila.py` ou
`origin/main:ci/tests/test_fila.py` funciona. Só quebra quando o segmento logo
depois dos dois-pontos começa com ponto. E o sino das armadilhas toca a **201**
(`git show ... > arquivo` apaga o arquivo), porque a assinatura dela casa
qualquer `ambiguous argument` com ponto-e-vírgula dentro. Se o seu comando não
tinha `>`, não é a 201: é esta.

Medido em 05/09/2026, nas duas formas, no clone principal e numa bancada.

## Causa

O Git Bash é MSYS, e o MSYS converte argumentos que parecem lista de caminhos
POSIX (`a:b`) para o formato do Windows (`a;b`, com barras invertidas) antes de
o `git` receber. A heurística dele só dispara quando o pedaço depois dos
dois-pontos parece caminho, e um segmento começando com ponto parece. É o `git`
recebendo `origin\main;.claude\settings.json`, que não é revisão nenhuma.

O PowerShell não faz conversão nenhuma: lá o mesmo comando funciona.

## Solução

Duas formas, as duas medidas:

```bash
MSYS_NO_PATHCONV=1 git show origin/main:.claude/settings.json   # desliga a conversão
git show origin/main:./.claude/settings.json                    # o ./ tira o ponto da frente
```

A primeira é a receita para uma sessão inteira: `export MSYS_NO_PATHCONV=1` no
começo do comando e nada mais muda. A segunda serve para um comando só.

Régua para reconhecer: a mensagem traz **barra invertida e ponto-e-vírgula**
num caminho que você escreveu com barra e dois-pontos. Isso é o MSYS falando, não
o `git`.
