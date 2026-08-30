---
schema_version: 2
armadilha: 206
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/conftest.py
sinal:
  - `JSONDecodeError: Expecting value: line 1 column 1 \(char 0\)`
  - `alarme-main +FAIL`
---

# Tirar um gerado do Git é meia cura: falta dizer QUEM o monta em cada chamador

**Sintoma.** Um arquivo gerado sai do Git para acabar com conflitos entre sessões
paralelas, o PR da mudança fica **todo verde**, e a `main` fica **vermelha logo
depois do merge**. Os testes que leem o gerado estouram com
`JSONDecodeError: Expecting value: line 1 column 1 (char 0)` (ou
`FileNotFoundError`), e o `portao-de-deploy` recusa publicar por
`alarme-main FAIL` — corretamente, porque ele é fail-closed. Resultado: **nenhum
merge chega ao site**, inclusive os de quem não tem nada a ver com a mudança.

**Causa.** "Tirar do Git" tem duas metades, e só a primeira é visível:

1. o arquivo sai do índice e ganha linha no `.gitignore` — **fácil de lembrar**;
2. **cada chamador que lê o arquivo passa a precisar de quem o monte antes** —
   fácil de esquecer, porque o autor da mudança tem a árvore dele já
   materializada e nunca vê o modo de falha.

Medido em 30/08/2026 (TAR-022, PR #580): `armadilhas/INDICE.md`,
`GUARDAS.json` e `SINAIS.json` saíram do Git. O workflow `muralhas` continuou
verde porque ele roda `ci/ci.py --apenas muralhas` **antes** do
`--apenas testador`, e a muralha materializa de passagem. O job
`guardas do repositório` do `alarme-main` roda a suíte **sem** passar pelas
muralhas — e numa árvore recém-clonada do runner os três arquivos simplesmente
não existiam.

**Solução.** Materialize na **porta da suíte**, não num passo de YAML: um passo
conserta um workflow, e a suíte quase sempre tem mais de um chamador (aqui:
`muralhas`, `alarme-main` e a pessoa que roda `pytest ci/tests` na mão — e esta
última não tem YAML nenhum onde encaixar o passo). Uma fixture
`scope="session", autouse=True` no `conftest.py` chama o gerador contra a raiz
real antes de qualquer teste. É a mesma escolha de "uma definição só" que o
resto desta casa faz.

**Como conferir que a cura vale**, e é a única prova que conta: **apague os
gerados** e rode a suíte. Sem a fixture, `pytest ci/tests/test_guarda_declarada_e_sino.py`
devolve `2 failed, 24 passed`; com ela, `26 passed`, e `python ci/ci.py --apenas
testador` fecha `1126 passed` a partir da árvore vazia. Rodar com os arquivos
presentes não prova nada — é exatamente o ponto cego do autor da mudança.

**A regra que fica, maior que o caso:** ao desversionar um gerado, liste os
chamadores que o LEEM antes de apertar o `git rm --cached`, e prove a cura numa
árvore que não tem o arquivo. E desconfie de PR verde numa mudança de
versionamento: se nenhum check de PR exercita o caminho, o verde não mediu o que
importa — foi assim que este furou.
