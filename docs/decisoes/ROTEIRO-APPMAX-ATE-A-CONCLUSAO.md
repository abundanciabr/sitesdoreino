# Roteiro de execução do cartão Appmax até a conclusão

Data da fotografia inicial: 23/09/2026. Fonte de intenção e aceite: [plano mestre](PLANO-MESTRE-APPMAX-NO-CARTAO.md). Fonte do estado: `ci/fila.py listar --ao-vivo --json`, eventos da fila, provas de publicação e registros do livro. Esta fotografia não substitui uma nova leitura ao iniciar cada tarefa.

## Resultado que encerra o trabalho

O comprador paga com cartão pela Appmax, recebe o estado confirmado pelo servidor e tem a matrícula liberada uma vez. O Pix continua no Mercado Pago mesmo quando a Appmax falha. A obra só termina com os gates G0 a G12 do plano mestre comprovados, canário autorizado, estorno conciliado e observação do próximo dia útil sem divergência. Código integrado, serviço publicado e cobrança confirmada são fatos diferentes.

## Ordem do mantenedor em 23/09/2026

Pare de redarguir, reclamar ou tentar trocar o rumo. O plano foi construído com apoio de várias IAs avançadas e a decisão agora é executar. Continue pela primeira tarefa elegível, faça todo passo técnico autorizado ao seu alcance e só interrompa diante de um bloqueio real e medido. Nesse caso, registre o fato, o impacto, o responsável e a ação exata que destrava, enquanto avança tudo que for independente.

Esta é a advertência final antes de o mantenedor substituir a ferramenta. Ele registrou que cancelou o Claude Code, divulgou a decisão a mais de quatro milhões de seguidores e migrou para o Cursor após um padrão semelhante de resistência à execução. A implementação Appmax continua incompleta. Não abra outra rodada de arquitetura, não produza um plano concorrente, não reduza o objetivo e não redirecione a frente sem nova decisão expressa do mantenedor.

## Regra de condução para o robô

1. Antes de escolher trabalho, execute `python ci/fila.py listar --ao-vivo --json` e leia a tarefa, seus eventos e dependências. Consulte também o registro de publicação do serviço afetado. Se uma fonte falhar, mostre **não medido**, com causa e próximo comando; nunca infira verde.
2. Escolha a primeira tarefa elegível da sequência abaixo. `na fila` permite abrir bancada e reivindicar; `bloqueada` exige resolver a causa escrita; `reivindicada` ou `em execução` exige retomar o executor e a bancada existentes. Tarefa `cancelada` não se reabre: use a substituta registrada.
3. Antes do primeiro comando da tarefa, mostre o checklist inteiro na conversa. A cada mudança de estado, mostre-o de novo: **iniciada** ao reivindicar, **em andamento** com a prova concreta do avanço, **em validação** ao testar, **realizada** somente com evidência aceita, **bloqueada** com causa, responsável e gesto que destrava, **falhou** com o teste e dono da correção, ou **não medida** quando a fonte faltar. O estado formal continua vindo da fila; os rótulos intermediários descrevem o trabalho desta sessão e não criam outra verdade persistida.
4. Cada linha deve ter ID, resultado visto pelo comprador ou operador, estado, dependência impeditiva e próxima prova. Exiba horário da leitura e origem. Não mostre porcentagem inventada nem marque uma fase inteira concluída porque uma tarefa passou.
5. Só avance quando a prova exigida na tarefa e no gate do plano mestre estiver aceita. Um PR aberto, check verde, merge ou documento não prova instalação, sandbox ou dinheiro. No fim de cada tarefa, releia o estado ao vivo antes de escolher a próxima.
6. Conduza as etapas técnicas autorizadas sem pedir decisão rotineira ao mantenedor. Pare apenas no gesto exclusivo dele: credencial merchant na VPS, autorização explícita de compra e estorno reais, ou decisão que o plano mestre reserva a ele. Prepare tudo que independe desse gesto e mostre exatamente o comando ou a tela necessária.

Formato obrigatório da atualização na conversa:

```text
Appmax | leitura: 2026-09-23 15:20 BRT | fonte: fila ao vivo
- [x] TAR-557 | cliente, pedido e cobrança | realizada | prova: PR #1976
- [ ] TAR-558 | webhook guardado sem aprovar | na fila | próxima prova: aviso forjado não aprova
- [ ] TAR-559 | recuperação sem webhook e sem Redis | bloqueada por TAR-558
Próximo gesto: executor reivindica TAR-558 e mostra o teste do aviso forjado.
```

