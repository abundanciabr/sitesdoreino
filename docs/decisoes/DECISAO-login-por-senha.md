# DECISÃO — login por e-mail e senha, para quem não tem conta do Google

> **Sessão de arquitetura com o mantenedor presente**, 31/08/2026 — o rito que
> `DECISAO-celula-de-identidade.md` e `RITOS.md` §3 exigem por escrito antes de
> o contrato congelado da `identidade` mudar. Contexto imediato: o PR #771,
> mergeado nesse mesmo dia, transformou `/cadastro` de captura de lead em
> pedido real de vaga (nome, e-mail, WhatsApp → fila "Aguardando aprovação").
> Isso expôs a lacuna: quem não tem conta do Google pode pedir vaga e ser
> aprovado, mas não tinha nenhum jeito de ENTRAR no site depois — a única
> porta era o Google.
>
> Perguntado como resolver o "esqueci minha senha" sem nenhum serviço de
> e-mail ou WhatsApp automático (nenhum existe na plataforma hoje), o
> mantenedor escolheu, entre as opções apresentadas: **login com senha,
> recuperação manual por WhatsApp** (não um serviço de e-mail automático
> novo). Perguntado se a senha nasce no próprio formulário de `/cadastro` ou
> só depois da aprovação, escolheu: **no próprio formulário**. Perguntado o
> que fazer se a escrita da senha falhar por problema técnico no meio do
> cadastro, escolheu: **o pedido inteiro falha e pede para tentar de novo**
> (não um sucesso parcial silencioso) — a página some, a pessoa refaz; isso é
> seguro porque `alunos.entrar_na_fila` (a fila de aprovação) já é idempotente
> por e-mail, então reenviar nunca duplica ninguém na fila.

**Status:** *isto é lei.*

## 1. O que foi decidido

1. **Login por senha é um SEGUNDO caminho, ao lado do Google — não substitui
   nada.** O caminho do Google continua exatamente como está.
2. **A senha nasce no formulário de `/cadastro`** (`services/funil`), junto
   com nome, e-mail e WhatsApp — não numa etapa separada pós-aprovação.
3. **Falha ao gravar a senha ⇒ o pedido inteiro falha (502, formulário
   preservado)** — mesmo padrão `erro_envio` que a página já usa para a fila
   de aprovação. Nenhum estado parcial ("na fila mas sem senha") é aceito.
4. **"Esqueci minha senha" é manual, por enquanto**: a pessoa fala com o
   mantenedor pelo WhatsApp que ela já deixou no cadastro; ele confirma quem
   ela é e aciona um reset pela área administrativa, que gera uma senha nova
   e a mostra em texto puro UMA vez, para ele repassar por fora. Nenhum
   e-mail nem WhatsApp automático nasce com esta lei — é dívida reconhecida,
   não esquecimento (ver §4).
5. **Uma pessoa recusada continua conseguindo "entrar" (ser reconhecida) por
   senha**, exatamente como qualquer conta Google recusada já consegue
   entrar hoje. É o invariante *reconhecer não é autorizar*
   (`DECISAO-celula-de-identidade.md` §1.3) aplicado sem exceção: a porta
   nunca confere matrícula, quem confere é a célula dona do recurso, na hora
   do recurso.

## 2. O que muda no contrato congelado (`contracts/identidade.openapi.yaml`)

Três operações novas, todas em `/interno/` (superfície de máquina — o POST
que o navegador de fato usa, `/entrar/senha`, NÃO entra no contrato, pela
mesma razão que `/entrar/google` não entra: é endereço de gente, roteado
pelo Traefik, não chamada entre células):

| operationId | rota | quem chama | por quê |
|---|---|---|---|
| `issueLoginToken` | `POST /interno/tokens-de-entrada` | qualquer par aceito | prova, no POST de `/entrar/senha`, de que o pedido veio do site — ver §3 |
| `setPassword` | `POST /interno/pessoas/definir-senha` | par com o grau novo `TOKENS_SENHA_*` | grava a senha escolhida no cadastro (upsert por e-mail, mesma forma de `cunhar_ou_recuperar`) |
| `resetPassword` | `POST /interno/pessoas/resetar-senha` | par com o grau novo `TOKENS_SENHA_*` | gera senha nova para o reset manual (§1.4) |

Mudança aditiva (`ci/contrato_aditivo.py` confere): nada do que já existe em
`Session`/`SessionFull`/`getSession`/`getSessionFull` muda — `funil`,
`sugestoes` e `admin` continuam lendo sessão exatamente como hoje, sem
tocar em nenhum PR desta lei.

