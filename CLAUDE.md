# CLAUDE.md — sitesdoreino

Instruções para qualquer sessão do Claude Code neste repositório.

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

Não pergunte "quer que eu atualize o painel?". Atualize, e diga o que mudou.
Perguntar antes de agir continua valendo para a AÇÃO em si quando ela for
arriscada (push direto, merge, apagar algo) — não para manter o painel em
dia, que é sempre de baixo risco e reversível.

Se o painel ainda não tiver uma seção adequada para o que aconteceu, crie uma
(ex.: a "Linha do tempo de incidentes" foi criada assim, sob demanda) — o
painel deve crescer para caber a realidade do projeto, não o contrário.
