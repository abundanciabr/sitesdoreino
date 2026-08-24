# `re.error: unterminated character set` num regex que está certo

**Sintoma:** você roda um script Python pelo Bash — heredoc `<<'PY'` (delimitador entre
aspas, que em bash *não* processa nada) ou `python -c` — e um regex correto estoura:

```
re.error: unterminated character set at position 5
```

O mesmo regex, colado num arquivo `.py` e rodado igual, funciona. Trocar `'...'` por
`r'...'` **não muda nada** — que é o detalhe que faz perder tempo, porque a hipótese
óbvia ("esqueci o raw string") já está descartada e não sobra suspeito.

**Causa: a contrabarra dupla some no transporte, antes de o shell existir.** Cada `\\`
escrito no comando chega ao processo como `\`. Medido nesta máquina, com o delimitador
do heredoc entre aspas simples (que deveria preservar tudo):

| Escrito no comando | O que o Python recebe |
|---|---|
| `'a\b'` | `'a\x08'` — uma barra chegou, e `\b` virou *backspace* |
| `'a\\b'` | `'a\x08'` — **as duas viraram uma**, mesmo resultado do caso acima |
| `'a\\\\b'` | `'a\\b'` — só com QUATRO sobram duas |

Aplicado ao caso real: `re.findall(r'"((?:[^"\\]|\\.)*)"', texto)` chega ao Python como
`"((?:[^"\]|\.)*)"`. Ali o `\]` deixou de fechar a classe de caracteres e virou um
colchete literal escapado — daí "unterminated character set". O regex nunca esteve
errado; ele foi **reescrito no caminho**.

Isso morde qualquer coisa cheia de contrabarra: regex com `\\`, `\d`, `\s`, `\.`,
caminhos de Windows (`C:\Users\...`), `printf '%s\\n'`.

**Solução — não passe contrabarra por comando: escreva o script num arquivo.**

Use a ferramenta `Write` para criar o `.py` (o conteúdo vai direto ao disco, sem passar
por shell nenhum) e depois só execute:

```bash
python /caminho/do/scratchpad/meu_script.py
```

Foi o que destravou o caso: o mesmo trabalho que falhava duas vezes por heredoc rodou
**de primeira** como arquivo. Para trabalho descartável, o scratchpad da sessão serve —
não suja o repositório.

**Se for inevitável fazer inline**, duas saídas que também fecham:

- **Dobre tudo:** escreva `\\\\` onde você quer `\\`. Funciona e é ilegível — só para
  uma linha, nunca para um script.
- **Fuja da contrabarra:** quase todo regex tem forma sem ela. `[^"\\]` vira
  `[^"] `+ tratamento à parte; `\d` vira `[0-9]`; `\s` vira `[ \t]`… e `\.` vira
  `re.escape(".")`.

**Como confirmar em 5 segundos, antes de culpar o seu código:**

```bash
python -c "print(len('a\\b'))"
```

Respondeu `2` (em vez de `3`)? O transporte está comendo contrabarra — o problema não é
o seu regex.

> Parente próximo, mesma família: `armadilhas/006` (arquivo escrito no bash não é
> encontrado pelo Python em seguida) e `armadilhas/007` (path `/c/Users/...` dentro de
> código Python). Os três são a mesma lição: **o que atravessa a fronteira
> Bash → Python nesta máquina não chega como você escreveu.**
