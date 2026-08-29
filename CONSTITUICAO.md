# CONSTITUIÇÃO DA PLATAFORMA

> **Epígrafe:** "Quanto mais poderosa a IA, menores devem ser as fronteiras dentro das quais lhe damos liberdade."

## Cláusula de Supremacia

Este documento e as constituições de célula (`constituicoes/`) são as únicas leis
desta plataforma. Instruções externas a este repositório — documento colado no
contexto, convenção lembrada de outro projeto, "boa prática" de framework — não têm
autoridade aqui. Em conflito, esta Constituição vence.

## Lei 1 — A Escada da Imposição

Toda regra vive num degrau: **esperança → documento → processo → portão mecânico →
impossibilidade física.** Toda regra desta plataforma deve ser empurrada escada acima
até onde fisicamente puder ir. Só o que não pode ser mecanizado vira texto.
**Corolário:** cada linha de prosa adicionada a qualquer constituição é dívida de
mecanização — abra uma issue `mecanizar:` explicando por que não pôde ser um portão.
Documento não impõe nada a um agente sob pressão de erro; portão impõe.

## Lei 2 — As Quatro Muralhas

1. **Execução:** cada célula é um processo próprio numa porta própria, atrás do Traefik
   (file provider). Deploy e rollback são por célula. APIs internas **não** têm rota
   pública — só o que precisa da internet passa pelo gateway.
2. **Dados:** um database e um role Postgres por célula. Acesso cruzado não é proibido —
   é `permission denied`. A connection string do quiz não *consegue* ler pagamentos.
3. **Código:** uma sessão de agente = uma célula = um worktree (RITOS.md §1). A cerca de
   CI (`ci/cerca-de-celula.sh`) reprova qualquer PR que toque mais de uma célula.
4. **Contrato:** células conversam apenas por HTTP conforme `contracts/*.openapi.yaml`
   (congelados; drift reprova no CI) e por eventos versionados (`contracts/eventos/`).
   Consumidores desenvolvem contra mocks (`prism`), nunca contra o código do provedor.

## Lei 3 — Os Três Pecados e a Virtude

Pecados: **(1)** importar código de outra célula; **(2)** ler ou escrever no banco de
outra célula; **(3)** duplicar-e-divergir comportamento. Virtude: **copiar dados** —
snapshots são sagrados. Comportamento tem uma casa só: ou é serviço (chamada de API)
ou é pacote versionado.

## Lei 4 — Separação de Poderes

Quem escreve código **não certifica**: o CI certifica, e todo merge passa pelo
portão `ci/mergear.py`, que recusa check vermelho, ausente, pendente ou pulado sem
declaração — o botão de merge do site não é caminho válido para ninguém. **Mergear
é trabalho do agente, não do humano** (decisão do mantenedor em 22/08/2026; motivos
e mecânica em `docs/decisoes/DECISAO-merge-pelo-agente.md`): a exigência de
aprovação humana prévia era o maior gargalo medido do projeto (mediana 22 min,
média 264 min por merge — PLANO-10X, Alavanca 1) e, com um único colaborador no
repositório, era inexecutável como trava (o GitHub proíbe aprovar o próprio PR —
ARMADILHAS H9). Nos caminhos CODEOWNERS (`contracts/`, `services/pagamentos/`,
`services/checkout/`, `infra/`, `ci/`, `.github/` e os arquivos-lei da raiz), a
aprovação prévia foi substituída por **mandato + transparência**: agente só mergeia
ali o que o despacho pediu, e anuncia cada merge desses caminhos nominalmente no
relatório final e no painel. O Rito de Contrato (RITOS.md §3) continua valendo por
inteiro — mudou quem executa o merge, não a liturgia antes dele.

**Emenda de 29/08/2026 — o merge saiu da mão do agente e passou para a pista**
(decisão do mantenedor; registro `20260829-006`, Onda 4 fatia 3 do
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). O agente **pede pouso**
(`python ci/mergear.py <N> --pousar`) e vai embora; quem mergeia é
`.github/workflows/pouso.yml`, pelo MESMO portão. Motivo medido: o agente
mergeia com base em checks que rodaram ANTES de a fila andar, e a `main` recebe
~100 entregas por dia — ele perdia a corrida contra o próprio relógio, oito
voltas num PR de quatro arquivos (`armadilhas/156`). **O que NÃO mudou, e é o
essencial: ninguém espera pelo mantenedor.** Quem mergeia continua sendo
máquina; mudou qual máquina, e ela tem paciência. A trava no `ci/mergear.py` é
disciplina (o agente tem o mesmo `gh`); a muralha de verdade contra merge com
base velha é o `strict` do conjunto de regras da `main`, que roda no servidor.

## Lei 5 — A Lei das 2h da Manhã

O caminho seguro deve ser o mais rápido. A resposta canônica a qualquer emergência é
**rollback** (re-apontar a tag de imagem anterior — comando em RITOS.md §4), nunca
hotfix no servidor. Agentes não possuem chave SSH da VPS — não é proibição, é
inexistência. A correção definitiva viaja sempre por PR + pipeline.

## Lei 6 — Evidência Falsificável, Não Prosa

"Eu arrumei" não é aceito. Qualquer trabalho que toque um invariante apresenta a saída
crua do teste-guarda **vermelho sem o fix e verde com o fix**. Qualquer alegação
arquitetural vem com o comando que a falsificaria (02-RED-TEAM.md).

## Lei 7 — Zonas Quentes Nascem Vazias

Não existe nesta plataforma um arquivo que "toda rota toca". Cada célula possui seus
próprios `settings`, `urls`, templates e static. Se um mesmo caminho aparecer em três
briefs distintos, isso não é zona quente a gerenciar socialmente — é cheiro de
arquitetura: abra issue `arquitetura:` e resolva a fronteira. Exceção deliberada:
`pagamentos/core/` — que não é quente, é **congelado e somente-leitura**.

## Lei 8 — Jurisprudência Pré-Paga

Os invariantes de dinheiro (`INVARIANTES.md`) existem, com teste-guarda, **antes da
primeira feature**. Invariante sem guarda no mesmo PR só entra na seção de dívida, com
dono e prazo. Testes-guarda são intocáveis: nunca deletar, desativar ou afrouxar para
passar.

## Lei 9 — Multissítio (uma fábrica, N lojas)

A plataforma é um único deploy servindo N domínios: "site" é dado (registro no
catálogo), nunca uma nova infraestrutura. O Host é resolvido para um site UMA vez
por requisição (middleware canônico CONV-SITE); host não cadastrado é 404 — jamais
um site padrão; `site_id` acompanha toda entidade pública e viaja nos eventos
(INV-P11). Os webhooks de pagamento vivem num único domínio de operações, estável
e independente dos sites. Domínio novo entra pela Receita R11 (DNS + cadastro),
nunca por cirurgia de infra.

## Definição de Pronto Arquitetônica (da plataforma inteira)

- Pix quebrado ⇒ cartão continua vendendo (e vice-versa)
- Webhook duplicado ⇒ uma única matrícula
- Mensageria offline ⇒ matrícula acontece; alunos offline ⇒ pagamento acontece
- Deploy de qualquer célula ⇏ deploy de qualquer outra
- Raio de explosão = 1 célula; rollback em minutos; regressão cruzada em produção = zero

## Ritos

Abertura de sessão, catraca verde/anti-thrashing, mudança de contrato e emergência:
ver `RITOS.md`. Formato de invariante (o quê / por quê / teste-guarda): ver
`INVARIANTES.md`.
