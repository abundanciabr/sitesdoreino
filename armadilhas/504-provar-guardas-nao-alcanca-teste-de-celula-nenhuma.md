---
schema_version: 2
armadilha: 504
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/provar_guardas.py
  - services/*/tests/*
sinal:
  - "baseline não passou integralmente no teste escolhido"
  - "sabotagem não produziu FAIL na chamada do teste"
  - "No module named .?pytest_jsonreport"
guarda:
  tipo: nenhum
  motivo: o instrumento reprova por comparacao de caminho, nao por excecao; um teste que provasse o alcance teria de rodar pytest dentro de uma celula real, e a fabrica so descobriu o defeito porque dois despachos tentaram usar o instrumento no mesmo dia
licao: "ci/provar_guardas.py so alcanca ci/tests/. O nodeid do relatorio vem relativo ao rootdir do pytest.ini da celula (tests/test_x.py::test_y) e e comparado com o alvo relativo a raiz (services/alunos/tests/test_x.py::test_y): nunca batem. Contorno: PYTEST_ADDOPTS=--rootdir=. e pytest-json-report no venv da celula. Segundo defeito: sabotar com pass mais comentario so compila em instrucao simples."
---

# 504: a prova de sabotagem não alcança teste de célula nenhuma

**Data:** 21/09/2026 · **Onde:** `ci/provar_guardas.py` · **Custo evitado:** duas
sessões descobrindo o mesmo defeito no mesmo dia, mais a prova por mutação feita
à mão em toda entrega de célula.

## Sintoma

O instrumento que a lei exige para provar guarda (RITOS.md) reprova sempre que o
teste alvo mora em `services/`, e reprova ANTES de sabotar coisa alguma:

```
ProvaInvalida: baseline não passou integralmente no teste escolhido; confira log_baseline
```

O `log_baseline` mostra o pytest verde. O teste passou; o instrumento é que não
reconheceu que passou. Em `ci/tests/` o mesmo comando funciona, o que faz o
defeito parecer culpa da célula.

## Causa

`selecionados()` (linha 209) decide se o pytest rodou o teste pedido comparando
literalmente o campo `nodeid` do relatório JSON com o alvo informado:

```python
return bool(testes) and all(t["nodeid"] == teste or t["nodeid"].startswith(teste + "[") for t in testes)
```

O `nodeid` nasce relativo ao **rootdir** do pytest, e cada célula tem o seu
`pytest.ini`, então ele sai como `tests/test_x.py::test_y`. O alvo que o despacho
informa é relativo à raiz do repositório, `services/alunos/tests/test_x.py::test_y`.
As duas cadeias nunca são iguais fora de `ci/tests/`, onde o rootdir por acaso é a
raiz. O despacho de alunos mediu o campo `root` do relatório saindo como
`...\bancada\services\alunos`, o que fecha o diagnóstico.

Há um segundo defeito no mesmo instrumento, independente deste: `DIALETOS`
(linha 63) sabota Python prefixando `pass  # ` na linha protegida. Isso só é
sintaxe válida quando a linha é uma instrução completa. Entrada de dicionário,
argumento nomeado de chamada em várias linhas e linha de `if` viram erro de
sintaxe, e o arquivo nem compila.

## Solução

Enquanto o conserto não entra, o contorno medido e confirmado em `pagamentos`,
na chamada do instrumento:

```bash
py -3.12 -m pip install pytest-json-report   # dentro do venv DA CÉLULA
PYTEST_ADDOPTS="--rootdir=." py -3.12 ci/provar_guardas.py <alvo>
```

Sem `pytest-json-report` no venv da célula não existe relatório nenhum para ler,
e o `--rootdir=.` é o que alinha o `nodeid` ao alvo. Para a linha protegida, não
aponte entrada de dicionário, argumento nomeado nem cabeçalho de `if`: aponte uma
instrução simples, ou o instrumento morre por sintaxe antes de medir qualquer
coisa. O conserto de verdade é tarefa própria na fila.

**Origem.** Medido em 21/09/2026 por dois despachos independentes que não se
falavam: um em `services/pagamentos` e outro em `services/alunos`.
