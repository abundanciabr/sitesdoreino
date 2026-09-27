---
schema_version: 2
armadilha: 528
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o validacao.json e escrito por quem chama o ci/pr.py, e so essa pessoa sabe qual venv pertence a celula; um portao generico nao pode adivinhar o caminho certo do executavel.
sinal:
  - "No module named 'httpx'"
gatilho:
  - "ci/pr.py"
licao: "declarar so \"python\" no primeiro elemento de um comando do validacao.json do ci/pr.py roda o Python base do Windows, sem Django, httpx nem pytest da celula, e a validacao reprova com ModuleNotFoundError. Declare o executavel absoluto do venv da celula (ex: services/<celula>/.venv/Scripts/python.exe) no primeiro elemento de cada comando."
---

# 528: `"python"` genérico no `validacao.json` roda o Python base do Windows

**Data:** 27/09/2026 · **Onde:** validação local do `ci/pr.py` numa célula com
venv próprio · **Custo evitado:** validação reprovada por dependência
ausente, achando que o teste está quebrado

## Sintoma

Um comando de `validacao.json` começando com `"python"` (sem caminho) rodou
o Python base instalado no Windows, não o interpretador do venv da célula.
Como esse Python base não tem Django, `httpx` nem `pytest` instalados, a
validação reprovou com:

```
ModuleNotFoundError: No module named 'httpx'
```

## Causa

`ci/pr.py` executa cada comando de `validacao.json` como está escrito. Se o
primeiro elemento é só `"python"`, o sistema resolve pelo `PATH`, e no
Windows isso costuma apontar para o Python base, não para o
`services/<celula>/.venv/Scripts/python.exe` onde as dependências da célula
estão instaladas.

## Solução

Declare o caminho absoluto do executável do venv da célula como primeiro
elemento de cada comando, por exemplo:

```json
["C:/Users/.../services/cursos/.venv/Scripts/python.exe", "-m", "pytest", "..."]
```

Antes de escrever um `validacao.json` novo, confira se a lição já existe
(`python ci/consultar_armadilhas.py "Python base"` e
`"validacao.json"`); nenhuma entrada prévia foi encontrada em 27/09/2026.

## Evidência

Validação local do `ci/pr.py`, 27/09/2026, reprovada por `ModuleNotFoundError`
até o comando ser trocado para o `python.exe` do venv da célula.
