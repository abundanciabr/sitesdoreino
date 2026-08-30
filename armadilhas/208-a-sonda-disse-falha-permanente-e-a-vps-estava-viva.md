---
schema_version: 2
armadilha: 208
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  detector: test_sonda_da_vps
  dono: ci/tests/test_sonda_da_vps.py
sinal:
  - `n[ãa]o respondeu deste runner`
  - `PAROU POR SEGURAN[ÇC]A: a porta 22`
  - `falha PERMANENTE de alcance`
---

# A sonda disse "falha PERMANENTE" e a VPS estava viva — o falso-vermelho CATEGÓRICO

**Sintoma.** O `deploy-celula` para na 2ª tentativa com esta mensagem, e ela não
deixa dúvida nenhuma:

```
🧱 PAROU POR SEGURANÇA: a porta 22 da VPS não respondeu deste runner
   Isto NÃO é o soluço de rede da armadilhas/127 — é a armadilhas/017:
   falha PERMANENTE de alcance. Nenhuma tentativa nova vai passar.
   O conserto é de configuração e passa pelo mantenedor (Lei 5).
```

E a VPS está **viva**. Sondada do PC na mesma janela, a porta 22 devolve
`SSH-2.0-OpenSSH_9.6p1`; o site responde 200; `gh run rerun --failed` sobe em
1min02s. Era a [127](127-deploy-vermelho-com-i-o-timeout-e-a-vps-viva-nao-e.md),
o soluço intermitente — exatamente o caso que a vacina existe para salvar.

**Por que é grave, e não um detalhe de texto.** `permanente` é o único dos três
vereditos que faz o deploy **desistir**. Um falso `permanente` inverte a vacina:
em vez de salvar a entrega de um soluço, ela abandona uma entrega que subiria na
tentativa seguinte — e o merge fica na `main` sem chegar ao site, em silêncio. É
o irmão do falso-verde: **o falso-vermelho categórico**, pior de um jeito,
porque parece diagnóstico em vez de dúvida. Quem lê "nenhuma tentativa nova vai
passar" para de tentar, e está certo em parar: a mensagem não deixa espaço.

**Causa — duas confusões, uma em cima da outra.** O log do run 33312655853
(deploy da `admin`, PR #589, 30/08/2026) entrega as duas sem palpite:

1. **"Estourou o tempo" caía no mesmo `except` de "recusou a conexão".** Cada
   uma das três medições durou 25 s — 10 s de estouro na porta 22, 15 s de
   estouro no site — e **nenhuma conexão foi recusada**. O código de então fazia
   `except (socket.timeout, TimeoutError, ConnectionError): return False`, e
   `False` significava "porta morta". Mas as duas coisas são fatos diferentes: a
   recusa é uma RESPOSTA (o pacote chegou em algum lugar e voltou um "não"); o
   estouro é SILÊNCIO — e silêncio é a assinatura **literal** do soluço da 127
   (`dial tcp ***:22: i/o timeout`). A sonda reproduzia o próprio engasgo que
   existe para diagnosticar e então o declarava permanente. Circular.
2. **A testemunha estava do lado e era ignorada.** As três medições também não
   alcançaram `https://meshcraft.top/healthz`, que servia 200 para o mundo
   inteiro naquele minuto. Quem estava cego era o **runner**, não a porta. O
   `site_http` já era medido e só virava um recado no fim do texto; nunca entrava
   na decisão.

**E "duas medições concordando" não salvou** — o desenho da TAR-013 já exigia
duas medições para pular a 3ª tentativa, e as duas concordaram. Elas eram uma
sondagem cada, e as duas estouraram o tempo pelo mesmo motivo. **Repetir a mesma
medição cega não é corroboração.**

**Solução (TAR-026), em três peças:**

- **Silêncio deixou de ser resposta.** `sondar_uma_vez` devolve seis sinais em
  vez de um booleano: `ATENDEU` · `NAO_E_SSH` · `RECUSOU` · `NOME_NAO_RESOLVE` ·
  `SEM_RESPOSTA` · `NAO_PERGUNTEI`. Os três do meio são respostas negativas da
  rede; `SEM_RESPOSTA` é silêncio.
- **`permanente` exige no mínimo DUAS sondagens concordando, dentro do próprio
  módulo** (`MEDICOES_MINIMAS_PARA_PERMANENTE`). Cada chamada sonda até três
  vezes e para cedo quando a porta atende — o caminho feliz custa
  milissegundos. A régua passou a morar onde a decisão é tomada, e não só no
  YAML.
- **Silêncio só vira `permanente` com a testemunha do site.** Se o runner
  alcança a internet pública e não alcança a porta 22, a saída dele funciona e o
  buraco é a porta — a forma exata da
  [017](017-cloudflare-na-frente-do-dominio-deploy-morre-em.md), que **continua
  acontecendo**. Sem a testemunha, o veredito é `nao_medi` e o retry segue
  inteiro.

**A regra que fica, e ela é maior que esta sonda: quando o instrumento e o
suspeito estão do mesmo lado do cabo, a medição não é sobre o suspeito.** A
sonda mede DO runner; um estouro de tempo lá prova "não alcanço a VPS daqui,
agora", nunca "a VPS está inalcançável". Antes de transformar a segunda frase na
primeira, é preciso uma testemunha independente que prove que o instrumento
enxerga.

**E o fail-closed aqui aponta para o outro lado.** Repetir à toa custa 45
segundos; desistir à toa custa uma entrega que não chega ao site, sem ninguém
perceber. Por isso a dúvida vira `nao_medi` — continuar tentando **é** fechar a
porta segura. Vale conferir a direção do fail-closed sempre que um portão
aprender a desistir: o custo dos dois erros raramente é simétrico.

**A mensagem que manda desistir agora mostra a conta.** Ela diz em quantas
sondagens se baseia e o que cada uma viu ("3 sondagens seguidas … estourou o
tempo em 3"), no texto do passo e no `$GITHUB_OUTPUT`, e o passo de parada do
`deploy-celula.yml` repete o número no log. Mensagem categórica é acreditada;
mensagem com a conta à vista é **falsificável** — quem lê pode discordar.

**Origem.** 30/08/2026, TAR-026 — medido por um robô irmão (o da TAR-023) que não
tinha nada a ver com a sonda, durante o deploy do PR #589, com a porta 22
conferida do PC na mesma janela. A sonda tinha nascido nesse mesmo dia
(TAR-013, PR #584).
