# O documento auditado não continua auditado depois que você aplica as respostas nele

**Sintoma:** não há erro nenhum, e é esse o problema. Um documento passa por uma
auditoria séria — no caso real, **quatro cadeiras independentes**, com achados
convergentes, todos corrigidos. Em seguida o mantenedor responde as perguntas
que a auditoria deixou em aberto, e o agente aplica as respostas no mesmo
documento. Uma revisão feita **depois disso** acha quatro erros de fato, **três
deles introduzidos exatamente por essas edições pós-auditoria**:

1. Uma CSP escrita como `frame-ancestors 'none'` para "endurecer" a área —
   recriando, por dentro da célula, o mesmo bug de iframe que a auditoria tinha
   acabado de pegar no `frameDeny` do Traefik (`'none'` proíbe enquadramento
   **inclusive de mesma origem**).
2. "Isso pega carona no mesmo Rito §3 que o PR já vai fazer, sem PR extra" —
   quando aquele PR **não fazia rito nenhum**. Custo real escondido: uma sessão
   de arquitetura com o mantenedor + 2 PRs.
3. Uma lista de provedoras de métrica reaproveitada da auditoria, sem notar que
   a resposta nova do mantenedor (liberar a seção de marketing) acrescentava uma
   célula que não estava nela.
4. Um dado prometido como "existe hoje" que não existe em lugar nenhum do
   repositório — a afirmação foi escrita ao lado de outros três dados que de
   fato existem, e a vizinhança fez parecer conferido.

**Causa:** a auditoria valida **um estado do documento**, não o arquivo. Depois
dela, tanto o humano quanto o agente passam a tratar o documento como
"já revisado" — e as edições seguintes entram com a guarda baixa, justamente
quando a atenção está na *decisão* que está sendo registrada, e não na
*mecânica* de quem vai executá-la. Some a isso o efeito de vizinhança: uma
afirmação nova escrita no meio de afirmações já verificadas herda a confiança
delas sem ter passado por nada.

Note o tipo dos erros: nenhum deles é sobre o que foi decidido. Todos são sobre
**como a decisão seria executada** — CSP, ordem de ritos, contagem de PRs,
existência do dado. É o que se degrada quando a cabeça está no "o quê".

**Solução:**

1. **Toda edição pós-auditoria é código não revisado, não documento revisado.**
   Ao aplicar respostas num documento auditado, releia o diff **como se outra
   pessoa o tivesse escrito** — e confira no código cada afirmação nova, sem
   crédito pela vizinhança.
2. **Desconfie especialmente de três frases**, que foram exatamente as que
   falharam aqui: *"pega carona em X"*, *"sem PR extra"*, *"esse dado já
   existe"*. As três afirmam um fato sobre o resto do sistema, e as três são
   verificáveis em menos de um minuto (`grep` no manifesto, no contrato, nos
   models).
3. **Ao endurecer segurança, confira se o endurecimento não quebra um requisito
   que o próprio documento tem.** `'none'` é sempre mais seguro que `'self'` —
   e às vezes o documento, três seções abaixo, exige `'self'`.
4. **Quando a correção for desfazer uma frase errada, desfaça com todas as
   letras** — "o texto anterior dizia X, e X é falso porque Y". Corrigir em
   silêncio faz o leitor seguinte encontrar duas versões do plano em duas
   conversas e não saber qual vale.

**Origem:** revisão final do `PLANO-AREA-ADMIN.md`, 25/08/2026, pedida pelo
mantenedor ("só uma revisão para eu ter certeza de que tudo está ok") depois de
o documento já ter sido auditado por banca **e** atualizado com as seis
respostas dele. Parente do padrão 2 da `RETROSPECTIVA-FASE-D.md` (*garantia
declarada sem mecanismo apodrece*), com uma diferença que vale registrar: aqui
a garantia não apodreceu com o tempo — **nasceu podre, dentro da própria
correção**, minutos depois de o documento estar limpo.
