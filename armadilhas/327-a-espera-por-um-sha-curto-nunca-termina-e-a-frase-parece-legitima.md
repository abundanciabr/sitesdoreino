---
schema_version: 2
armadilha: 327
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: são três guardas porque são três coisas distintas, e cada uma cai sozinha na mutação de uma linha - recusar o que não dá para resolver, resolver o que dá, e DIZER qual sha acabou medindo; um só permitiria trocar a cura por uma que recusa tudo, ou por uma que resolve em silêncio
sinal:
  - "nenhum run de deploy apareceu ainda"
---

# A espera por um sha curto nunca termina, e a frase que ela repete parece legítima

**Sintoma.** `python ci/esperar.py --deploy 40f6f8ae --teto 20` fala a cada
volta, com toda a educação do mundo:

```
⏳ 1min02s de 20min · nenhum run de deploy apareceu ainda para 40f6f8ae
```

E vai repetir isso por vinte minutos. O deploy, enquanto isso, **já terminou
verde**: `gh run list` mostra o run `completed success` para aquele mesmo
commit, desde antes de a espera começar.

**Causa.** O `head_sha=` da API do GitHub casa por **igualdade**, nunca por
prefixo. Um sha de oito caracteres devolve zero runs, e `observar_deploy` faz a
única coisa honesta que pode fazer com uma lista vazia: dizer que ainda não
apareceu nada. A frase está certa sobre o que ela mediu; o que estava errado era
a pergunta.

**E é aí que dói:** "ainda não apareceu" é exatamente o que uma espera legítima
diz nos primeiros minutos de um deploy de verdade. Não há como distinguir de
dentro. É a lição 2 do Lote A no `RUNBOOK-LOTES.md` §9 acontecendo com a própria
ferramenta de esperar: *espera que mede a coisa errada é indistinguível de espera
legítima, e só quem está de fora percebe*. Medido em 04/09/2026, com a
sessão-maestro esperando o veredito do último deploy do dia — que estava verde
desde o começo da espera.

**Solução.** `--deploy` resolve o valor antes de começar:

- 40 caracteres hexadecimais passam direto, sem tocar no git (o caso normal não
  pode depender de um repositório);
- qualquer outra coisa vai para `git rev-parse --verify <valor>^{commit}`, que é
  a fonte certa e está a um comando de distância;
- o que o repositório não conhece é **RECUSADO na porta**, com a mensagem
  dizendo por que (a API casa por igualdade) e qual é o caminho
  (`git rev-parse`);
- e a resolução **fala**: `(resolvi 40f6f8ae para o sha inteiro 40f6f8ae3a16…)`.
  Resolver em silêncio esconderia do robô qual sha ele acabou medindo, que é a
  mesma doença numa roupa mais discreta.

Recusar tudo o que é curto seria cura pior que a doença: um sha curto é o que se
tem na mão o tempo todo, e a ferramenta existe para servir quem a usa.

**Prova.** Três guardas em `ci/tests/test_espera.py`. Vermelho contra a versão
anterior: 2 de 3 falham; o terceiro (o sha inteiro passa direto) é verde dos dois
lados **de propósito**, porque é anti-afrouxamento. Três mutações deliberadas,
uma linha por vez:

| mutação | quem cai |
|---|---|
| o `--deploy` volta a não resolver nada | o guarda da recusa e o da resolução |
| `resolver_sha_inteiro` devolve o valor sem conferir | os mesmos dois |
| a resolução fica muda | só o guarda da resolução |

**A régua que fica, e vale para qualquer espera:** antes de começar a esperar,
pergunte se a condição que você vai medir *pode* ser satisfeita. Uma espera com
teto protege do infinito; ela não protege de perguntar a coisa errada durante
vinte minutos.
