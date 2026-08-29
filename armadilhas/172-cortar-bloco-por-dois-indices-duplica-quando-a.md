# Cortar um bloco com `s[:i] + s[j:]` DUPLICA o arquivo quando `j < i`

**Sintoma.** Um script de edição "remove" um bloco de código e o arquivo **cresce**.
Funções aparecem duas vezes; o `grep` acha dois `def` iguais; o Python nem sempre
reclama (a segunda definição só sobrescreve a primeira). No caso real: um `api.py`
de 46 KB virou 84 KB, com um handler inteiro duplicado, e o único sinal foi um
`grep -n` que mostrou o mesmo comentário em duas linhas distantes.

**Causa.** O padrão comum para tirar um trecho é:

```python
i = s.index("INICIO_DO_BLOCO")
j = s.index("ANCORA_SEGUINTE")
s = s[:i] + s[j:]          # só funciona se j > i
```

Se a âncora seguinte aparece **antes** do bloco no arquivo, `j < i` e a conta vira
uma **cópia**: tudo entre `j` e `i` passa a existir duas vezes. Nenhuma exceção é
levantada — `str.index` achou as duas coisas, e ambas existem mesmo.

Foi exatamente o caso aqui: eu quis cortar o handler `delete` usando o `patch` como
âncora final, sem notar que, naquele arquivo, o `patch` era declarado **acima** do
`delete`.

**Solução.** Três linhas de disciplina, e a primeira sozinha já pega o caso:

```python
assert j > i, "a ancora seguinte esta ANTES do bloco — o corte viraria copia"
```

- **afirme a ordem** (`assert j > i`) antes de cortar;
- **compare os tamanhos**: `assert len(depois) < len(antes)` numa remoção;
- quando o bloco a remover é o **último** do arquivo, não procure âncora nenhuma —
  corte com `s[:i]` e confirme com `resto.count("@router.") == 1` (ou equivalente)
  que não havia mais nada depois dele.

**Por que vale uma entrada.** Edição por script é como um agente mexe em arquivo
grande, e este erro **não reprova em lint nem em teste**: código duplicado que
sobrescreve a si mesmo continua rodando. O que salvou foi olhar o diff — o hábito
de conferir `git diff --stat` depois de toda edição por script custa dois segundos
e é a única barreira barata contra isso.

**Onde já mordeu.** `services/alunos/apps/core/api.py`, 29/08/2026 (PR #476).
