# painel/ia — 07. Oportunidades e Fronteiras

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Diferente dos outros
> documentos deste mapa, este NÃO é um resumo de uma fonte única — é uma
> **síntese** montada a partir da pesquisa que gerou todo o mapa (27/08/2026),
> apontando onde procurar. Trate cada item como uma **pista verificada na
> data acima**, não como veredito fechado: confirme contra o código e contra
> `painel/registros/` antes de agir, e nunca contra a data deste documento.

## Como usar este documento

Se você é uma IA procurando onde uma sugestão de melhoria realmente ajudaria
este projeto: comece por aqui, mas não pare aqui. As três seções abaixo
respondem three perguntas diferentes — "onde NÃO mexer", "o que já está
sabidamente incompleto (e por quê)", e "o que esta própria pesquisa
encontrou de concreto". A última é a mais imediatamente acionável: são
achados pequenos, verificados, com caminho de arquivo exato.

## 1. Onde não mexer sem pedido explícito

A lista completa, com o porquê de cada uma, está em
[06 — produto, decisões e roadmap](06-produto-decisoes-e-roadmap.md#decisões-que-uma-ia-nova-pode-ficar-tentada-a-reabrir-mas-não-deve).
A mais importante, porque é a mais fácil de violar por engano: **nunca
proponha ou retome trabalho em pagamentos/checkout/Mercado Pago** por
iniciativa própria — só se o pedido do usuário for explicitamente sobre
isso. Não é avaliação técnica de prioridade; é diretiva direta do
mantenedor, registrada desde 22/08/2026.

## 2. Lacunas já conhecidas e rastreadas (fotografia por documento, confira o estado real)

Estas não são descobertas desta pesquisa — são gaps que o próprio projeto já
documentou. Valem como ponto de partida, mas cada um pode já ter sido
fechado desde que o documento-fonte foi escrito; **confira `painel/registros/`
antes de propor trabalho em qualquer um**.

| Lacuna | Onde está documentada | Por que ainda não fechou (se declarado) |
|---|---|---|
| Red Team (`02-RED-TEAM.md`) nunca fechou 15/15 golpes — só 5-6 têm evidência marcada | [01](01-leis-ritos-e-invariantes.md) | Sem motivo declarado — parece só não ter sido retomado |
| Esqueleto Que Anda: critério 2 (VPS processando cartão real) bloqueado | `RUNBOOK-FASE-D.md` §5 | Falta Card Payment Brick + confirmação síncrona não emite evento + webhook real exige passo manual do mantenedor no painel do MP — **e está sob a diretiva de pagamento por último** |
| `e2e/esqueleto.sh` não roda dentro do CI automatizado, apesar da doutrina original prometer isso | `RUNBOOK-FASE-D.md`, confirmado por leitura direta dos workflows | Gap de implementação conhecido, não decisão deliberada |
| i18n Fase 5 (levar tradução além do `funil`) congelada | `docs/i18n/PLANO-I18N.md` | Falta de **alvo legítimo**, não decisão técnica contra — guardas de teste já escritos e vermelhos de propósito, esperando |
| Notificações: 2ª metade da Fase 3 (migrar avisos antigos da Caixa para a célula nova) e Fases 4-7 (sino em toda página, preferências, outros canais) | `docs/notificacoes/PLANO-MESTRE.md` | Trabalho enfileirado, não bloqueio |
| `RUNBOOK-FASE-D.md` §7: checkout descarta parâmetros UTM; i18n do quiz ainda é local (não usa o catálogo YAML) | `RUNBOOK-FASE-D.md` §7 | Tabela de pendências herdadas, sem motivo individual declarado |
| PLANO-10X item 4 ("detecção de falha"): mensagens presas na fila do Redis sem recuperação, relays de evento sem cobertura de queda, nenhuma reconciliação "quem pagou e não recebeu" | `docs/decisoes/PLANO-10X.md` | Identificado como alavanca, não confirmado se já endereçado — **candidato real a auditoria técnica de uma IA**, fora da zona de pagamentos-por-último (é sobre robustez do transporte de eventos, não sobre nova feature de cobrança) |
| Nenhum ChangeSpec real foi escrito ainda (o mecanismo está pronto e testado) | `docs/caixa-de-sugestoes/` | Considerado correto, não falha — não é um "conserte isto" |

## 3. Achados concretos desta pesquisa (candidatos diretos a PR pequeno)

Estes foram encontrados ao vivo, lendo o código e a configuração reais, não
copiados de um documento antigo — cada um é um bom primeiro alvo se você
quiser um PR pequeno, verificável, de baixo risco:

1. **Inconsistência de domínio em documentação.** `RUNBOOK-FASE-D.md` §5.3
   referencia `basileiatoutheou.org` como se fosse a URL real de registro do
   webhook do Mercado Pago; todo o resto do runbook (e a produção real) usa
   `meshcraft.top`. Provável resíduo de template não atualizado. Ver
   [01](01-leis-ritos-e-invariantes.md).
2. **`ci/manifesto-de-contratos.json` tem `reason` desatualizada** para
   `funil` e `quiz` — diz "célula ainda em esqueleto, só expõe `/healthz`",
   mas ambas já têm páginas reais em produção. A conclusão (sem contrato
   OpenAPI, por não expor API JSON) continua correta — só o texto do motivo
   está errado. Ver [04](04-arquitetura-de-celulas-e-contratos.md).
3. **`sugestao.mesclada.v1` é prometido em `constituicoes/AGENTS.sugestoes.md`**
   mas não existe em `contracts/eventos/` — confirme se é feature não
   implementada ou constituição adiantada demais antes de assumir qualquer
   um dos dois. Ver [04](04-arquitetura-de-celulas-e-contratos.md).
4. **`checkout` expõe um Bearer token estático no HTML da página**
   (visível em "ver código-fonte"). A própria `services/checkout/LICOES.md`
   já registra isso como pendência de arquitetura em aberto, sugerindo um
   token de curto prazo por sessão como alternativa — mas ninguém puxou o
   fio ainda. Ver [04](04-arquitetura-de-celulas-e-contratos.md).
5. **`quiz` resolve "Site" numa tabela própria local**, em vez de chamar a
   API do `catalogo` como a Receita genérica do Caminho Dourado prescreve
   para páginas públicas — desvio deliberado, mas a própria `LICOES.md` da
   célula pede revisão humana, porque o `site_id` local não tem checagem
   automática de sincronia com o do catálogo. Ver
   [04](04-arquitetura-de-celulas-e-contratos.md).
6. **`ARMADILHAS-OPERACAO.md` §9 lista dívidas conhecidas e ainda abertas**:
   referências obsoletas ao antigo `ARMADILHAS.md §1/§9` espalhadas em ~12
   lugares dentro de `services/` (ponteiros que não resolvem mais desde a
   reforma de 23/08/2026), 3 buracos de cobertura de teste especificamente
   na célula `pagamentos`, e 37 "guardas não declarados" (testes que
   protegem algo sem ter um `INV-*` numerado correspondente em
   `INVARIANTES.md` — rastreados, não escondidos, em
   `ci/guardas-nao-declarados.txt`). Ver
   [02](02-armadilhas-e-padroes-recorrentes.md).

## 4. Antes de propor qualquer mudança: o método que este próprio projeto exige

Isto não é conselho genérico — é a lei operacional documentada em
`docs/decisoes/RETROSPECTIVA-FASE-D.md` (resumida em
[02](02-armadilhas-e-padroes-recorrentes.md)), e ignorá-la já custou caro
mais de uma vez neste projeto especificamente:

- **Não afirme viabilidade sem ler a configuração real** — roteamento do
  Traefik, permissões de banco, workflow de deploy, não só o código de
  aplicação. Uma sugestão de arquitetura sem isso já enganou uma decisão
  real do mantenedor antes.
- **Verifique, não convirja.** Este projeto já teve 5+ rodadas de
  consultoria com múltiplas IAs externas (Gemini, GPT, Opus, Sonnet, Fable —
  arquivadas em `docs/*/recomendação-*.txt` e `Recomendacao-*.txt`) e a
  lição registrada, por escrito, depois de comparar os pareceres com o
  código real, foi: "convergência entre LLMs mede convencionalidade, não
  correção". Um parecer chegou a citar sintaxe do Traefik v2 que não existe
  mais na v3.4 usada aqui. Rode o comando, leia o arquivo, não confie só no
  consenso entre modelos — inclusive o seu.
- **Distinga "isto é uma lacuna" de "isto foi decidido assim".** A seção 1
  deste documento e a lista completa em
  [06](06-produto-decisoes-e-roadmap.md) existem exatamente para isso —
  consulte antes de propor.
- **Prova vem de fora, fail-closed nas bordas, ERROR≠FAIL, contexto é
  orçamento.** Os outros 4 padrões da retrospectiva, todos em
  [02](02-armadilhas-e-padroes-recorrentes.md) — qualquer sugestão de
  mudança em CI/portões/deploy deve ser lida contra eles primeiro.
