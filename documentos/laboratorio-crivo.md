---
titulo: Laboratório Crivo | Guia de experiências
publico: true
ordem: 1000
---

# Experimente o Laboratório Crivo

Abra o [Laboratório Crivo](/quiz/laboratorio-crivo/?utm_source=laboratorio&utm_campaign=laboratorio-crivo&utm_content=foco) e a [observação dos registros](/quiz/laboratorio-crivo/observacao/) em duas abas do mesmo navegador. O Crivo atual continua separado, em seu endereço anterior. A entrada continua por link direto.

Faça primeiro estas três rodadas. Escolha a primeira alternativa nas três perguntas para receber **Escolha um projeto para começar**. Clique em **Refazer o quiz** e escolha a segunda alternativa nas três perguntas para receber **Proteja seu ritmo de execução**. Refaça mais uma vez e escolha a terceira alternativa nas três perguntas para receber **Feche e compartilhe sua entrega**. Nesse resultado, o botão abre a [oferta do curso de teste](/checkout/curso-teste/).

Use somente **laboratorio.crivo@exemplo.test** no e-mail. Nome e telefone são opcionais. Se quiser preencher o nome, use **Laboratório Crivo**; deixe o telefone vazio. Esse endereço é sintético e não recebe mensagens. Não use seu contato real. Os textos descrevem hábitos de projetos.

## O que está sendo comparado

Há três perguntas sobre escolher uma entrega, reservar tempo e encerrar uma rodada. Cada alternativa vale 0, 1 ou 2 pontos, na ordem em que aparece. Os pontos ficam no servidor. A soma vai de 0 a 6.

| Pontos | Resultado | Próximo passo |
| 0 a 1 | Escolha um projeto para começar | Exercício de foco neste guia |
| 2 a 4 | Proteja seu ritmo de execução | Exercício de ritmo neste guia |
| 5 a 6 | Feche e compartilhe sua entrega | Oferta existente do curso de teste |

As versões **original** e **conversa** contam a mesma história com redações diferentes. Cada uma tem peso 100. O sorteio usa uma nova rodada e permanece nela. Atualizar a página preserva o cookie da rodada; por isso preserva a versão. Pesos iguais dão a mesma chance, mas não obrigam duas pessoas seguidas a receberem versões diferentes. Não existe um parâmetro público para escolher a versão.

## Começar com origens diferentes

Abra cada link abaixo em uma sessão independente. Uma nova aba comum compartilha cookies e não cria uma rodada independente. Para comparar versões ou origens, use outro perfil do navegador, outro navegador ou uma nova sessão privada depois de fechar todas as janelas privadas anteriores.

- [Origem de foco](/quiz/laboratorio-crivo/?utm_source=laboratorio&utm_campaign=laboratorio-crivo&utm_content=foco)
- [Origem de ritmo](/quiz/laboratorio-crivo/?utm_source=laboratorio&utm_campaign=laboratorio-crivo&utm_content=ritmo)
- [Origem de entrega](/quiz/laboratorio-crivo/?utm_source=laboratorio&utm_campaign=laboratorio-crivo&utm_content=entrega)

A origem da primeira chegada fica na rodada. Abrir outro desses links na mesma rodada não troca a origem. **Refazer** preserva essa origem e cria outra rodada. Para trocar a origem, comece uma sessão independente.

## Como ler a observação

A [observação](/quiz/laboratorio-crivo/observacao/) usa o cookie deste navegador. Ela mostra a versão, a origem de demonstração reconhecida, as aberturas recebidas, a resposta registrada, a pontuação e as escolhas gravadas. Não mostra contato, identificadores de sessão nem dados de respostas de outras pessoas.

O relatório é calculado pela mesma consulta usada no comando operacional **funil**. Na conversão, cada rodada conta uma vez, mesmo que o formulário tenha sido aberto várias vezes. **Hesitação** significa mais de uma escolha na mesma pergunta. **Tempo médio** significa o intervalo da primeira visualização à primeira escolha; não mede o tempo até avançar. **Saída** significa que o formulário emitiu o evento de abandono. A mesma rodada pode sair e depois concluir, portanto saída não significa que a pessoa jamais voltou.

A coleta de cliques é recebida em segundo plano. Após uma experiência, espere até um minuto e recarregue a observação. Ausência de coleta aparece como ausência de registros, sem fingir que houve zero visitas.

