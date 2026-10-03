# Super CRM no site — plano, 03/10/2026

## O que já existe (contado no banco do site em 03/10/2026)

- Serviço `leads` (contatos): **100 pessoas**, 83 com telefone, 99 delas no site principal.
- Linha do tempo de cada pessoa: **188 eventos** — 78 pedidos, 44 pagamentos recusados,
  37 quizzes respondidos, 18 pagamentos aprovados, 10 Pix vencidos sem pagar.
- Funil de oportunidades já modelado (nova → qualificada → proposta → negociação →
  ganha/perdida), com responsável, próximo passo com prazo, histórico e passagem de
  responsável entre pessoas da equipe. **Ainda 0 oportunidades**: nada cria nem mostra.
- Em volta: 212 matrículas (alunos), WhatsApp (12 mensagens), jornadas de e-mail,
  fórum, pontos, encomendas, painel da equipe e robô do painel.
- Falta o principal: **nenhuma tela mostra os contatos**. Os dados estão lá, ninguém vê.

## O dinheiro parado

44 pagamentos recusados + 10 Pix vencidos contra 18 aprovados. Quem tentou pagar e não
conseguiu é a lista mais quente que o site tem. A primeira utilidade do CRM é essa.

## Fases

1. **Ficha do contato** — `https://meshcraft.top/admin/contatos/`: lista com busca e a ficha de cada
   pessoa com origem, etiquetas e linha do tempo em português.
2. **Recuperar venda** — `https://meshcraft.top/admin/crm/`: pagamento recusado ou Pix vencido abre sozinho uma oportunidade
   "recuperar", com responsável e prazo; quadro por etapa no admin; ao pagar, vira "ganha".
3. **Conversa no mesmo lugar** — WhatsApp e e-mails enviados aparecem na ficha; botão de
   mandar WhatsApp dali (depende da retomada da API do WhatsApp).
4. **Pessoa inteira** — a ficha junta aluno (cursos, progresso), pontos, fórum, encomendas
   e compras: um só retrato, do primeiro clique ao aluno formado.
5. **Robô no CRM** — o robô do painel lê a ficha, sugere o próximo passo e entrega de
   manhã "com quem falar hoje"; segmentos prontos para campanhas.
6. **Números** — receita por origem/campanha, quanto da venda recusada foi recuperada,
   tempo até fechar.

## Construção da primeira entrega

Fases 1 e 2 publicadas em `https://meshcraft.top/admin/crm/` e
`https://meshcraft.top/admin/contatos/`. Conferência de produção em 03/10/2026:
103 contatos e 195 acontecimentos; 53 oportunidades construídas a partir
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

As fases 3 a 6 continuam como próximas entregas. A conexão e o envio real do
WhatsApp precisam ser concluídos para integrar as conversas à ficha.
