---
schema_version: 2
armadilha: 385
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  detector: test_o_corpo_nao_muda_so_porque_o_relogio_andou
  dono: ci/tests/test_vigia_do_pouso.py
gatilho:
  - .github/workflows/vigia-do-pouso.yml
  - ci/vigia_do_pouso.py
licao: quadro que se reescreve sozinho e promete "só quando muda" quebra a promessa por duas coisas invisíveis, e as duas em silêncio - um número que anda com o relógio DENTRO do conteúdo, e a quebra de linha que o `--jq` acrescenta e o arquivo não tem. Ponha o INSTANTE, nunca o "há N horas", e compare por `$(...)`, que come as quebras finais dos dois lados.
---

# 3.385 O quadro que se reescreve sozinho promete "só quando muda", e mente por dois motivos que ninguém vê

**Data:** 07/09/2026 · **Onde:** `.github/workflows/vigia-do-pouso.yml`, nas duas
primeiras passagens reais do vigia do pouso (TAR-167) · **Custo medido:** o
defeito nasceu no mesmo PR que criou o vigia e só apareceu porque a segunda
passagem foi disparada à mão; sozinho, ele transformaria o aviso em ruído em
menos de um dia.

## Sintoma

Um workflow mantém UM artefato idempotente (o corpo de uma issue, um comentário
de PR, um arquivo gerado) e traz a defesa contra ruído escrita no próprio YAML:

```bash
if [ "$ATUAL" = "$NOVO" ]; then
  echo "já diz exatamente isto — não reescrevo."
else
  gh issue edit "$EXISTENTE" --body-file denuncia.md
fi
```

Duas passagens seguidas, quatro minutos entre elas, com a lista de PRs
**idêntica** nas duas (runs `34081585426` e `34081787250`):

```
ESQUECIDOS=3
   🔴 #1216  ...  🔴 #1224  ...  🔴 #1244  ...
Issue #1288 atualizada com o quadro de agora.
```

O ramo do "não reescrevo" nunca roda. A defesa está escrita, passa nos testes,
e não defende nada. E o modo de falha é o pior que existe para um aviso: ele
não fica errado, fica **barulhento** - e barulho se ignora, que é o mesmo que
não avisar.

## Causa

São **duas** causas empilhadas, e as duas produzem o mesmo "mudou". Achar a
primeira e parar deixa a segunda de pé.

**1. Havia um número que anda com o relógio DENTRO do conteúdo.** A tabela dizia
`verde há 11 h`. De duas em duas horas isso vira `13 h`, e o corpo muda sozinho
com a lista parada. Qualquer "há N minutos", "faltam N dias", "atualizado às
HH:MM" tem o mesmo efeito: o conteúdo deixa de ser função do ESTADO e passa a
ser função do estado **mais o instante da leitura**, e comparação de
idempotência não sobrevive a isso.

**2. O `--jq` acrescenta uma quebra de linha que o arquivo não tem.** Medido:

```
$ gh issue view 1288 --json body --jq .body | tail -c 12 | od -c
0000000   o   /   r   e   p   o   >   `  \n
```

`Path.write_text("\n".join(linhas))` **não** termina em `\n`; a saída do `jq`
termina. O `diff` acusa diferença por causa dela, em toda passagem, para
sempre. O `tr -d '\r'` que já estava lá (fim de linha do Windows) resolve outra
coisa e esconde esta, porque dá a sensação de que a normalização foi feita.

## Solução

**Ponha o INSTANTE, nunca o tempo decorrido.**

```python
# antes:  | #1216 | verde há 11 h | ...
# depois: | #1216 | verde desde 06/09 16:51 UTC | ...
```

Ganha duas vezes: o quadro fica estável enquanto o estado for o mesmo, e o
leitor recebe um dado que **não fica velho entre escrever e ler** - "há 11 h"
está errado no minuto seguinte.

**Compare por substituição de comando, que normaliza os dois lados.**

```bash
ATUAL="$(gh issue view "$N" --json body --jq .body | tr -d '\r')"
NOVO="$(cat denuncia.md)"
if [ "$ATUAL" = "$NOVO" ]; then ...
```

`$( )` come TODAS as quebras finais, dos dois lados, sem ninguém precisar saber
qual dos dois tinha uma a mais.

## A régua, antes de escrever o `if` da idempotência

Duas perguntas de dois segundos, e as duas já custaram:

1. **"Tem algum número aqui dentro que muda sozinho?"** Se tem, o `if` é
   decoração. Troque por um instante, um id, um hash do estado - qualquer coisa
   que só mude quando o estado mudar.
2. **"Os dois lados da comparação vieram do mesmo lugar?"** Não vieram: um veio
   de um arquivo seu, o outro de uma API. Normalize os dois de propósito, e
   nunca confie que já estão normalizados porque você lembrou do `\r`.

E o guarda que fecha isto não é ler o YAML: é gerar o conteúdo **duas vezes,
com relógios diferentes**, e exigir que saiam iguais.

```python
agora = corpo(varrer(inventario, AGORA))
depois = corpo(varrer(inventario, AGORA + timedelta(hours=3)))
assert agora == depois
```

Com as horas de volta na tabela, esse teste fica vermelho na hora - foi como
ele foi provado.
