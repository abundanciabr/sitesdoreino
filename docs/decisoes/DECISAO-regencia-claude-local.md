# Regência do Claude com proteção instalada na máquina

Em 13/09/2026 o mantenedor pediu impedir que Claude Code execute o trabalho
do Codex e multiplique agentes em um pedido de plano. As capturas mostram
um Workflow com 14 agentes e 3,3 milhões de tokens; não provam que o painel
local solicitado naquela conversa tenha sido implementado.

O PR #1606 contém uma trava de subagentes ainda fora da main. Ela permite
Explore e revisor sem orçamento agregado. O clone usado pelo Claude também
está antigo e tem alterações de outras sessões. Esta entrega complementa
esse trabalho com instalação local, sem substituir os arquivos do espelho.

Claude rege: lê, escreve briefs em uma bancada e cria tarefas na fila;
a integração é automática. Plano, pesquisa e construção vão ao Codex. Agent, Task,
Workflow, edição de código, shell arbitrário e ferramentas não reconhecidas
são recusados. A guarda aceita somente os comandos enumerados de regência;
ela não tenta interpretar programas shell. Revisão independente usa o Codex
ou o Antigravity; não dispara outro agente do Claude.

Em 14/09/2026 o mantenedor elevou o teto de 180.000 para 800.000, incluindo
cache. Vale o valor explícito de 800.000 (4,44 vezes o anterior); quatro vezes
180.000 seriam 720.000. O consumo acumulado é preservado na reinstalação.

O teto operacional é 800.000 tokens registrados por sessão, somando entrada,
criação e leitura de cache e saída, sem contar novamente blocos da mesma
resposta. Este é um limite de consumo acumulado, distinto do teto de contexto
do brief. Ao atingir o teto ou perder a medição, PreToolUse devolve
`continue: false`. A leitura do transcript nesta guarda é restrita à medição;
nenhuma mensagem é injetada no contexto ou publicada. Compactar não autoriza
gastar outro orçamento nem criar sessão para contornar a parada.

O limite é conferido antes da próxima ferramenta. Não interrompe geração
em andamento, não é limite financeiro do provedor e não cancela Workflows
já iniciados. Uma resposta pode ultrapassá-lo. O harness precisa carregar
o hook: instalar não prova que uma sessão antiga o recarregou.

Instalação pelo Codex na bancada: `python ci/regencia_claude.py instalar`.
O comando copia a guarda para `~/.claude/hooks/sitesdoreino-regencia/`, mantém
backup de `~/.claude/settings.json` e acrescenta um PreToolUse global com
escopo por repositório Git, incluindo seus worktrees. Outras configurações
e outros projetos permanecem preservados. Repetir a instalação atualiza
a cópia sem duplicar o hook. Reversão: remover somente a entrada que aponta
para `sitesdoreino-regencia` em PreToolUse; o backup permite conferir os
valores anteriores sem sobrescrever configurações acrescentadas depois.

**Quem faz valer:** `ci/regencia_claude.py` e `ci/tests/test_regencia_claude.py`.
Contrato do hook: [documentação oficial do Claude](https://code.claude.com/docs/en/hooks).
