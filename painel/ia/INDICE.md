<!-- Escrito por leitura humana+IA em 27/08/2026, a pedido do mantenedor.
     Diferente de armadilhas/INDICE.md, este arquivo NÃO é gerado — é mantido
     à mão. Quem adicionar/remover um documento em painel/ia/ deve atualizar
     esta tabela no mesmo PR. -->

# Mapa do sitesdoreino para IA

> **Você é uma IA (agente, assistente, revisor) tentando entender este
> projeto para sugerir melhorias, otimizações ou mudanças.** Este diretório
> existe para você. Comece aqui.

## O que é este documento — e o que ele NÃO é

`painel/ia/` é um **mapa técnico curado**, escrito para que uma IA sem
contexto prévio consiga entender infraestrutura, arquitetura, sistema,
ferramentas e decisões deste projeto de ponta a ponta, e então propor
melhorias com informação real em vez de suposição.

O que ele não é: **não é a fonte de verdade, e não é um painel de status.**
- Onde este mapa e um documento original (`CONSTITUICAO.md`, `RITOS.md`,
  código real, etc.) divergirem, **o original vence** — este mapa é um
  resumo, escrito por leitura em 27/08/2026, e não é recalculado
  automaticamente como `painel/painel.html` é. Se você encontrar uma
  divergência, é sinal de que este mapa ficou velho: corrija-o no mesmo PR
  da sua mudança, ou abra um registro em `painel/registros/` apontando o quê.
- Este mapa não guarda nenhum veredito sobre o estado atual do projeto
  (o que está pronto, o que está pendente, quem prometeu o quê). Isso é
  papel exclusivo do livro de ocorrências (`painel/registros/`) e do painel
  calculado a partir dele — ver [03](03-sistema-do-painel-e-livro.md). Um
  mapa que inventasse seu próprio placar seria exatamente a doença que a
  reforma do painel, em 26/08/2026, existiu para curar.

## O projeto, em 3 parágrafos

O **sitesdoreino** é uma plataforma de cursos online vendidos por Pix/cartão
(Mercado Pago), multissítio (N domínios, um único deploy), com destaque
atual para uma escola de Roblox 3D ("Meshcraft Academy", em `meshcraft.top`)
e um produto de baixo valor usado para provar a esteira ponta a ponta
("Curso Esqueleto", R$9,90). É construído quase inteiramente por sessões de
IA (Claude Code) para um mantenedor que é leigo em código e terminal — essa
única característica explica boa parte das escolhas de arquitetura do
projeto: o que não pode ser mecanizado em portão de CI acaba exigindo um
passo manual do único ser humano no projeto, então mecanizar é
sistematicamente preferido a documentar.

Arquiteturalmente, é uma plataforma de **13 microsserviços Django+django-ninja
isolados ("células")** — `admin`, `alunos`, `catalogo`, `checkout`, `forum`,
`funil`, `identidade`, `leads`, `mensageria`, `notificacoes`, `pagamentos`,
`quiz`, `sugestoes` — cada uma com banco Postgres próprio, processo próprio
atrás de um Traefik roteado por caminho, e proibida de importar código ou ler
banco de outra célula. A 14ª, `gamificacao`, foi aprovada em 30/08/2026 e
nasceu no mesmo dia, com seção própria em
[04](04-arquitetura-de-celulas-e-contratos.md). Uma 16ª, `metricas` (o livro
de fatos: a única célula sem tela, que guarda a história dos números para o
painel poder dizer o que mudou), nasceu em 04/09/2026 e tem seção lá. Uma 15ª,
`encomendas` (a Fila do Primeiro Dólar, o marketplace de encomendas 3D da
escola), ganhou
lei aprovada e esqueleto em `services/` em 03/09/2026, e também tem seção em
[04]. Uma 17ª, `cursos` (a sala de aula da Meshcraft: o conteúdo do curso, o
progresso, o checkpoint, o laudo e os agentes de IA que trabalham nela), ganhou
lei aprovada e esqueleto em `services/` em 04/09/2026, com seção em [04]. Uma
18ª, `pages` (a casa das páginas do aluno: o portfólio, a Prancheta que ensina a
montá-lo e a vitrine pública em `/estudio/<apelido>`), foi liberada para
construção em 05/09/2026 e **ainda não existe em `services/`**: ela nasce no
degrau 01 da escada do plano dela, e a seção em [04] foi escrita antes do
código, de propósito. A
comunicação entre células é
só HTTP contratado (OpenAPI congelado) ou eventos versionados (outbox +
Redis Streams). Tudo
isso é lei escrita e imposta por portões mecânicos, não só convenção — ver
[01](01-leis-ritos-e-invariantes.md).

