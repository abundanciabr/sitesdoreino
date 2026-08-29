# Espera sem teto parece trabalho — o mantenedor olha a janela e ela mente por omissão

**Sintoma:** a janela do Claude Code mostra o robô "trabalhando, executando,
fazendo algo". Passam horas. No fim o robô confessa: *"eu estava esperando algo
me responder, mas esse algo quebrou e daí eu não pude continuar"*. O mantenedor
— que olha a tela dia e noite — não tinha COMO distinguir: espera sem fim é
visualmente idêntica a trabalho.

Medido: 2h de silêncio num laço `until` aberto em 28/08/2026; dias inteiros
perdidos em episódios anteriores (relato do mantenedor em 29/08/2026, que
originou esta entrada).

**Causa — três fatos somados:**

1. **Nenhuma chamada de ferramenta sozinha dura horas** (o Bash do harness tem
   teto de 10 min em primeiro plano). As horas vêm de comando em **segundo
   plano sem teto interno**: background só re-invoca o agente QUANDO o comando
   termina — um comando que nunca termina nunca re-invoca. E foi **medido em
   29/08/2026: o campo `timeout` do Bash NÃO se aplica a `run_in_background`**
   (um `sleep 300` com timeout de 10s sobreviveu os 300s inteiros).
2. **Nada no harness dispara DURANTE uma ferramenta** — hooks são antes e
   depois. Um poller pendurado não emite nada, e o stdout de um Bash em
   primeiro plano só chega no fim.
3. **A lição existia e não alcançava ninguém**: "esperas em background precisam
   de limite" morava só na memória privada do mantenedor. Robô que nasce num
   worktree lê as leis do repositório, não a memória dele — garantia sem
   mecanismo apodrece (RETROSPECTIVA-FASE-D §2; o cofre `refs/reservas/*`
   vazio por dias é a outra prova viva).

**Solução — não prometa falar: use a espera que fala sozinha.**

```bash
python ci/esperar.py --run <id-do-run> --teto 20 --dizendo "o deploy da admin"
```

Rodado pela ferramenta **`Monitor`** do harness (cada linha do stdout vira
mensagem na conversa AO VIVO — medido em 29/08/2026), com `timeout_ms` MAIOR
que o teto. O contrato: **partida** (o que espero, teto, plano Z), **batimento**
a ~60s com o estado OBSERVADO lá fora (relógio nu é silêncio com batimento
bonito), e **desfecho sempre barulhento** — verde, reprovado, teto estourado ou
"não consegui medir" (que nunca vira verde). Ao estourar, `--ao-estourar pousar`
executa o plano Z em vez de só anunciá-lo.

**Antes de esperar, pergunte se a espera precisa existir.** Checks de PR não se
esperam: `python ci/mergear.py <N> --pousar` e siga (RITOS.md §2, armadilhas/156).
A espera que a lei manda ter é o veredito do run de deploy (CLAUDE.md).

**Três formas de esperar que continuam erradas mesmo com voz:**

- `gh run watch` / `gh pr checks --watch` — espera muda, sem teto, em primeiro
  plano (morre no timeout do Bash sem dizer por quê).
- `until …; do sleep …; done` / `while true` sem teto — o laço das 2h.
- `run_in_background` de qualquer comando que pode pendurar — sem teto interno
  ele fica pendurado PARA SEMPRE, invisível (fato medido, acima). Prefixe com
  `timeout <segundos>` ou use o `esperar.py`.

**Origem:** relato do mantenedor em 29/08/2026 + medições da mesma data
(timeout em background; stdout ao vivo via Monitor). **Categoria**
(`RETROSPECTIVA-FASE-D`): garantia sem mecanismo · falso-verde (silêncio lido
como progresso).
