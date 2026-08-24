# CLAUDE.md — sitesdoreino

Instruções para qualquer sessão do Claude Code neste repositório.

## Antes de começar qualquer tarefa: leia as armadilhas

A memória de campo do projeto — o que já custou tempo aqui, em formato sintoma →
causa → solução — mora em **`armadilhas/`**, uma entrada por arquivo. Desde
23/08/2026 ela **não é mais um monólito**: o antigo `ARMADILHAS.md` de 1.490 linhas
era 48% da carga de contexto de todo despacho (PLANO-10X, Alavanca 2).

**A regra de leitura, em uma frase: leia `armadilhas/INDICE.md` e abra SÓ a entrada
que casa com a sua tarefa.** O índice tem uma linha por armadilha, com a mensagem de
erro crua como chave — dê Ctrl+F pelo erro que você está vendo, ou pela tecnologia
que vai tocar. Ler a pasta inteira desfaz o motivo de ela existir. Leia também o
`ARMADILHAS.md` (que ficou curto: a regra de uso + a partida rápida do §2) e, se for
trabalhar dentro de uma célula, o `services/<celula>/LICOES.md` quando existir.

Não é formalidade: as mesmas armadilhas já pegaram mais de um agente — sombreamento
de nome entre model Django e `ninja.Schema`, o middleware que derruba o `/healthz`, o
orçamento de 15 arquivos que decide a arquitetura antes de você escrever código. Cada
redescoberta custa tokens e uma rodada de teste.

**Ao terminar, acrescente o que aprendeu** — isso faz parte de terminar a tarefa, como
o painel. Regra de onde escrever: se serve para qualquer célula, **crie um arquivo
novo** `armadilhas/NNN-slug.md` (NNN = próximo número livre) e rode
`python ci/indice_de_armadilhas.py` para regenerar o índice; se só faz sentido dentro
de uma célula, vai no `LICOES.md` dela. **Nunca acrescente ao fim do `ARMADILHAS.md`
nem edite a entrada de outro agente para encaixar a sua** — arquivo novo por entrada
é exatamente o que faz duas sessões paralelas pararem de colidir no mesmo hunk.

**Se a correção definitiva não estiver nas suas mãos** — depende de instalar algo na
máquina, de plano pago, de permissão — registre na tabela `§1 — PRECISA DE VOCÊ` do
**`ARMADILHAS-OPERACAO.md`** (o arquivo do humano: §1, como se mergeia, painéis, §9
dívidas abertas) **e diga isso ao usuário no relatório final, em texto claro**. Ele
não lê o documento a cada sessão; se você contornar em silêncio, o mesmo atrito volta
no próximo despacho, e no seguinte.

## O painel vivo é obrigatório, não opcional

`arquivos/painel-fundacao.html` é o checklist vivo deste projeto — feito para o
dono do projeto (leigo em código) acompanhar o que está acontecendo sem
precisar ler a conversa inteira ou o histórico do Git.

**Regra permanente:** depois de CADA tarefa relevante — iniciada, concluída,
falhou, ficou bloqueada, ou mudou de estado — atualize
`arquivos/painel-fundacao.html` refletindo a realidade, **sem perguntar se
deve fazer isso**. Atualizar o painel é parte de terminar a tarefa, não um
passo extra opcional. Isso inclui:

- Marcar itens do checklist como concluídos assim que houver evidência real
  (nunca por promessa ou intenção).
- Atualizar notas nos itens quando o resultado mudar.
- Registrar incidentes relevantes (merge inesperado, CI vermelho, revert,
  qualquer coisa que quebrou e foi consertada) na seção "Linha do tempo de
  incidentes".
- Manter a caixa "Precisa de você agora" honesta: só o que está *realmente*
  em aberto, nem mais, nem menos.
- **Merge é gatilho de painel, não pergunta.** Desde 22/08/2026 quem mergeia é
  o agente (seção "Mergear é trabalho do agente" abaixo): mergeou, atualize o
  painel na MESMA resposta. E se um merge acontecer fora da sessão (o usuário
  clicou no site, outra sessão mergeou) e alguém o confirmar — em qualquer
  forma ("feito", "ok", um link, um "✓", mesmo em sessão diferente da que
  abriu o PR) — vale o mesmo gatilho: confira o merge de verdade
  (`gh pr view <N> --json state,mergedBy,mergeCommit`) e atualize o painel sem
  esperar a pergunta. A confirmação é o gatilho para checar, não um substituto
  para checar.