A seção de eventos mostra apenas contagens da amostra sintética deste laboratório com as três origens acima. É uma amostra compartilhada. O evento atual não contém um vínculo direto com a resposta completa. Por isso a tela separa as contagens de eventos da resposta da sua rodada e não afirma que um evento específico pertence a ela. **Entregue** significa publicado pelo relay no canal de eventos; não é uma confirmação do serviço de contatos, do livro de números ou de uma compra.

## Experimento 1: os três diagnósticos

**O que fazer.** Faça as três rodadas descritas na abertura, usando Refazer entre elas. O formulário abre limpo a cada nova rodada.

**O que deve aparecer.** Primeiras alternativas somam 0, segundas somam 3 e terceiras somam 6. Os diagnósticos e os botões são diferentes. A versão pode mudar depois de Refazer.

**O que foi registrado.** Uma resposta completa por rodada, contendo escolhas, pontos, resultado, versão e origem, junto do evento de conclusão. A observação mostra a resposta da rodada atual.

**O que isso demonstra.** Pontuação no servidor, faixas, conteúdo próprio de resultado e idempotência da conclusão.

**Exercício de foco.** Escolha um único projeto. Escreva uma entrega que você consiga mostrar em uma sessão. Exemplo: uma página com uma proposta e um botão funcional.

**Exercício de ritmo.** Reserve uma sessão na semana. Escreva a ação que fará e o critério que encerra essa rodada. Pare os ajustes quando o critério estiver atendido.

## Experimento 2: as fronteiras entre resultados

**O que fazer.** Use Refazer entre as combinações abaixo. Os números indicam a posição da alternativa em cada uma das três perguntas.

| Alternativas | Pontos | Resultado esperado |
| 2, 1, 1 | 1 | Foco |
| 3, 1, 1 | 2 | Ritmo |
| 3, 2, 2 | 4 | Ritmo |
| 3, 3, 2 | 5 | Entrega |

**O que deve aparecer.** Mudar de 1 para 2 pontos troca foco por ritmo. Mudar de 4 para 5 troca ritmo por entrega. Os limites pertencem à faixa que a tabela mostra.

**O que foi registrado.** Uma resposta por rodada com a soma e a chave do resultado.

**O que isso demonstra.** Intervalos inclusivos sem lacuna de 0 a 6. A mesma prova é executada nas duas versões no banco de teste.

## Experimento 3: duas versões e permanência

**O que fazer.** Antes de responder, abra a observação e veja a versão. Atualize o quiz. Depois abra uma sessão independente pelo mesmo link. Repita em novas sessões independentes se aparecer a mesma versão.

**O que deve aparecer.** A atualização mantém os textos e a versão. Uma sessão independente pode receber a outra versão. Não há garantia de alternância.

**O que foi registrado.** Versão e origem na rodada, nos eventos de visita e escolhas e na resposta final.

**O que isso demonstra.** Sorteio por peso e continuidade por cookie. O cookie assinado dura até sete dias; apagá-lo ou deixá-lo expirar começa outra rodada.

## Experimento 4: origens de demonstração

**O que fazer.** Abra foco em uma sessão independente e ritmo em outra. Confira cada observação no mesmo navegador da rodada. Abra o link de entrega na rodada de foco já iniciada.

**O que deve aparecer.** Cada sessão independente conserva sua primeira origem. O terceiro link não muda a origem da rodada de foco.

**O que foi registrado.** A origem de chegada fica no cookie, na resposta e nos eventos. A tela mostra somente os nomes de demonstração reconhecidos.

**O que isso demonstra.** Preservação de origem, sem confundir atualização de endereço com uma nova campanha.

## Experimento 5: escolha obrigatória e hesitação

**O que fazer.** Em uma rodada nova, clique em Continuar sem escolher. Depois escolha uma alternativa e mude para outra na mesma pergunta antes de continuar.

**O que deve aparecer.** Sem escolha, a pergunta continua na tela e pede uma resposta. A mudança de escolha deixa somente a última marcada.

**O que foi registrado.** A pergunta foi vista e duas escolhas foram emitidas. Depois da coleta, a observação mostra hesitação 1 nessa pergunta e o tempo até a primeira escolha. A resposta final guarda somente a escolha final.

