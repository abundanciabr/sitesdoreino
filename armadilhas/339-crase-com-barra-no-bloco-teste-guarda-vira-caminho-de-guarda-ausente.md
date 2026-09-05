---
schema_version: 2
armadilha: 339
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  motivo: o próprio `ci/guarda_dos_guardas.py` reprova na hora, com a frase "citado em INVARIANTES.md e ausente do disco", e a recusa nomeia o token; o que faltava era a entrada dizer que o token pode ser PROSA, e não um caminho errado
sinal:
  - "Teste-Guarda citado em INVARIANTES.md e ausente do disco"
  - "Guardas declarados que não são `.py` e não estão em ordem"
---

# Uma crase com barra na PROSA do bloco `Teste-Guarda:` vira "guarda ausente do disco"

**Sintoma.** Você declara um invariante novo em `INVARIANTES.md`, o arquivo de
teste existe e morde, e `python ci/guarda_dos_guardas.py` reprova duas vezes,
citando um caminho que você nunca escreveu como caminho:

```
  guardas/declaracao  FAIL   1 guarda(s) declarado(s) que não existem em disco
  guardas/nao-python  FAIL   1 guarda(s) fora do pytest sem dentes

Teste-Guarda citado em INVARIANTES.md e ausente do disco:
  [INV-CUR-P1] alunos/
```

O `alunos/` era um pedaço da frase que descreve a prova por mutação: *"uma rota
`alunos/` nova deixa o dente 2 vermelho"*.

**Causa.** O parser do bloco `- **Teste-Guarda:** …` conta como CAMINHO todo
token entre crases que tenha barra e não tenha espaço (`RE_TOKEN` em
`ci/guarda_dos_guardas.py`). A régua existe para separar
`services/x/tests/test_inv_y.py` de `make ci` e de `lint-imports`, e ela é
boa; o que ela não sabe é que a prosa do bloco pode citar uma rota, um prefixo
de URL ou um diretório entre crases sem querer declarar guarda nenhum. Como o
bloco vai até o próximo item em negrito, tudo o que você escreve depois da
lista de arquivos (a descrição da mutação, inclusive) está dentro da régua.

**Solução.** Dentro do bloco `Teste-Guarda:`, crase com barra é só para
caminho de guarda. Rota, prefixo e diretório citados na prosa saem sem crase
("uma rota nova de lista de alunos") ou vão para o `O quê:`/`Por quê:`, que o
parser não lê. A recusa já traz o token; não é preciso adivinhar qual foi.

**Origem.** Degrau 1.8 da célula `cursos` (TAR-154, PR #1062, 05/09/2026), ao
declarar [INV-CUR-P1]. Custou uma rodada do portão e um minuto de leitura do
regex.
