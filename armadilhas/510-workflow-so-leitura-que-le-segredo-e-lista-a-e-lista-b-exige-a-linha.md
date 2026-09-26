---
schema_version: 2
armadilha: 510
estado: guardada
degrau: 3
confianca: estrutural
custo_por_queda: medio
gatilho:
  - .github/workflows/
  - ci/mandato_por_faixa.py
  - ci/mergear.py
sinal:
  - "é senhas e chaves"
  - "falta a linha Mandato-do-mantenedor:"
  - "o mandato não alcança"
guarda:
  tipo: CI
  dono: ci/mandato_por_faixa.py
  detector: classificar
licao: Workflow que só lê `secrets.*` é Lista A por tocar CODEOWNERS de senhas e chaves; "somente leitura" não vira Lista B. Lista B também não dispensa a linha `Mandato-do-mantenedor:`, só troca o que ela cita; PR sem a linha, mesmo em Lista B, reprova em `--automatico`. A linha é UMA linha física: o regex lê só até a primeira quebra.
---

# 510: workflow de leitura que lê `secrets.` é Lista A, Lista B ainda precisa da linha, e a linha vale só na primeira linha física

**Data:** 26/09/2026 · **Onde:** `ci/mandato_por_faixa.py`, `ci/mergear.py` ·
**Custo evitado:** ciclos de `--automatico` recusado e mandato pedido tarde
demais, com o PR já pronto.

## Sintoma

PR #2117 alegou Lista B para `.github/workflows/operacoes-vps.yml` porque a
operação nova (`quiz-configuracao`) é fechada e somente leitura em produção.
PR #2116, só com testes em `ci/` (Lista B de verdade), ficou sem a linha
`Mandato-do-mantenedor:` e `mergear.py --automatico` recusou cinco vezes.

```
$ python ci/mandato_por_faixa.py --arquivos .github/workflows/operacoes-vps.yml ci/operacoes_vps.py
LISTA A: exige mandato nominal antes de editar
  .github/workflows/operacoes-vps.yml é senhas e chaves
```

```
$ python ci/mandato_por_faixa.py --arquivos ci/tests/test_operacoes_vps.py --faixa ci --corpo-arquivo <pr-sem-linha>.txt
LISTA B: falta a linha Mandato-do-mantenedor:
```

O corpo do #2117 ainda trazia a linha quebrada em três linhas de markdown. No
navegador ela parece inteira; no portão, só a primeira linha física conta, e os
caminhos das linhas seguintes somem:

```
$ python ci/mandato_por_faixa.py --arquivos .github/workflows/operacoes-vps.yml --faixa ci --corpo-arquivo <corpo-2117>.md
LISTA A: o mandato não alcança .github/workflows/operacoes-vps.yml
```

## Causa

`docs/decisoes/MANDATO-POR-FAIXA.md` classifica por caminho tocado, não pela
natureza da operação que o código executa: todo workflow de `.github/` que lê
`secrets.` entra em "senhas e chaves" (Lista A), mesmo que o script chamado
por ele nunca escreva nada. O despacho julgou pela operação (leitura, sem
efeito colateral) em vez de julgar pelo caminho tocado, e alegou Lista B para
um arquivo que a regra classifica como Lista A.

No sentido oposto, Lista B não é ausência de mandato: é mandato dado uma vez
por este documento, mas a linha continua obrigatória para o portão confirmar
que o autor sabe disso e cita a faixa certa. PR sem nenhuma linha, mesmo
tocando só caminhos de Lista B, reprova em `--automatico` do mesmo jeito que
reprovaria por CODEOWNERS.

`ci/mandato_por_faixa.py` e `ci/mergear.py` leem a linha com
`^Mandato-do-mantenedor: (.{20,})$` em `re.MULTILINE`, sem `re.DOTALL`: o que
vem depois da primeira quebra de linha não faz parte do mandato.

## Solução

Antes de alegar a faixa no corpo do PR, classifique pelo caminho, nunca pela
intenção do código:

```bash
python ci/mandato_por_faixa.py --arquivos <arquivos do PR> --faixa <faixa> --corpo-arquivo <corpo>
```

Saída 0 antes de `gh pr edit`. Se cair em Lista A, peça o mandato nominal
mesmo que a operação seja só leitura; se cair em Lista B, escreva a linha
citando a faixa e `docs/decisoes/MANDATO-POR-FAIXA.md` de qualquer forma,
mesmo sem nenhum caminho de CODEOWNERS no PR. Escreva a linha inteira numa
linha física só, com todos os caminhos como tokens separados por espaço, e só
então rode a conferência acima.
