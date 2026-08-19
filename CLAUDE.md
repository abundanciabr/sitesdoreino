# CLAUDE.md — sitesdoreino

Instruções para qualquer sessão do Claude Code neste repositório.

## Antes de começar qualquer tarefa: leia as armadilhas

`ARMADILHAS.md` (raiz) é a memória de campo do projeto: o que já custou tempo aqui,
em formato sintoma → causa → solução. **Leia antes de escrever a primeira linha**, e
se for trabalhar dentro de uma célula, leia também `services/<celula>/LICOES.md`
quando existir (o mesmo, mas específico daquela célula).

Não é formalidade: as mesmas armadilhas já pegaram mais de um agente — sombreamento
de nome entre model Django e `ninja.Schema`, o `python3` que dá falso-positivo no
freeze de contrato, o orçamento de 15 arquivos que decide a arquitetura antes de você
escrever código. Cada redescoberta custa tokens e uma rodada de teste.

**Ao terminar, acrescente o que aprendeu** — isso faz parte de terminar a tarefa, como
o painel. Regra de onde escrever: se serve para qualquer célula, vai em
`ARMADILHAS.md`; se só faz sentido dentro de uma célula, vai no `LICOES.md` dela.

**Se a correção definitiva não estiver nas suas mãos** — depende de instalar algo na
máquina, de plano pago, de permissão — registre na tabela `§1 — PRECISA DE VOCÊ` do
`ARMADILHAS.md` **e diga isso ao usuário no relatório final, em texto claro**. Ele não
lê o documento a cada sessão; se você contornar em silêncio, o mesmo atrito volta no
próximo despacho, e no seguinte.

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
- **Confirmação de merge de PR é gatilho, não pergunta.** Assim que o usuário
  confirmar que um PR foi mergeado — em qualquer forma ("feito", "mergeado",
  "ok", um link, um "✓" — não precisa ser a palavra exata — mesmo que a
  confirmação chegue em uma sessão diferente da que abriu o PR), isso conta
  como "tarefa mudou de estado": atualize o painel na mesma resposta, sem
  esperar a pergunta "o painel foi atualizado?". Antes de marcar como
  concluído, confira o merge de verdade (`gh pr view <N> --json state,
  mergedBy,mergeCommit`) — a confirmação do usuário é o gatilho para checar,
  não um substituto para checar.

Não pergunte "quer que eu atualize o painel?". Atualize, e diga o que mudou.
Perguntar antes de agir continua valendo para a AÇÃO em si quando ela for
arriscada (push direto, merge, apagar algo) — não para manter o painel em
dia, que é sempre de baixo risco e reversível.

Se o painel ainda não tiver uma seção adequada para o que aconteceu, crie uma
(ex.: a "Linha do tempo de incidentes" foi criada assim, sob demanda) — o
painel deve crescer para caber a realidade do projeto, não o contrário.
