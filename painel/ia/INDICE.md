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
  resumo, originalmente escrito em 27/08/2026 e revisto em 10/09/2026 contra
  a revisão `12101ba`; ele não é recalculado automaticamente como
  `painel/painel.html` é. Se você encontrar uma
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

Arquiteturalmente, é uma plataforma de serviços Django+django-ninja isolados,
chamados de células. `celulas.yml` lista as células atuais, seus caminhos e os
consumos HTTP; `ci/manifesto-de-contratos.json` declara o estado dos contratos;
e [04](04-arquitetura-de-celulas-e-contratos.md) explica as fronteiras. Cada
célula tem processo e banco próprios atrás do Traefik e não importa código nem
lê o banco de outra. A comunicação legítima ocorre por HTTP contratado ou por
eventos versionados. Confira a revisão e rode `python -B
ci/mapa_de_celulas.py --verificar` antes de usar o inventário numa decisão.

Culturalmente, os portões usam a semântica fail-closed de quatro estados
(PASS, FAIL, ERROR e SKIP), e o projeto registra erros em `armadilhas/` e
padrões transversais em `docs/decisoes/RETROSPECTIVA-FASE-D.md`. Materialize
`armadilhas/INDICE.md` para a revisão atual em vez de confiar numa contagem
copiada. Leia [06](06-produto-decisoes-e-roadmap.md) antes de propor mudança
de produto e [01](01-leis-ritos-e-invariantes.md) antes de mudar processo.

## Prompt para construir o GPS de execução

O documento versionado `docs/decisoes/PROMPT-EQUIPE-MAPA-DE-EXECUCAO.md` é o
prompt integral para abrir uma nova conversa, montar a equipe e construir o
mapa operacional derivado. Ele prepara essa obra; não declara que o GPS já está
implementado. Depois do merge e do deploy comprovados, sua rota pública é
[`/mapa-ia/planos/PROMPT-EQUIPE-MAPA-DE-EXECUCAO.md`](/mapa-ia/planos/PROMPT-EQUIPE-MAPA-DE-EXECUCAO.md).

## Índice — leia só o que casa com sua tarefa

| # | Documento | Cobre | Leia se você for... |
|---|---|---|---|
| — | [Este arquivo] | Orientação geral, o que foi omitido | ...abrir este mapa pela primeira vez (você está aqui) |
| 01 | [Leis, Ritos e Invariantes](01-leis-ritos-e-invariantes.md) | A Constituição vigente, os ritos obrigatórios de sessão/merge/emergência, os invariantes técnicos e as receitas do Caminho Dourado | ...mexer em qualquer código — especialmente dinheiro, CI, merge, ou abrir uma sessão nova |
| 02 | [Armadilhas e Padrões Recorrentes](02-armadilhas-e-padroes-recorrentes.md) | Taxonomia do catálogo de armadilhas, padrões estruturais da retrospectiva e geração do índice | ...investigar um erro específico, ou quiser não repetir uma falha já catalogada |
| 03 | [Sistema do Painel e Livro](03-sistema-do-painel-e-livro.md) | O mecanismo `painel/` inteiro — schema do registro, como as vistas são calculadas, a lei anti-duplicação, como a produção serve o painel | ...mexer em `painel/`, ou construir qualquer coisa que relate status/progresso |
| 04 | [Arquitetura de Células e Contratos](04-arquitetura-de-celulas-e-contratos.md) | O padrão de célula, fontes do inventário atual, fronteiras, contratos OpenAPI, eventos e isolamento entre células | ...entender ou mudar uma célula específica, mexer em `contracts/`, ou propor qualquer mecânica de ponto/selo/recompensa |
| 05 | [Infraestrutura, CI e Deploy](05-infraestrutura-ci-e-deploy.md) | Topologia Docker/Traefik, fontes dos workflows atuais, scripts de `ci/`, deploy, rollback e integrações externas | ...mexer em `infra/`, `.github/workflows/`, ou qualquer script de `ci/` |
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

## Fontes de frescor

- Células e consumo HTTP: `celulas.yml` e `python -B
  ci/mapa_de_celulas.py --verificar`.
- Contratos: `ci/manifesto-de-contratos.json`, `contracts/` e o exportador de
  cada célula.
- Rotas: `painel/mapa-do-site.json` e `python -B
  ci/mapa_do_site.py --verificar`, com os limites declarados pelo verificador.
- Estado de trabalho: `python ci/fila.py listar --ao-vivo --json`, eventos da
  fila, livro e GitHub.
- Armadilhas: índice materializado por `python ci/indice_de_armadilhas.py`.

Se uma fonte não puder ser consultada, escreva `NÃO MEDIDO`. O teste de
presença deste mapa não certifica seus fatos; `armadilhas/222` explica o limite.