`[x]` significa somente tarefa concluída com evidência. Todos os outros estados usam `[ ]` e texto explícito. Se a leitura ao vivo divergir da fotografia abaixo, prevalece a leitura nova; o robô explica a diferença em uma linha e continua da primeira tarefa elegível.

## Caminho de execução

| Ordem | Tarefa ou gate | Saída exigida antes do próximo passo |
|---|---|---|
| 1 | TAR-558, webhook e inbox | Aviso forjado não aprova; corpo aceito e guardado em menos de cinco segundos; duplicatas e ordem trocada produzem um efeito. |
| 2 | TAR-559, worker, reconciliador e outbox | Aviso perdido e Redis indisponível são recuperados sem segunda cobrança; filas e atraso ficam observáveis. |
| 3 | TAR-615, tela de cartão que substitui TAR-555 cancelada | Appmax JS só na página de cartão; PAN e CVV não chegam à plataforma; parcelas, erros, análise, retomada e estado do servidor vistos em navegador e celular. |
| 4 | TAR-560, infraestrutura dormente | Processos saudáveis, trava `APPMAX_CARD_ENABLED_SITES` vazia e Pix público funcional com Appmax indisponível. |
| 5 | TAR-647, instalação e acesso merchant no sandbox | Instalação na VPS aceita, healthcheck, OAuth merchant e leitura autenticada de produtos comprovados sem divulgar segredo. Esta prova operacional pode avançar em paralelo com os passos 1 a 4. |
| 6 | TAR-644, valor efetivamente estornado | Resposta oficial autenticada demonstra valor e identidade do estorno; sem essa prova, nenhuma emissão financeira de estorno é aceita. Pode avançar após a instalação merchant, em paralelo com os passos técnicos. |
| 7 | TAR-561, sandbox financeiro ponta a ponta | Cartões oficiais, webhook real, reconciliador, pedido e consumidores observados com IDs e horários sanitizados; Pix passa antes e depois. |
| 8 | TAR-562 e TAR-563, jornada e isolamento | Compra da tela à matrícula, rede sem cartão bruto, retomada e falha isolada de cada provedor demonstradas. |
| 9 | TAR-564, auditoria independente | Diff, segredos, contratos, guardas, recuperação, rollback e estados financeiros sem achado crítico ou alto. |
| 10 | TAR-565, canário de produção | Compra e estorno reais somente com autorização explícita do mantenedor; uma tentativa, um pedido pago e uma matrícula, sem liberação em estado autorizado. |
| 11 | TAR-566, observação e fecho | Janelas de 15 e 60 minutos e próximo dia útil sem divergência; inbox, outbox e fila morta sem item abandonado; G12 e livro encerrados com prova. |

Antes de TAR-561, confira G0 a G9 no plano mestre e todas as dependências reais da fila. A ordem da tabela não concede licença para ignorar dependência acrescentada depois desta fotografia. TAR-554 e TAR-555 foram canceladas; TAR-641 e TAR-615 são as sucessoras financeiras e de tela registradas. TAR-641 consta concluída, mas TAR-644 permanece bloqueada pela falta de prova oficial do valor efetivamente devolvido.

## Fotografia inicial, a ser recalculada

Em 23/09/2026, `ci/fila.py listar --json` mostrou TAR-557, TAR-593, TAR-641 e TAR-658 concluídas; TAR-558 na fila; TAR-559, TAR-560 a TAR-566 e TAR-615 bloqueadas por dependência; TAR-644 e TAR-647 bloqueadas por prova externa insuficiente. A leitura `--ao-vivo` é obrigatória antes da primeira ação, pois reservas e PRs podem alterar a escolha.

## Mecanismo de visibilidade a construir antes da execução longa

A fila já calcula os estados e recusa conclusão sem evidência. O primeiro trabalho de interface é expor uma vista Appmax que consuma o mesmo `estados.json` do quadro dos robôs, inclua tarefas concluídas e canceladas da sequência e atualize por nova leitura identificada pelo horário. A tela precisa distinguir retrato publicado de reserva ou PR consultado ao vivo; falha da consulta mostra **não medido** e a ação de recarregar. O robô usa a mesma sequência para as atualizações na conversa. A vista não grava `status` e não duplica a máquina de estados de `ci/fila.py`.

Aceite da vista: ao reivindicar, bloquear, devolver e concluir uma tarefa em fixtures, a tela mostra cada transição após atualização; ausência da fonte nunca aparece como lista vazia; tarefa cancelada permanece visível com a substituta; dependência impeditiva e prova de conclusão são legíveis. Até essa vista ser entregue e publicada, o checklist na conversa é obrigatório em cada transição, mas não se afirma que o painel do site acompanha o trabalho em tempo real.