**O que isso demonstra.** Validação por etapa e diferença entre histórico de cliques e resposta completa.

## Experimento 6: sair e voltar

**O que fazer.** Abra antes a observação em outra aba. Responda a primeira pergunta, avance e feche a aba do quiz. Aguarde a coleta e atualize a observação. Volte ao quiz sem apagar cookies.

**O que deve aparecer.** A observação registra uma saída na pergunta em que você estava. Sem conclusão, o formulário volta ao começo; ele não salva um rascunho entre visitas.

**O que foi registrado.** Evento de abandono com pergunta, versão e origem. Ainda não há resposta completa.

**O que isso demonstra.** Medição de saída. Fechamento abrupto, perda de rede ou bloqueio da coleta podem impedir o evento; o registro de abandono não é garantido em toda saída.

## Experimento 7: contato inválido e correção

**O que fazer.** Responda as perguntas. No contato, use **endereco-invalido** e tente concluir. Corrija para o contato sintético da abertura. Nome e telefone podem ficar vazios.

**O que deve aparecer.** A tela pede um e-mail válido. As escolhas e o contato preenchido permanecem. Depois de corrigir, você chega ao resultado sem responder tudo de novo. Limites são 254 caracteres para e-mail, 200 para nome e 32 para telefone.

**O que foi registrado.** Entrada inválida não grava resposta completa nem evento de conclusão. O envio válido grava uma resposta e um evento. Erros de contato acima do limite também foram exercitados diretamente contra o servidor no teste controlado.

**O que isso demonstra.** E-mail obrigatório, contato opcional, validação no servidor e preservação durante correção. A validação HTML do navegador pode recusar o e-mail antes de enviá-lo ao servidor.

## Experimento 8: concluir, fechar e retornar

**O que fazer.** Conclua uma rodada. Feche a aba e reabra o link do laboratório no mesmo navegador.

**O que deve aparecer.** O resultado anterior abre automaticamente enquanto o cookie válido permanecer. A observação continua mostrando uma resposta completa nessa rodada.

**O que foi registrado.** Nenhuma conclusão adicional é criada só por retornar.

**O que isso demonstra.** Retorno ao resultado e separação entre abrir a página e concluir novamente.

## Experimento 9: Refazer e resultado antigo

**O que fazer.** Mantenha o resultado antigo aberto numa aba. Em outra aba, clique em Refazer. Confira o formulário vazio, faça outra rodada e volte à aba do resultado antigo.

**O que deve aparecer.** Nova rodada, formulário limpo e origem preservada. O resultado antigo continua acessível pela aba anterior. A observação passa a acompanhar a rodada nova.

**O que foi registrado.** A resposta antiga permanece e a nova conclusão cria outra resposta. A observação não oferece um histórico de todas as rodadas do navegador.

**O que isso demonstra.** Refazer cria outra rodada, sem apagar a anterior. Preservar resultado não é preservar rascunho.

## Experimento 10: duplicação e duas abas

**O que fazer.** Abra duas abas do formulário antes de concluir. Preencha ambas com o contato sintético e conclua a primeira. Conclua a segunda sem clicar em Refazer.

**O que deve aparecer.** As abas compartilham a rodada. A segunda conclusão volta ao primeiro resultado, mesmo que as escolhas fossem diferentes. Para outra resposta, clique em Refazer.

**O que foi registrado.** Uma resposta completa e um evento de conclusão para essa rodada. A contagem de visitas pode ter mais de uma abertura, mas a conversão continua uma.

**O que isso demonstra.** Proteção contra conclusão duplicada. Durante envio, o botão fica desativado e aparece **Calculando seu resultado…**. Lentidão artificial é demonstrada somente no navegador de teste.

## Experimento 11: seguir o botão

**O que fazer.** Nos resultados de foco e ritmo, siga o botão para este guia e faça o exercício correspondente. No resultado de entrega, siga o botão para a oferta do curso de teste.

**O que deve aparecer.** O destino abre. Na oferta, confira que o curso de teste está disponível. Pare antes de contratar ou pagar.

**O que foi registrado.** O quiz já registrou a conclusão. Ele não emite um evento próprio para clique no botão de resultado nem confirma compra ou entrega de curso.

**O que isso demonstra.** Dois destinos funcionais e limite da medição do quiz. Chegar à compra não é comprar, contato não é cliente e conclusão não é receita.