Culturalmente, é um projeto com uma disciplina de engenharia incomumente
madura para o tamanho: praticamente todo processo tem teste-guarda,
praticamente todo portão de CI segue uma semântica fail-closed de 4 estados
(PASS/FAIL/ERROR/SKIP — "não consegui medir" nunca vira "passou"), e o
projeto documenta ativamente os próprios erros passados (`armadilhas/`, ~126
entradas) e os padrões que os atravessam
(`docs/decisoes/RETROSPECTIVA-FASE-D.md`, 8 padrões — ver
[02](02-armadilhas-e-padroes-recorrentes.md)). Muita coisa que pareceria
dívida técnica vista de fora é, na verdade, uma escolha deliberada e testada
— por isso a leitura de [06](06-produto-decisoes-e-roadmap.md) antes de
propor mudança de produto, e de [01](01-leis-ritos-e-invariantes.md) antes
de propor mudança de processo, importa mais aqui do que em um projeto médio.

## Índice — leia só o que casa com sua tarefa

| # | Documento | Cobre | Leia se você for... |
|---|---|---|---|
| — | [Este arquivo] | Orientação geral, o que foi omitido | ...abrir este mapa pela primeira vez (você está aqui) |
| 01 | [Leis, Ritos e Invariantes](01-leis-ritos-e-invariantes.md) | As 9 leis da `CONSTITUICAO.md`, os ritos obrigatórios de sessão/merge/emergência, os invariantes técnicos (INV-P*, INV-CI01), as receitas do Caminho Dourado (R1-R12) | ...mexer em qualquer código — especialmente dinheiro, CI, merge, ou abrir uma sessão nova |
| 02 | [Armadilhas e Padrões Recorrentes](02-armadilhas-e-padroes-recorrentes.md) | Taxonomia do catálogo de ~126 armadilhas, os 8 padrões estruturais da retrospectiva, como o índice é gerado | ...investigar um erro específico, ou quiser não repetir uma falha já catalogada |
| 03 | [Sistema do Painel e Livro](03-sistema-do-painel-e-livro.md) | O mecanismo `painel/` inteiro — schema do registro, como as vistas são calculadas, a lei anti-duplicação, como a produção serve o painel | ...mexer em `painel/`, ou construir qualquer coisa que relate status/progresso |
| 04 | [Arquitetura de Células e Contratos](04-arquitetura-de-celulas-e-contratos.md) | O padrão de célula, tabela das 13 células **+ a 14ª em gênese (`gamificacao`: o que consome, o que oferece, o que deliberadamente não faz)**, o mecanismo de contratos (OpenAPI + eventos) e o isolamento entre células | ...entender ou mudar uma célula específica, mexer em `contracts/`, ou propor qualquer mecânica de ponto/selo/recompensa |
| 05 | [Infraestrutura, CI e Deploy](05-infraestrutura-ci-e-deploy.md) | Topologia Docker/Traefik, os 6 workflows do GitHub Actions, todos os scripts de `ci/`, deploy e rollback, integrações externas por célula | ...mexer em `infra/`, `.github/workflows/`, ou qualquer script de `ci/` |
| 06 | [Produto, Decisões e Roadmap](06-produto-decisoes-e-roadmap.md) | Mapa de features (identidade, admin, notificações, i18n, Caixa de Sugestões, pagamentos), o mecanismo de ChangeSpec, e uma lista do que não reabrir | ...avaliar prioridade de feature, ou perguntar "por que isso existe assim" |
| 07 | [Oportunidades e Fronteiras](07-oportunidades-e-fronteiras.md) | Lacunas já conhecidas, achados concretos desta pesquisa, e o método que este projeto exige antes de propor mudança | ...está exatamente caçando o que melhorar — **comece e termine sua auditoria aqui** |

## O que foi deliberadamente omitido, e por quê

Este mapa foi escrito para poder ser lido por uma IA **sem** acesso
privilegiado ao projeto — inclusive fora do ambiente de desenvolvimento.
Por isso, mesmo quando os documentos-fonte continham os itens abaixo, eles
foram deliberadamente excluídos ou generalizados aqui:

- **Nenhum endereço IP real** (a VPS de produção tem um; não está neste mapa).
- **Nenhuma credencial, token, senha ou chave privada real** — confirmado
  por varredura dedicada; o projeto também tem um portão de CI
  (`ci/guarda-de-segredos.sh`) especificamente para isso.
