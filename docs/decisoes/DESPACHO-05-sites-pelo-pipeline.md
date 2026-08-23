# DESPACHO 05 — Sites pelo pipeline (R11 mecanizada)

**Data:** 23/08/2026 · **Mandato:** pedido direto do mantenedor, em sessão, ao
configurar o meshcraft.top: *"sem esse negócio de código que só atrasa tudo —
você vai me ajudar a dar esse poder a você"*. O poder pedido era o de o agente
executar sozinho a parte de servidor de um domínio novo.

## A decisão

**O poder foi dado ao PIPELINE, não à máquina do agente.** A proposta literal
(dar SSH ao agente) foi recusada pela mesma razão de sempre da Lei 5: segredo
de longa duração morando na máquina de trabalho, canal sem trilha de auditoria,
e — pior para o próprio objetivo do mantenedor — MAIS passos manuais dele para
configurar chave e acesso. O caminho que entrega o mesmo resultado sem nada
disso já existia: o `deploy-infra` entra na VPS com a chave dele a cada merge.
Faltava só ensiná-lo a cadastrar sites.

Nada disso depende de o agente ser "mais inteligente" que os anteriores: a Lei 5
não é um julgamento do agente, é arquitetura — todo poder novo entra pelo canal
auditável, revisado e reversível, seja quem for que o use.

## A mecânica (o que passou a existir)

- **`infra/sites.json`** — registro declarativo dos sites (a R11 como DADO).
  Domínio novo = uma entrada aqui, por PR normal de infra.
- **`infra/sincronizar_sites.py`** — código que converge o catálogo da produção
  ao arquivo, rodando DENTRO do container do catalogo via
  `manage.py shell -c "$(cat ...)"` (exceção ⇒ exit ≠ 0, fail-closed).
  Idempotente; transação única; nunca toca site que não está no arquivo; nunca
  edita preço de oferta existente (aviso no log; nova versão é decisão humana).
- **`deploy-infra` passo 5** — depois da verificação dos serviços: roda o sync
  e prova cada host do arquivo com smoke `Host: <h>` ⇒ 200 na raiz, insistindo
  ~80s para atravessar o cache de 60s do CONV-SITE (ARMADILHAS §4.13).

## O que segue manual (e por quê)

- **DNS/Cloudflare e nameservers no registrador**: exigem login nas contas do
  mantenedor. Opções: cliques guiados pelo painel, ou o agente pilotando o
  navegador do mantenedor logado (Claude in Chrome).
- **Segredos de runtime (`env/`)**: intocados, como sempre (INV-P8).

## Primeiro uso

O merge deste despacho dispara o `deploy-infra`, que cadastra o
**meshcraft.top** (site de testes, oferta `curso-teste`, 990 cents) — o
veredito do run e o smoke são a prova de que a mecânica funciona.