Não pergunte "quer que eu atualize o painel?". Atualize, e diga o que mudou.
Perguntar antes de agir continua valendo para a AÇÃO em si quando ela for
arriscada (push direto na `main`, apagar algo irrecuperável, agir fora do
mandato do despacho) — não para manter o painel em dia, que é sempre de baixo
risco e reversível.

## Mergear é trabalho do agente (desde 22/08/2026)

Decisão do mantenedor — motivos e mecânica em
`docs/decisoes/DECISAO-merge-pelo-agente.md`; lei: `CONSTITUICAO.md` Lei 4;
rito: `RITOS.md` §2 peça 4. O fluxo, sem perguntar "posso mergear?":

1. PR aberto dentro do escopo de um despacho → espere os checks concluírem.
2. `python ci/mergear.py <N> --conferir` — tudo verde?
3. `python ci/mergear.py <N> --confirmo <N>` — mergeia e já confere no GitHub
   que o PR virou `MERGED`.
4. Painel; e, se o merge toca `services/` ou `infra/`, o veredito do run de
   deploy (seção "Depois de todo merge que dispara deploy").

Vermelho, pendente, ausente ou ERROR **nunca** se mergeia — conserte ou
reporte. O botão de merge do site não é caminho para ninguém. Merge em caminho
CODEOWNERS (`contracts/`, `pagamentos`, `checkout`, `infra/`, `ci/`,
`.github/`, arquivos-lei da raiz) só com mandato do despacho, e **anunciado
nominalmente no relatório final**.

**Vários despachos em paralelo (lote):** a sessão raiz rege pelo
`RUNBOOK-LOTES.md` — composição, as sete regras de inteligência, janela de
merge serial e fechamento. Se o mantenedor pedir "toque um lote", é esse
documento que define o como.

Se o painel ainda não tiver uma seção adequada para o que aconteceu, crie uma
(ex.: a "Linha do tempo de incidentes" foi criada assim, sob demanda) — o
painel deve crescer para caber a realidade do projeto, não o contrário.

## Como trabalhar com o mantenedor (vale para TODA sessão)

O dono do projeto é leigo em código e em terminal, e lê SOMENTE português —
**toda resposta em PT-BR, sempre**. O resto foi aprendido a custo alto em
21-22/08/2026, no dia em que a plataforma subiu (ele quase desistiu do projeto
no meio dos passos manuais):

- **Faça você o máximo.** Tudo que der por `gh`, pipeline e arquivos, o agente
  faz — o mantenedor só entra onde é insubstituível (segredos, console do
  provedor; desde 22/08/2026 nem o merge: ele é do agente, seção acima).
  Agente não tem SSH para a VPS (Lei 5) e o harness bloqueia a tentativa —
  não insista; o canal do agente é o pipeline.
- **Quando sobrar passo manual, entregue UM bloco único de colar**, fail-closed
  (que se recusa a agir se algo estiver estranho, com uma mensagem tipo "PAROU
  POR SEGURANÇA"), nunca uma sequência de comandos avulsos para digitar um a um.
- **Diga SEMPRE em qual janela colar.** A confusão mais repetida da história do
  projeto: rodar comando do PC dentro da VPS e vice-versa. Regra de bolso que
  funcionou: linha começando com `PS C:\>` = PC; começando com `deploy@srv...`
  ou `root@srv...` = já está DENTRO da VPS (não use `ssh` aí).
- **Avise as surpresas de terminal antes delas acontecerem**: senha invisível ao
  digitar, silêncio = sucesso, a diferença entre `>>` (acrescenta) e `>` (apaga).
- **Reporte em linguagem de resultado** ("a plataforma está no ar"), não de
  processo — e marcos merecem ser celebrados. O ânimo do mantenedor é parte da
  infraestrutura do projeto.

## Depois de todo merge que dispara deploy

Merge tocando `services/**` dispara o `deploy-celula`; tocando
`infra/docker-compose.yml`, `infra/traefik/**` ou o próprio workflow, dispara o
`deploy-infra`. **Merge confirmado ⇒ conferir o run disparado**, na mesma
resposta — o veredito REAL vem de `gh run view <id> --json status,conclusion`,
nunca do exit de um comando com `| tail`/`| head` pendurado (ARMADILHAS §5.10:
já houve falso-verde assim, e os greens históricos do deploy-celula mentiram
até 21/08/2026 — H13). Run vermelho: `gh run view <id> --log-failed` mostra
onde parou; repete-se sem novo merge com `gh run rerun <id> --failed`. Reporte
o veredito ao mantenedor em texto claro — não há required check (H3), ninguém
mais vai olhar por você.