- **Nenhum valor de variável de ambiente real** — só nomes de variáveis
  (`MP_ACCESS_TOKEN`, `GOOGLE_CLIENT_SECRET`, etc.), nunca valores.
- Isso não empobrece o mapa para o propósito de sugerir melhorias — nenhuma
  proposta séria de arquitetura, processo ou produto depende de conhecer o
  IP da VPS ou o valor de um segredo.

## Este mapa segue a lei que ele descreve

Não é coincidência que `painel/ia/` seja uma pasta com um índice curto e
vários documentos focados, em vez de um único arquivo enorme — é a mesma
lição que o próprio projeto já aprendeu do jeito caro duas vezes
(`ARMADILHAS.md` chegou a ser 48% da carga de contexto de todo despacho
antes da reforma de 23/08/2026; ver o padrão 6 em
[02](02-armadilhas-e-padroes-recorrentes.md)). E não é coincidência que este
índice aponte para os documentos-fonte em vez de tentar substituí-los — é a
mesma lei anti-duplicação de `painel/` (ver [03](03-sistema-do-painel-e-livro.md)),
aplicada aqui a documentação em vez de a registros de fato.

## Manutenção — isto é mecanismo, não promessa

Existe um teste-guarda (`ci/tests/test_painel_ia_atualizado.py`) que reprova
a suíte de CI se uma célula existir em `services/` e não for citada em
nenhum documento deste mapa — a forma mais barata e mais provável de este
mapa ficar cego por omissão é uma célula nova nascer e ninguém atualizar
`04-arquitetura-de-celulas-e-contratos.md`. Fora desse caso específico, este
mapa **não se recalcula sozinho**: quem mudar uma lei, um portão de CI, ou
uma decisão de produto documentada aqui deveria atualizar o documento
correspondente no mesmo PR — do mesmo jeito que se espera de qualquer outro
documento deste repositório.

## Fotografia — quando isto foi escrito

Pesquisa e redação: 27/08/2026, por uma sessão de Claude Code a pedido do
mantenedor, lendo os documentos-fonte e o código reais deste repositório
(não por inferência ou por memória de treinamento). Números que mudam com o
tempo (quantidade de registros no painel, quantidade de armadilhas
catalogadas, quantidade de contratos congelados) estão marcados como
fotografia nos documentos individuais — **recontar é sempre mais confiável
que confiar no número escrito aqui.**

**Revisões desde então** (uma linha por passagem, para que quem ler saiba a
idade de cada parte):

- **30/08/2026** — [04](04-arquitetura-de-celulas-e-contratos.md) ganhou a
  seção da célula `gamificacao`, que está nascendo, e teve corrigidos os
  fatos que haviam envelhecido desde 27/08: o `forum` passou de esqueleto a
  célula com `LICOES.md` e contrato congelado, `notificacoes` também já tem
  contrato, e a contagem de contratos (que dizia "7 + 5" num projeto de 13
  células) foi refeita contra `ci/manifesto-de-contratos.json`. **Ainda
  velho, e não corrigido nesta passagem:** a contagem de armadilhas ("~126"
  aqui e em [02](02-armadilhas-e-padroes-recorrentes.md)) — o catálogo tinha
  **201** entradas em 30/08/2026, contadas por
  `python ci/indice_de_armadilhas.py`. O porquê de o guarda deste mapa não
  pegar nada disso está em `armadilhas/222`.
- **04/09/2026** — [04](04-arquitetura-de-celulas-e-contratos.md) ganhou a
  seção da célula `cursos` (a sala de aula da Meshcraft: conteúdo, progresso,
  checkpoint, laudo e os agentes de IA que trabalham nela), planejada nesse
  dia a partir dos nove documentos do projeto Meshcraft e ainda não nascida.
  Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md`.
- **04/09/2026 (noite)** — a célula `cursos` nasceu (TAR-146): a seção dela em
  [04](04-arquitetura-de-celulas-e-contratos.md) passou de "planejada" a
  "nascida", e o parágrafo das células acima ganhou a 17ª.
- **05/09/2026**: [04](04-arquitetura-de-celulas-e-contratos.md) ganhou a seção
  da célula `pages`, que **ainda não existe em `services/`** e nasce no degrau 01
  da escada. Este é o degrau 00 do `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`:
  o mapa cita a casa antes de ela ser construída, para que nenhuma IA desenhe
  portfólio de aluno ou vitrine de obra em outra célula. Corredor assinado:
  `docs/changespecs/CS-PAGES-0001.md`.
