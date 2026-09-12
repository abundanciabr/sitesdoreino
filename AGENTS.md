# AGENTS.md | sitesdoreino

Regra de intenção: todo pedido neste projeto é execução no código, com mudança,
validação e entrega no repositório. Conversa informal fica fora deste fluxo.

Leia `CLAUDE.md` antes de agir: é a lei canônica, com o significado integral do
Padrão abaixo, as três costuras e as regras de operação. Não há uma segunda
versão dessas leis aqui. Leia `CONSTITUICAO.md`, `RITOS.md` e instruções
dos caminhos do brief; contexto direcionado não dispensa leis.

| Regra | Padrão de Trabalho, referência para a lei canônica |
|---|---|
| 1 | Resolva o problema real; comece pela experiência e protótipo quando necessário. |
| 2 | Discorde antes, com alternativa e trade-off; execute a decisão dele. |
| 3 | Justifique adições, preserve o pedido inteiro e elimine excesso. |
| 4 | Decida o que é seu; decisões exclusivas ou irreversíveis voltam ao mantenedor. |
| 5 | Responda pelo caminho inteiro, do primeiro comando até a tela. |
| 6 | Prove com comando e saída real; sem prova escreva NÃO RODEI. |
| 7 | Remova o que não faz falta ao pedido. |
| 8 | Revise como crítico, corrija antes de entregar. |
| 9 | Demonstre; checklist e quatro blocos finais, sem enchimento. |
| 10 | Não substitua prova por promessa nem use as frases proibidas. |

No Codex, as fichas ficam em `.codex/agents/`; modelo, esforço e teto vêm de
`python ci/economia_da_fabrica.py brief`. A maestro divide e delega;
despacho não cria subagente nem pergunta ao mantenedor.

Na tríade (`docs/decisoes/DECISAO-triade-de-ias.md`), o Codex é o EXECUTOR:
implementa decisões e testa o próprio trabalho pela ficha `despacho`; não
decide arquitetura ou lei por conta própria nem rege lote. Claude Code somente
rege: decide, prioriza, prepara briefs, acompanha e encaminha. Antigravity só
audita e verifica com independência. Pedido direto não muda papel. Subagentes
herdam os limites da IA que os lançou; nomes não transferem autoridade, e
Claude Code não implementa por subagente. Autorrevisão técnica do Codex não
substitui a revisão nem a verificação independente da tríade.

Execute no PowerShell tudo que puder executar. Antes de passo manual ou
decisão do mantenedor, leia `docs/guia-mantenedor.md`. Sempre PT-BR.
`python ci/sessao.py --celula <area> --tarefa <slug>` abre a bancada;
sem serviço, acrescente `--sem-container`. Principal é somente leitura,
salvas as operações permitidas na lei canônica.

Hooks nativos estão em `.codex/hooks.json`: SessionStart, UserPromptSubmit,
Stop e a guarda de Monitor. Ações comuns não injetam documentos nem leem
transcript. Texto publicado é verificado no pre-commit e CI.
Consulte erros por `python ci/consultar_armadilhas.py "<mensagem>"` ou
`--caminho <arquivo>`; abra somente origens pertinentes.

No fecho, checklist atualizado e **O que mudou**, **O que foi verificado**,
**Pendências**, **Veredito** PRONTO ou NÃO PRONTO. Auditoria item a item
somente quando relevante; cortes somente quando houver.
Despacho devolve número do PR, ramo, SHA, arquivos, CODEOWNERS e provas.
A maestro confere revisão independente e recibo, pede
`python ci/mergear.py <N> --pousar`, confirma etiqueta e SHA e encerra.
A pista acompanha checks, integração e publicação; nenhum deles é
sinônimo de validação local ou encaminhamento.

**Quem faz valer:** `ci/padrao_de_trabalho.py`, `ci/hook_codex.py`,
`ci/prestacao_de_contas.py`, `ci/mergear.py` e respectivos testes.
