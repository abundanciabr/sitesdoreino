# Célula nova com o compose no MESMO PR trava os dois deploys, e nenhum rerun sai

**Sintoma:** o PR de gênese de uma célula (código + `infra/docker-compose.yml`
juntos) é mergeado com tudo verde, e os DOIS deploys ficam vermelhos:

```
deploy-celula → ERRO: 'notificacoes' não tem serviço algum em
                /opt/plataforma/docker-compose.yml.
                Abortado de propósito: 'up -d' sem argumento subiria a
                plataforma inteira.

deploy-infra  → vermelhos-nao-previstos  FAIL
                - .github/workflows/deploy-celula.yml => failure
```

**Causa — e os dois portões estão CERTOS, que é o que torna isto confuso:**

1. o merge dispara `deploy-celula` e `deploy-infra` **no mesmo commit**;
2. o `deploy-celula` corre primeiro e procura os serviços da célula no compose
   **que está na VPS** — ainda o antigo, sem a célula. Ele aborta em vez de rodar
   `up -d` sem argumento, o que subiria a plataforma inteira. Trava boa;
3. o portão do `deploy-infra` então vê um workflow vermelho no mesmo SHA e
   recusa entregar o compose novo — que era exatamente o que destravaria o
   passo 2. Trava boa também.

**Nenhum rerun sai disso: o vermelho e a cura estão no mesmo commit.** Rerodar o
`deploy-celula` falha igual (o compose na VPS não mudou); rerodar o
`deploy-infra` falha igual (o vermelho do outro continua lá).

**Solução — um PR que toca SÓ o compose.** Ele nasce num SHA onde o
`deploy-celula` nem roda (os paths dele não incluem `infra/`), então o
`deploy-infra` fica verde sozinho e entrega o arquivo. Depois disso,
`gh run rerun <id-do-deploy-celula> --failed` sobe a célula — agora com onde
subir. Foi a sequência que funcionou em 26/08/2026:

```bash
# 1. PR só com infra/docker-compose.yml  → merge → deploy-infra verde
# 2. gh run rerun <id do deploy-celula> --failed  → verde
```

O diff desse PR pode ser **só comentário**: o que importa é que o compose já
esteja na `main` e que o push toque aquele arquivo.

**A REGRA, para não passar por isto de novo: o compose de uma célula nova entra
em PR PRÓPRIO, sozinho, separado do PR da gênese.** Era o que o precedente já
fazia sem estar escrito — a `identidade` (#153) e o `admin` tiveram o compose em
PR separado —, e convenção lembrada não sobrevive ao próximo despacho. Agora está
comentada no `infra/docker-compose.yml`, no bloco da célula.

**O que NÃO fazer, e a tentação é real:** declarar o `deploy-celula` na lista de
"vermelhos previstos" do `ci/portao_de_deploy.py` para o `deploy-infra` passar.
Isso cega o portão para um deploy de célula quebrado **para sempre**, e por um
problema de ordem que dura minutos. É trocar uma espera por um buraco permanente.

**Categoria** (`RETROSPECTIVA-FASE-D`): não é falso-verde — é o oposto, dois
fail-closed corretos se encontrando. O que faltava era a ORDEM estar escrita.

**Origem:** gênese da célula `notificacoes`, 26/08/2026 — PRs #248 (a célula) e
#252 (o compose sozinho, que destravou).
