---
schema_version: 2
armadilha: 207
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
sinal:
  - `character value in \\x\{\} or \\o\{\} is too large`
---

# Contar um caractere não-ASCII no Git Bash devolve **zero em tudo**, e zero parece "não existe"

**Sintoma:** você quer saber quantos travessões (`—`), aspas curvas ou emojis
existem no repositório, escreve o que parece a forma correta, e o resultado é
uniforme e tranquilizador:

```
services: 0 arquivos
painel: 0 arquivos
docs: 0 arquivos
```

Nenhum erro na tela, três pastas, zero em todas. A conclusão natural é "o
projeto está limpo". **Estava errado por três ordens de grandeza:** as mesmas
pastas tinham 593, 293 e 134 arquivos com travessão.

O comando era:

```bash
for d in services painel docs; do
  echo "$d: $(grep -rlP '\x{2014}' "$d" 2>/dev/null | wc -l) arquivos"
done
```

**Causa — duas, e as duas silenciam de um jeito diferente:**

1. **O `grep` do Git Bash recusa `\x{2014}`.** Ele não está em modo UTF-8, então
   a sintaxe PCRE de ponto de código acima de `\xFF` estoura antes de procurar
   qualquer coisa: `grep: character value in \x{} or \o{} is too large`. O erro
   existe, mas foi para o `stderr` — e o `2>/dev/null`, posto ali para calar
   ruído de permissão, calou justamente o aviso que importava.
2. **Heredoc para o `stdin` do Python transforma acento em outra coisa.** A
   segunda tentativa foi medir em Python, com o caractere escrito direto no
   código:

   ```bash
   python - <<'PY'
   alvo = "…tarefa/evento fora do molde"   # com travessão dentro
   assert texto.count(alvo) == 1
   PY
   ```

   Falhou com `AssertionError: 0` num texto onde o trecho existia. O corpo do
   heredoc chega ao interpretador na página de código do console, não em UTF-8;
   a string do código e a string do arquivo viram sequências de bytes
   diferentes, e `count`/`replace`/`find` não casam mais. Aspas simples no
   delimitador (`<<'PY'`) protegem contra expansão do shell, **não** contra
   recodificação.

O que faz esta armadilha ser cara não é errar a conta: é que **os dois modos
falham para baixo**. Um devolve zero, o outro devolve "não encontrei" — as duas
respostas são indistinguíveis de um repositório limpo, e nenhuma pede atenção.
É o padrão 1 da `docs/decisoes/RETROSPECTIVA-FASE-D.md` (falso-verde) na
ferramenta de medição, que é onde ele custa mais: a decisão seguinte inteira
nasce de um número inventado.

**Solução — três, em ordem de preferência:**

1. **Se for travessão, não conte à mão: use o portão que já existe.**
   `python ci/travessao.py --listar` mostra arquivo, linha e frase, já despido
   dos comentários (que ninguém publica). É a única contagem que a CI reconhece.
2. **Para qualquer outro caractere, case o literal**, sem sintaxe de ponto de
   código: `grep -rl -- '—' services`. O `--` antes do padrão evita que um
   caractere seja lido como opção. Funciona porque o byte procurado é o mesmo
   byte do arquivo, sem tradução no meio.
3. **Se precisar de Python, o código vai para um ARQUIVO**, lido com
   `encoding="utf-8"` explícito, nunca pelo `stdin` de um heredoc. Escreva o
   script com a ferramenta de escrita da sessão e rode `python script.py`.

**Regra de bolso que resolve as duas de uma vez:** ao medir algo que não é
ASCII, meça primeiro uma coisa que você SABE que existe. Se a sonda não acha o
caso que você acabou de ver com os olhos, o problema é a sonda — e não o
repositório.

**Contexto:** descoberto em 30/08/2026, ao levantar a dívida para a muralha do
travessão (`CLAUDE.md`, "Nenhum texto publicado sai com travessão"). O primeiro
número medido foi **zero em todo o repositório**; o verdadeiro era 125
travessões publicados em 19 arquivos.
