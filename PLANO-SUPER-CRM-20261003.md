# Super CRM no site — plano, 03/10/2026

## Contatos do CRM

Contatos são apenas os leads captados nos quizzes, conforme correção do mantenedor
em 03/10/2026. Cadastro de aluno, pedido ou pagamento sozinho não cria um contato.
A lista, as fichas, o quadro e seus totais usam a origem registrada no quiz, inclusive
quando essa captura está preservada no histórico e a origem atual mudou.

## Levantamento inicial da base técnica (03/10/2026)

- Serviço `leads`: **100 registros de pessoas**, 83 com telefone, 99 no site principal.
  Essa era a base inteira do serviço, não a quantidade de contatos vindos dos quizzes.
- Linha do tempo de cada pessoa: **188 eventos** — 78 pedidos, 44 pagamentos recusados,
  37 quizzes respondidos, 18 pagamentos aprovados, 10 Pix vencidos sem pagar.
- Funil de oportunidades já modelado (nova → qualificada → proposta → negociação →
  ganha/perdida), com responsável, próximo passo com prazo, histórico e passagem de
  responsável entre pessoas da equipe. No levantamento inicial havia **0 oportunidades**.
- Em volta: 212 matrículas (alunos), WhatsApp (12 mensagens), jornadas de e-mail,
  fórum, pontos, encomendas, painel da equipe e robô do painel.
- As telas de contatos e CRM foram construídas e publicadas após esse levantamento.

## O dinheiro parado

O levantamento inicial trouxe 44 pagamentos recusados e 10 Pix vencidos contra 18
aprovados na base técnica, incluindo testes. Isso não mede dinheiro real parado.
No CRM, a recuperação acompanha apenas os contatos captados pelos quizzes.

## Fases

1. **Ficha do contato** — `https://meshcraft.top/admin/contatos/`: lista com busca e a ficha de cada
   pessoa com origem, etiquetas e linha do tempo em português.
2. **Recuperar venda** — `https://meshcraft.top/admin/crm/`: pagamento recusado ou Pix vencido abre sozinho uma oportunidade
   "recuperar", com responsável e prazo; quadro por etapa no admin; ao pagar, vira "ganha".
3. **Conversa no mesmo lugar** — WhatsApp e e-mails enviados aparecem na ficha; botão de
   mandar WhatsApp dali (depende da retomada da API do WhatsApp).
4. **Histórico do lead** — quando um contato vindo do quiz se torna aluno, a ficha
   pode mostrar seus cursos, progresso, pontos, fórum e compras. A matrícula sozinha
   não inclui uma pessoa na lista de contatos.
5. **Robô no CRM** — o robô do painel lê a ficha, sugere o próximo passo e entrega de
   manhã "com quem falar hoje"; segmentos prontos para campanhas.
6. **Números** — receita por origem/campanha, quanto da venda recusada foi recuperada,
   tempo até fechar.

## Construção da primeira entrega

Fases 1 e 2 publicadas em `https://meshcraft.top/admin/crm/` e
`https://meshcraft.top/admin/contatos/`. Conferência de produção em 03/10/2026:
103 registros de pessoas e 195 acontecimentos na base técnica inteira; 53 oportunidades construídas a partir
dos eventos existentes. A repetição criou zero oportunidades novas.

Há registros explicitamente identificados como testes e sandbox nessa base.
O quadro os oculta por padrão e permite mostrá-los pelo filtro, sem apagar
o histórico. Ausência de identificação de teste não comprova venda real.

Implementados: contatos pesquisáveis e paginados, ficha com origem, etiquetas,
consentimentos e histórico em português; quadro de oportunidades com etapas,
responsável, próximo passo e prazo; notas de acompanhamento e encerramento.

Recusas e Pix vencidos abrem uma oportunidade por compra, sem repetir tentativas.
Aprovação fecha a oportunidade. Estorno ou contestação confirmado retira a compra
das recuperadas. Compra já aprovada antes da recusa não infla essa contagem.
As compras pagas após uma tentativa são contadas pelo histórico registrado;
esse número não atribui automaticamente a venda ao atendimento humano.

O recorte corrigido do CRM exibe exclusivamente contatos e oportunidades de leads
dos quizzes. Os demais registros do serviço permanecem preservados.

As fases 3 a 6 continuam como próximas entregas. A conexão e o envio real do
WhatsApp precisam ser concluídos para integrar as conversas à ficha.
