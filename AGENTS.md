# AGENTS.md | sitesdoreino

Regra de intenção: todo pedido neste projeto é execução com validação e entrega
no destino que o mantenedor pediu. Conteúdo destinado a pessoas fica no site;
artefato técnico indispensável ao funcionamento fica no repositório. Conversa
informal fica fora deste fluxo.

Leia `CLAUDE.md` antes de agir: é a lei canônica, com o significado integral do
Padrão abaixo, as três costuras e as regras de operação. Não há uma segunda
versão dessas leis aqui. Leia `CONSTITUICAO.md`, `RITOS.md` e instruções
dos caminhos do brief; contexto direcionado não dispensa leis.

| Regra | Padrão de Trabalho, referência para a lei canônica |
|---|---|
| 1 | Resolva o problema real; comece pela experiência e protótipo quando necessário. |
| 2 | Discorde antes, com alternativa e trade-off; execute a decisão dele. |
| 3 | Justifique adições; o pedido vira o menor caminho funcional que já funciona; elimine excesso. |
| 4 | Decida o que é seu; decisões exclusivas ou irreversíveis voltam ao mantenedor. |
| 5 | Responda pelo caminho inteiro, do primeiro comando até a tela. |
| 6 | Prove com comando e saída real; sem prova escreva NÃO RODEI. Prometer o conserto não é consertar. |
| 7 | Remova o que não faz falta ao pedido. |
| 8 | Revise como crítico, corrija antes de entregar. |
| 9 | Demonstre; checklist e cinco blocos finais, sem enchimento. |
| 10 | Não substitua prova por promessa nem use as frases proibidas. |
| 11 | Conversa é mudança real; interrompa loops. Nunca pergunte nem informe a outra IA o estado de Git, PR, checks, branches ou pouso: consulte a fonte e aja. |

No Codex, as fichas ficam em `.codex/agents/`; modelo e esforço vêm de
`python ci/economia_da_fabrica.py brief`. A sessão executa o pedido dentro
do mandato recebido, com validação, PR e registro pelo `make pr`.
As competências das fichas são por tarefa, sem papéis fixos por fornecedor.
Subagente não cria outro nem pergunta ao mantenedor; devolve por escrito
bloqueio, impacto e ação para destravar à sessão responsável.
Nunca edite o clone principal nem amplie o mandato. Trabalho descoberto
fora do brief vira tarefa na fila. Integração é automática pelos portões.

## Destino padrão do pedido do mantenedor

Manual, documento, página, guia, roteiro, texto, conteúdo, anúncio,
explicação ou qualquer material feito para ser lido no site deve nascer no
site, pelo editor de documentos de `/admin/documentos/`, e terminar publicado
com URL pública conferida. Criar um Markdown em `docs/` ou outro arquivo no
GitHub não é publicação e não substitui essa entrega.

O GitHub só recebe a parte obrigatória para o funcionamento do site, sistema
ou projeto: código, template, teste, contrato, configuração, infraestrutura,
workflow, lei mecânica e registro exigido pelo rito. Um manual ou documento
pedido pelo mantenedor não vai para o GitHub apenas por ser mais fácil de
editar ali.

Se a publicação exigir acesso, rota ou mecanismo que ainda não exista, a sessão
registra o bloqueio e o que falta. Ela não troca o destino para um PR de
documentação. Quando o pedido for ambíguo, o destino padrão é o site, salvo se
o mantenedor disser que o artefato é interno, técnico ou obrigatório ao código.

Execute no PowerShell tudo que puder executar. Antes de passo manual ou
decisão do mantenedor, leia `docs/guia-mantenedor.md`. Sempre PT-BR.
Na primeira resposta de qualquer sessão que vá trabalhar no projeto, declare
o caminho absoluto da pasta ativa. Se for
`C:\Users\davia\abundanciabr\sitesdoreino`, pare: é a pasta antiga preservada.
Use `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923` para trabalho novo.
`python ci/sessao.py --celula <area> --tarefa <slug>` abre a bancada;
sem serviço, acrescente `--sem-container`. Principal é somente leitura,
salvas as operações permitidas na lei canônica.
Para execução, descobertas, checkpoints, retomada e ausência de progresso,
use `docs/decisoes/ROTEIRO-EXECUCAO-DOS-AGENTES.md`; o estado continua vindo
da fila e de seus eventos, não do roteiro.

Hooks nativos estão em `.codex/hooks.json`: SessionStart, UserPromptSubmit,
Stop e a guarda de Monitor. Ações comuns não injetam documentos nem leem
transcript. Texto publicado é verificado no pre-commit e CI.
Consulte erros por `python ci/consultar_armadilhas.py "<mensagem>"` ou
`--caminho <arquivo>`; abra somente origens pertinentes.

No fecho, checklist atualizado e **O que mudou**, **O que foi verificado**,
**Pendências**, **Veredito** PRONTO ou NÃO PRONTO, e **Instruções** com o que
acontece agora. NÃO PRONTO exige lista em português de leigo: o que houve, de
quem é a bola, o que destrava e o prazo, mesmo que nada dependa dele; o gancho
recusa o fecho sem ela. Auditoria item a item
somente quando relevante; cortes somente quando houver.
Despacho devolve número do PR, ramo, SHA, arquivos, CODEOWNERS e provas.
O PR pronto integra automaticamente quando muralhas e ci-celula-gate ficam
verdes, sem revisor obrigatório, atestado ou etiqueta de pouso.
CODEOWNERS e contrato congelado continuam exigindo mandato do mantenedor.
Validação local, integração e publicação são estados distintos e exigem prova.

**Quem faz valer:** `ci/padrao_de_trabalho.py`, `ci/hook_codex.py`,
`ci/prestacao_de_contas.py`, `ci/mergear.py` e respectivos testes.