## Erros só no ambiente controlado

Não altere dados nem provoque falhas no site para reproduzir estes casos. Os testes usam outro banco e um Redis isolado.

| Cenário | Comportamento atual | Limite |
| Pergunta sem escolha | Etapa não avança; POST incompleto responde 422 e pede todas as perguntas | Não grava resposta completa |
| E-mail inválido ou contato acima do limite | 422, mensagem de correção e valores preservados | Navegador também tem validação própria |
| Envio duplicado e duas abas | Uma resposta e um evento; volta ao primeiro resultado | Para nova resposta, Refazer |
| Opção de outra pergunta ou texto inválido no identificador | 404 e nenhuma resposta nova | Não explica a adulteração em detalhes ao visitante |
| Cookie inválido ou expirado | Formulário abre uma rodada nova; telemetria sem cookie válido é recusada | Não retoma rascunho perdido |
| Resultado inexistente | 404 | Não recria resultado |
| Ausência de faixa | Recebemos suas respostas; permite Refazer | Sem diagnóstico específico, resultado interno sem_faixa |
| Faixa sem botão | Diagnóstico sem botão de destino; permite Refazer | Estado admitido pelo modelo |
| Nenhuma versão com peso positivo e ativa | 404 | Não há versão substituta automática |
| Falha na publicação do evento | Resposta e evento permanecem; evento fica pendente | Relay tenta novamente, em tarefa periódica |
| Repetição do semeador | Mesmas linhas, pesos e conteúdo preservados | Não sobrescreve edição posterior do mantenedor |
| Outro site | Não lê resultado ou observação da rodada deste site | Cadastro local precisa corresponder ao catálogo |

## Inventário e provas

A tabela distingue a experiência oferecida pelo site, a prova do banco de teste e as capacidades ausentes. A publicação e a conferência final são registradas no fecho da entrega; uma preparação local sozinha não é prova de publicação.