## 3. Por que um token assinado, e não o padrão de `/entrar/sair`

`/entrar/sair` é `csrf_exempt` e se defende só por Origin/Referer
(`_mesma_origem`) — mas a própria `services/identidade/LICOES.md` já registra
por escrito, antes desta lei existir, que esse padrão é só para ações que
DESTROEM estado: *"se um dia esta célula ganhar um POST que CRIE estado, ele
usa CSRF de verdade, não este padrão."* Login por senha CRIA sessão. E como
quem RENDERIZA o formulário de senha é o `funil` (a tela de login mora lá,
por `DECISAO-celula-de-identidade.md` §2), não a `identidade`, um CSRF token
gerado pela `identidade` nunca chegaria ao HTML que o `funil` serve — e um
token do `funil` nunca validaria na `identidade` (segredos diferentes, dois
processos Django distintos). A saída: a `identidade` emite um token efêmero
assinado (`django.core.signing.TimestampSigner`, biblioteca padrão do
Django — nenhuma dependência nova) que o `funil` busca ao montar `/login` e
embute como campo oculto; a `identidade` confere a assinatura e a validade
(minutos) antes de tocar em qualquer senha. Mesmo princípio do `state` que
o fluxo do Google já usa contra CSRF, adaptado para atravessar a fronteira
entre as duas células.

## 4. Grau novo de autorização: `TOKENS_SENHA_*`

Gravar a senha de alguém é mais que "perguntar quem é alguém" — por isso
`setPassword`/`resetPassword` exigem um grau PRÓPRIO, `TOKENS_SENHA_*`,
maior que `TOKENS_ACEITOS_*` e independente de `TOKENS_COMPLETOS_*` (que é
sobre LER e-mail, não sobre ESCREVER senha; misturar os dois alargaria um
grau de leitura para virar também um de escrita, em silêncio). Concedido a
`funil` (chama `setPassword` no cadastro) e a `admin` (chama `resetPassword`
no reset manual). Reaproveita o MESMO segredo que já está em
`TOKENS_ACEITOS_FUNIL`/`TOKENS_ACEITOS_ADMIN` — não é preciso gerar valor
novo nem rodar script de provisionamento: é uma linha a mais em
`identidade.env` na VPS por par, apontando para o segredo que já existe.
Este parágrafo é o registro que `DECISAO-celula-de-identidade.md` §6.3 pede
para todo grau novo de acesso — o mesmo espírito, um grau além do que
aquele parágrafo previu (`TOKENS_COMPLETOS_*`).

## 5. Sequência de entrega

1. Este documento + `contracts/identidade.openapi.yaml` (PR só de
   `contracts/`, label `contrato` — nenhum código de célula junto).
2. `identidade`: campo `senha_hash`, as três operações, a view
   `entrar_senha`, limite de tentativas, hashing e validação de senha.
3. `funil`: campos de senha em `/cadastro`, mini-formulário em `/login`,
   traduções nos três idiomas.
4. `admin`: botão de reset manual no prontuário do aluno, com auditoria.
5. Passo do mantenedor na VPS (antes do PR 2 ir ao ar): duas linhas em
   `identidade.env` (`TOKENS_SENHA_FUNIL`, `TOKENS_SENHA_ADMIN`, mesmo valor
   dos pares `TOKENS_ACEITOS_*` já existentes) — bloco único de colar, sem
   segredo novo para gerar.

## 6. O que fica decidido para o próximo agente

1. **Não** distinga, na mensagem de recusa do login por senha, "e-mail não
   existe" de "senha errada" — a mesma chave serve para os dois, para não
   virar uma forma de descobrir quem tem conta.
2. **Não** grave a senha em texto puro em lugar nenhum, nem em log, nem em
   auditoria — só o hash. A senha nova do reset manual sai em texto puro
   APENAS na resposta HTTP daquele POST, uma vez, para o mantenedor copiar.
3. **Não** use e-mail nem WhatsApp automático para "esqueci minha senha" sem
   voltar a este documento — a ausência é decisão (§1.4), não esquecimento;
   se um dia nascer um serviço de envio automático nesta plataforma, a
   pergunta "isso muda o reset manual?" volta para o mantenedor.

## 7. Estado

**Decidido em 31/08/2026.** Passo do mantenedor: duas linhas em
`identidade.env` na VPS (§5, item 5), quando o PR 2 estiver pronto para subir.
