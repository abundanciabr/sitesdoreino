---
schema_version: 2
armadilha: 375
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portao compara o texto da documentacao com os nameservers reais do dominio, e nao ha como um portao saber que a doc envelheceu. O que existe e a medicao de dois segundos (`nslookup -type=NS <dominio>`) antes de mandar alguem abrir um painel de DNS
gatilho: infra/provisionar-email.sh, infra/traefik/, DNS de meshcraft.top
licao: O DNS do meshcraft.top esta na HOSTINGER (pixel/byte.dns-parking.com). A doc que diz Cloudflare fala do dominio ANTIGO, basileiatoutheou.org. Meca os nameservers antes de mandar alguem procurar.
---

# 3.375 A doc manda procurar o DNS no Cloudflare, e o dominio mudou de casa

**Sintoma.** O mantenedor foi ligar o e-mail em 06/09/2026. A doc do projeto, e
o agente repetindo a doc, mandaram ele abrir o Cloudflare para colar os
registros de DNS. Ele abriu, e o dominio nao estava la. Perdeu tempo achando
que tinha errado alguma coisa.

**Causa.** O projeto TROCOU de dominio e ninguem atualizou o texto. Medido:

```
$ nslookup -type=NS meshcraft.top 8.8.8.8
meshcraft.top   nameserver = pixel.dns-parking.com   <- Hostinger
meshcraft.top   nameserver = byte.dns-parking.com

$ nslookup -type=NS basileiatoutheou.org 8.8.8.8
basileiatoutheou.org   nameserver = itzel.ns.cloudflare.com   <- Cloudflare
basileiatoutheou.org   nameserver = odin.ns.cloudflare.com
```

A doc nao estava errada quando foi escrita: `basileiatoutheou.org`, o dominio
original, ESTA no Cloudflare ate hoje (e a `armadilhas/017` nasceu disso). O
`meshcraft.top` nasceu depois, na Hostinger, e herdou o texto do antecessor.

O mesmo env guardava `SMTP_FROM=contato@basileiatoutheou.org`, do dominio
velho. Se o e-mail tivesse sido ligado sem substituir esse valor, toda carta
sairia de um dominio NAO autenticado no Brevo, e o Gmail a recusaria ou
mandaria para o spam. O `infra/provisionar-email.sh` sobrescreveu por
`escola@meshcraft.top`, que e o que os testes da mensageria ja esperavam.

**Solucao.** Antes de mandar alguem (humano ou robo) abrir o painel de DNS,
rode `nslookup -type=NS <dominio>` e leia a resposta. Nameserver e a unica
fonte que nao mente sobre onde o DNS mora: nem a doc, nem a memoria, nem o
nome do provedor que aparece na fatura do dominio.

Quando um projeto troca de dominio, o texto que cita o provedor de DNS vira
divida silenciosa: ele so falha no dia em que alguem precisa dele, que e
sempre um dia de pressa.

**Onde doeu:** `infra/provisionar-email.sh` linhas 49 e 297 (a 297 e um `echo`,
impresso NA TELA DA VPS bem na hora da conferencia). Consertado no PR #1244.