| Recurso | Como experimentar | Resultado esperado | Resultado observado e evidência | Estado |
| Etapas, escolha obrigatória e score no servidor | Experimentos 1 e 5 | Três perguntas e soma de 0 a 6 | Testes controlados de fronteira e guarda de score; navegador e observação da rodada | demonstrado em ambiente controlado |
| Intervalos e fronteiras | Experimento 2 | 1 foco, 2 ritmo, 4 ritmo, 5 entrega | Teste controlado nas duas versões; pontuação observável na tela de registros | demonstrado em ambiente controlado |
| Texto e botão de cada resultado | Experimentos 1 e 11 | Três diagnósticos, dois destinos | Conteúdo e destinos verificados nos testes de fronteira e no navegador | demonstrado em ambiente controlado |
| E-mail obrigatório, nome e telefone opcionais | Experimento 7 | Sem e-mail não conclui; opcionais vazios concluem | Guardas de contato do quiz e percurso do navegador | demonstrado em ambiente controlado |
| Correção preservando escolhas | Experimento 7 | 422 preserva respostas e contato | Guarda de e-mail inválido e E2E do Crivo | demonstrado em ambiente controlado |
| Envio lento e botão desativado | Experimento 10 | Aviso de cálculo e envio desativado | Navegador controlado com atraso no POST; sem lentidão provocada no site | demonstrado em ambiente controlado |
| Retorno ao resultado | Experimento 8 | Resultado anterior | Guarda de retomada e navegador | demonstrado em ambiente controlado |
| Refazer | Experimento 9 | Nova rodada, vazia, mesma origem | Guarda de duas abas e Refazer; navegador | demonstrado em ambiente controlado |
| Versões e pesos | Experimento 3 | Duas versões, peso 100 cada, corte estável | Guarda de corte por peso e semeador idempotente | demonstrado em ambiente controlado |
| Origem na rodada, resposta e evento | Experimento 4 | Origem da chegada permanece | Guardas de sessão, UTM, telemetria e fronteira | demonstrado em ambiente controlado |
| Visita, pergunta, escolha e saída | Experimentos 5 e 6 | Eventos recebidos em segundo plano | Testes de ingestão, drenagem e relatório; tela da rodada | demonstrado em ambiente controlado |
| Conclusão, abandono, hesitação e tempo | Observação da rodada | Contas calculadas por versão e origem | Mesmo montar_funil; teste usa hesitação 1 e tempo 3,0 segundos | demonstrado em ambiente controlado |
| Resposta e conclusão na mesma transação | Concluir | Uma resposta junto de um evento | Guarda transacional da outbox | demonstrado em ambiente controlado |
| Entrega posterior e recuperação | Não provoque no site | Pendente passa a entregue após recuperar | Guardas do relay com Redis real e falha controlada | demonstrado em ambiente controlado |
| Formulário, sessão, score, resultado e sites | Erros controlados | CSRF recusa, cookie assinado, validação no servidor e isolamento | Guardas da superfície pública, score, observação e sites | demonstrado em ambiente controlado |
| Publicação e repetição do semeador | Abertura e teste controlado | Quiz separado, sem duplicação | Migração usa o mesmo semeador; repetição medida com Crivo e edição preservados | demonstrado em ambiente controlado |
| Dados pessoais no livro de números | Leia a seção abaixo | Tratamento atual explícito | Contrato e código de descarte consultados; nenhuma alteração nesta entrega | demonstrado em ambiente controlado |
| Sem JavaScript | Desabilite scripts no seu navegador de teste | Formulário completo com todas as perguntas | HTML existente; o modo por etapas usa JavaScript | demonstrado em ambiente controlado |
| Limites de UTM e telemetria | Teste controlado | UTM limitada, corpo e tipos validados | Código atual limita 8 campos de origem, valor 200, corpo 4096 bytes e elemento 120 | demonstrado em ambiente controlado |
| Confirmação do contato no serviço de contatos | Não disponível nesta observação | Exigiria confirmação da célula receptora | Relay entregue não comprova criação de contato na receptora | não disponível |
| Vínculo individual entre evento e resposta | Não disponível | Exigiria identificador comum | O payload atual não guarda esse vínculo; contagens são separadas | não disponível |
| Clique do botão como evento do quiz | Não disponível | Exigiria recurso de medição próprio | O quiz emite somente visita, pergunta, escolha, saída e conclusão | não disponível |
| Rascunho entre visitas | Não disponível | Exigiria persistência parcial | Correção do mesmo POST preserva campos; reabrir sem conclusão começa o formulário | não disponível |
| Pagamento e entrega de curso | [Ensaio existente do sandbox](https://github.com/abundanciabr/sitesdoreino/actions/runs/36327860461) | Aprovação de teste, evento e matrícula únicos | Ensaio aprovado no computador e celular; prova independente desta rodada do quiz | demonstrado em ambiente controlado |

Os testes novos do laboratório são **test_laboratorio.py**. As proteções existentes estão nas suítes de superfície pública, pontuação e outbox, telemetria, Refazer e botão por faixa. O percurso do laboratório usa navegador real em 390 × 844 e 1280 × 800, com teclado, três diagnósticos, retorno e nova rodada. Os números da observação vêm do banco; o guia não mantém uma cópia manual de números de produção.

## Tratamento atual dos contatos

O quiz guarda e-mail e, se preenchidos, nome e telefone na resposta e no evento de conclusão. O contrato congelado continua exigindo e-mail nesse evento. O relay publica esse corpo no canal de eventos para as células receptoras.

Na revisão consultada, o consumidor do livro de números descarta o bloco de contato antes de guardar os fatos. Há migrações específicas para retirar contatos dos fatos antigos e dos eventos recusados antigos. A fila registra essas duas limpezas como concluídas. Isso não remove contato do banco do quiz nem do canal de transporte e não muda o contrato. A pendência histórica de contato no contrato permanece separada. Esta entrega não executa expurgo, não altera contrato e não reabre decisões sobre dados pessoais.

## Pagamento e entrega

O percurso deste laboratório chega à oferta existente do curso de teste. O [ensaio existente do sandbox de pagamento](https://github.com/abundanciabr/sitesdoreino/actions/runs/36327860461), executado em 27/09/2026, comprovou no computador e no celular a aprovação com cartão de teste, um evento de aprovação, pedido pago e matrícula única. O ensaio também passou nos cenários de recusa e recuperação previstos na matriz do provedor.

Essa prova usa compras sintéticas independentes: não liga a matrícula a uma resposta deste laboratório. O quiz não oferece essa atribuição. Não foi feita cobrança real nesta entrega. Nenhuma conclusão do quiz ou visita à oferta é contabilizada como receita.
