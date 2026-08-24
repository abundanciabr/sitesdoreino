# `deploy-infra` vermelho com a plataforma 100% saudável: a sonda envelheceu

**Sintoma:** o run do `deploy-infra` termina em `failure` com
`ERRO: a raiz de meshcraft.top respondeu 302 (esperava 200) — cadastro convergiu mas
o site não serve.` — mas o próprio log ACIMA da linha do erro mostra os 16 serviços
`Up ... (healthy)`, o traefik recriado, `OK: infra sincronizada` e
`SINCRONIZAÇÃO DE SITES: concluída`. Medido de fora, pela internet pública, no mesmo
minuto: `meshcraft.top/` → 302 para `/en/`, `/en/` → 200, `/pt-br/cadastro` → 200.
Nada está quebrado. (Run 32682355021, 23/08/2026.)

**Causa:** a sonda pós-deploy foi escrita quando todo site servia conteúdo na raiz, e
exigia literalmente `200` em `https://localhost/` com cabeçalho `Host:` — **sem seguir
redirecionamento**. Desde a fase 2 do `PLANO-I18N` (PR #88) a raiz de um site
multilíngue responde **302 para `/<idioma>/` de propósito**. A sonda não mediu nada
errado: ela mediu uma regra que deixou de valer. O detalhe que faz isso custar caro é
o atraso — o i18n entrou por `deploy-celula`, e o `deploy-infra` só rodou horas
depois, no primeiro merge que tocou `infra/` ou `.github/workflows/`. Quem levou o
vermelho foi um **PR de documentação que só trocou comentários**, e o instinto natural
("meu merge quebrou a produção") aponta para o lugar errado.

**Solução:** seguir o redirecionamento, sem deixar a VPS:

```bash
curl -sk -L --max-redirs 3 \
  --resolve "$H:443:127.0.0.1" --resolve "$H:80:127.0.0.1" \
  -o /dev/null -w '%{http_code}' "https://$H/"
```

`-L` mantém a exigência REAL ("o site serve") em vez de exigir uma forma de servir;
`--resolve` nas DUAS portas prende o host em `127.0.0.1`, então a prova continua
acontecendo dentro da VPS mesmo se o redirecionamento apontar para `http://` — sem
isso, `-L` sairia para a internet e a sonda viraria um teste de DNS.
`--max-redirs 3` impede laço.

**Vermelho→verde, reproduzível do seu PC** (troque `127.0.0.1` pelo IP da VPS — é a
mesma medida, vista de fora): a forma antiga devolve `302` e reprova; a nova devolve
`200`; e um host que não existe (`naoexiste.meshcraft.top`) devolve `404` na forma
nova — a guarda continua mordendo, não passou a aprovar tudo.

**A lição que generaliza:** sonda que afirma um CÓDIGO HTTP exato ("tem que ser 200")
está acoplada à forma de servir, não ao fato de servir. Toda vez que a plataforma
ganhar uma forma nova e legítima de responder (idioma na URL, domínio canônico,
manutenção programada), ela vira falso vermelho — e falso vermelho repetido ensina
todo mundo a ignorar vermelho, que é o oposto do que um portão existe para fazer.

**Origem:** merge do PR #100 (particionamento do ARMADILHAS), 23/08/2026 — o primeiro
`deploy-infra` depois do i18n entrar em produção.
