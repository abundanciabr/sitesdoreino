---
schema_version: 2
armadilha: 366
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: teste
  detector: ci/tests/test_espera.py::test_um_obrigatorio_por_nascer_nunca_e_verde_e_nunca_pede_pouso
  motivo: a espera deixou de fazer a pergunta menor. Quem responde "o universo de checks está completo?" é `obrigatorios_faltando()`, uma peça só, em `ci/mergear.py`, chamada pelo portão E pela espera, e as cenas verdes do teste são montadas a partir de `CHECKS_OBRIGATORIOS` — um obrigatório novo aparece nelas no dia em que for acrescentado lá, não no dia em que um PR pedir pouso sem ele
sinal:
  - `todos os 1 checks verdes`
  - `ERROR checks obrigat[óo]rios`
---

# A espera declara VERDE com um check só nascido, e o pouso é recusado em seguida

**Sintoma.** Você abre o PR, arma a espera com pouso automático, e ela devolve
o verde em segundos, quando o normal são minutos:

```
⏳ 0s de 20min · 0 de 1 checks prontos
✅ todos os 1 checks verdes · levou 16s.
🛬 checks verdes: passo pelo portão e peço pouso do PR 1189…
```

Logo depois o portão recusa o pouso que ela mesma acabou de pedir:

```
--- ERROR checks obrigatórios -----------------------------------------
Estes checks precisam existir em todo PR. A ausência deles pode
significar workflow renomeado, desabilitado, ou que nem disparou —
e nenhuma dessas coisas é aprovação.
MERGE RECUSADO.
```

**Causa.** Os dois medem o mesmo PR e respondem perguntas diferentes. A espera
pergunta *"algum check está pendente?"* e, quando o GitHub ainda criou só um
deles, a resposta honesta é "nenhum" — ela declara verde sobre um universo de
um. O portão pergunta *"os checks obrigatórios estão todos aqui e verdes?"*, e
essa é a pergunta completa.

A janela é real e curta: entre o `gh pr create` e o nascimento dos sete checks
passam alguns segundos, e é exatamente aí que uma sessão eficiente arma a
espera. Em 06/09/2026 aconteceu no PR #1189, e custou um pedido de pouso
perdido mais uma rodada de espera. **Nada entrou indevidamente na `main`** — o
portão recusou, que é o desenho funcionando: a espera é conveniência, o portão
é autoridade.

O caso vizinho JÁ era tratado: a espera reconhece **zero** checks e aponta a
`armadilhas/150` (conflito com a main). O buraco é o "poucos", não o "nenhum".

**Solução.** Feita em 07/09/2026 (TAR-226): a pergunta virou uma peça só.
`obrigatorios_faltando(rollup)` mora em `ci/mergear.py`, ao lado da lista que
ela lê, e é chamada pelos DOIS — o portão, para recusar o merge, e a espera,
para continuar esperando. Enquanto um obrigatório não nasce, a espera trata o
alvo como AINDA NÃO APARECIDO: é a graça (5 min) que decide quando isso deixa de
ser fila e vira workflow renomeado, desabilitado ou conflito com a main
(`armadilhas/150`), e o desfecho diz QUAL check faltou. O comando do rito não
mudou, e agora ele basta:

```bash
python ci/esperar.py --checks <N> --teto 20 --dizendo "os checks do PR <N>" --e-pousar
```

**O que se fazia antes da cura, e não é mais preciso:** desconfiar do verde que
chegava em menos de meio minuto, contar os checks nascidos com `gh pr checks <N>`
e armar a espera outra vez.

**A classe, que continua valendo.** Dois julgamentos separados do mesmo fato
divergem no primeiro dia em que alguém mexe num só. É o falso-verde por universo
incompleto, a mesma classe que já mordeu esta casa no H13 (os greens históricos
do `deploy-celula`) e na regra de nunca ler veredito de run pelo exit de um pipe.
A cura, sempre, é a pergunta morar em um lugar só.
