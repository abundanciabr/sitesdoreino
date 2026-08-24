# Guarda de mtime que só mede ANTES não protege nada

**Sintoma:** você transforma um arquivo grande que outra sessão pode estar editando,
protege a operação lendo o `mtime` antes de começar, o guarda passa — e mesmo assim o
resultado não bate com a cópia de segurança que você tirou no mesmo comando. No caso
medido (23/08/2026, corte do `painel-fundacao.html`): o backup ficou com 26 episódios
e o arquivo transformado com 27. Ninguém perdeu trabalho, mas provar isso custou
quatro rodadas de investigação no meio da janela.

**Causa:** a janela de risco é a **transformação inteira** (ler → processar →
escrever), não o instante anterior a ela. O guarda tinha esta forma:

```bash
ANTES=$(stat -c %Y alvo) && cp alvo alvo.bak && DEPOIS=$(stat -c %Y alvo)
[ "$ANTES" = "$DEPOIS" ] || { echo "PAROU POR SEGURANCA"; exit 1; }
python transformar.py alvo --aplicar     # <-- a outra sessão escreveu AQUI
```

Ele prova que o arquivo ficou parado durante o `cp`, e conclui — sem base — que vai
continuar parado durante o que vem depois. A outra sessão escreveu entre o `cp` e a
leitura do script; o script leu a versão NOVA (correto) e o backup ficou com a VELHA.
O sintoma aparece só quando alguém compara os dois, e parece perda de dados.

**Solução:** medir antes E depois da transformação inteira, e falhar alto se mudou:

```bash
ANTES=$(stat -c %Y alvo); cp alvo alvo.bak
python transformar.py alvo --aplicar
# o script escreve o alvo, então compare com o mtime do BACKUP, não do alvo:
[ "$(stat -c %Y alvo.bak)" = "$ANTES" ] || echo "PAROU: o backup não é o que foi transformado"
```

Melhor ainda quando o script permite: **transformar a partir do backup**
(`transformar.py alvo.bak --saida alvo`) — aí a cópia de segurança é, por construção,
exatamente a entrada que gerou a saída, e a corrida deixa de existir.

**Vale a pena lembrar por que o dano foi zero:** a transformação lia o arquivo uma vez
e escrevia uma vez, sem cache; ela capturou o trabalho da outra sessão em vez de
descartá-lo. Uma transformação que tivesse lido o arquivo ANTES (para planejar) e
escrito DEPOIS (a partir do plano velho) teria apagado a escrita alheia em silêncio.

**Origem:** Lote A (card C2 do PLANO-10X), 23/08/2026 — duas sessões de Claude Code
trabalhando no mesmo repositório ao mesmo tempo. Ver também
[§8 — lote: outra sessão escrevendo no seu worktree].
