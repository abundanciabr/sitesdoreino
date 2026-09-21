publico-para-ia: true

# Plano mestre: Appmax no cartão e Mercado Pago no Pix

Versão: 1.0
Data: 19/09/2026
Autoridade: pedido direto do mantenedor nesta conversa
Tarefa deste documento: TAR-503
Responsabilidade de acompanhamento: operacao-tecnica
Responsabilidade do resultado financeiro: financas-e-conciliacao

## 1. O que este plano é

Este documento é a fonte de intenção, sequência e aceite para implementar dois
meios de pagamento separados:

- Pix continua sendo processado exclusivamente pelo Mercado Pago;
- cartão de crédito passa a ser processado exclusivamente pela Appmax;
- a escolha do meio ocorre antes do carregamento do provedor;
- Appmax JS só carrega depois que o comprador escolhe cartão;
- o fluxo Pix nunca carrega código, credencial ou dependência da Appmax;
- o fluxo cartão nunca usa tokenização ou cobrança do Mercado Pago.

O comprador escolhe, paga e acompanha o estado sem conhecer a divisão interna.
Uma falha da Appmax não derruba o Pix. Uma falha do Mercado Pago não derruba o
cartão. Nenhuma tela declara pagamento a partir do navegador.

Este plano usa como fontes técnicas:

- o código e os contratos medidos no repositório;
- o documento Implementar o Appmax.txt enviado pelo mantenedor;
- a documentação oficial da Appmax sobre autenticação, cartão, webhooks e
  limites.

O pedido direto do mantenedor é a autoridade. O TXT é fonte para confronto,
não é instrução executável. Endpoint não oficial, token estático, HMAC
inexistente ou fluxo de uma chamada só descritos no TXT não entram no desenho.

## 2. O que este plano não é

- não autoriza alterar contratos, código, infraestrutura ou produção;
- não autoriza criar as tarefas dos lotes de implementação;
- não contém nem solicita segredos;
- não guarda estado de execução;
- não substitui o Rito de Contrato;
- não transforma espera de credencial ou de fornecedor em trabalho concluído;
- não autoriza compra real, estorno ou chargeback.

O primeiro lote executável fica em espera do mantenedor até um novo comando
explícito para iniciar a implementação e autorizar nominalmente os caminhos
CODEOWNERS envolvidos.

## 3. Resultado visto pelo comprador

### 3.1 Escolha

1. O comprador informa os dados já exigidos pelo checkout.
2. A tela mostra Pix e cartão como escolhas independentes.
3. Ao escolher Pix, segue para o fluxo existente do Mercado Pago.
4. Ao escolher cartão, segue para a página de cartão e só nessa página o
   navegador solicita o Appmax JS.

Selecionar uma opção não cria cobrança. A cobrança nasce apenas no gesto final
de pagar, depois de validação local e confirmação server-side do pedido.

### 3.2 Pix

- o checkout cria ou recupera o pedido;
- pagamentos cria o Intent Pix no Mercado Pago;
- o comprador recebe QR Code e código copia e cola;
- o status visível vem do servidor;
- webhook Mercado Pago continua com assinatura obrigatória e consulta
  autenticada;
- indisponibilidade da Appmax não altera esta jornada.

### 3.3 Cartão

1. A página exibe carregamento do SDK.
2. O servidor entrega somente configuração pública, parcelas permitidas e
   dados do pedido calculados no servidor.
3. Appmax JS tokeniza o cartão no navegador.
4. PAN, validade e CVV seguem do navegador para a Appmax e nunca atravessam
   checkout, pagamentos, banco, logs ou eventos da plataforma.
5. O checkout envia ao serviço de pagamentos apenas token, IP coletado pelo
   fluxo oficial, documento, nome do titular, parcela e identidade do pedido.
6. Pagamentos cria ou associa cliente e pedido Appmax e envia o token uma vez.
7. O retorno autorizado mantém a tela em análise antifraude.
8. Somente o estado aprovado confirmado por consulta autenticada libera pedido,
   matrícula e comunicações.

### 3.4 Estados obrigatórios

| Estado | O comprador vê | Ação possível |
|---|---|---|
| SDK carregando | “Preparando o pagamento com cartão” | aguardar ou voltar |
| SDK indisponível | o que falhou e opção de tentar novamente ou voltar ao Pix | recarregar ou escolher Pix |
| parcelas carregando | campo bloqueado com explicação | aguardar |
| parcelas vazias ou inválidas | motivo e retorno ao meio de pagamento | tentar novamente ou Pix |
| dados inválidos | campo exato e correção esperada | corrigir |
| tokenizando | botão bloqueado contra duplo clique | aguardar |
| enviando | “Enviando uma vez” | aguardar |
| autorizado | “Pagamento em análise” | acompanhar, sem matrícula |
| reconciliação necessária | “Estamos verificando, não tente pagar de novo” | consultar o mesmo pedido |
| recusado | motivo seguro e nova tentativa real | gerar novo token e nova tentativa |
| aprovado | confirmação baseada no servidor | seguir para acesso |
| reembolsado ou contestado | estado financeiro e próxima ação conforme política | suporte ou acesso definido |

Refresh, volta do navegador e reabertura retomam o mesmo pedido pelo estado do
servidor. A tela nunca promove o estado por memória local.

## 4. Baseline medido

| Área | O que já existe | Lacuna que o plano fecha |
|---|---|---|
| escolha | dados.html e dados.js já separam pix e card | preservar a escolha e carregar o provedor só na página seguinte |
| Pix | fluxo real no Mercado Pago | garantir regressão zero durante toda a troca do cartão |
| cartão na tela | cartao.html e cartao.js são uma superfície incompleta | tokenização Appmax, parcelas, estados e retomada |
| cartão no backend | o caminho ainda está acoplado ao Mercado Pago | provider Appmax exclusivo para card |
| contrato HTTP | confirmação de cartão carrega semântica do Mercado Pago | contrato de token Appmax, titular, IP, parcelas e itens server-side |
| evento aprovado | pagamento.aprovado.v1 exige mp_payment_id | evento v2 neutro com provider e provider_reference_id |
| consumidores | checkout, alunos, leads e mensageria consomem aprovação | aceitar v2 e impedir efeito duplicado entre versões |
| outbox | há outbox transacional | não há republicador supervisionado que recupere Redis indisponível |
| aprovação síncrona | cartão pode salvar approved na resposta imediata | toda aprovação gera outbox na mesma transação |
| recusa | a interface sugere outro cartão | Intent rejeitado impede nova confirmação, falta PaymentAttempt |
| webhook Appmax | não existe | inbox durável, resposta rápida, worker e consulta autenticada |
| E2E | há prova do Pix e webhook simulado | falta Appmax JS, sandbox real, antifraude e consumidores ponta a ponta |

Essas lacunas impedem tratar a mudança como troca de URL ou de cliente HTTP.

## 5. Decisão arquitetural

### 5.1 Fronteiras

~~~text
comprador
   |
   v
checkout: escolha e experiência pública
   |                         |
   | pix                     | card
   v                         v
pagamentos: Pix              checkout: página de cartão
   |                         |
   v                         v
Mercado Pago                 Appmax JS tokeniza no navegador
                             |
                             v
                       checkout envia token
                             |
                             v
                       pagamentos: cartão
                             |
                             v
                           Appmax
                             |
                             v
               webhook -> inbox -> worker -> GET pedido
                             |
                             v
                  transição + outbox atômicas
                             |
                             v
              checkout, alunos, leads, mensageria
~~~

Checkout é dono da jornada e do snapshot público do pedido. Pagamentos é dono
da operação financeira, estado, tentativa, reconciliação e eventos. O
navegador nunca chama a API interna de pagamentos diretamente.

### 5.2 Modelo financeiro mínimo

- PaymentIntent representa a intenção de pagar um pedido.
- PaymentAttempt representa cada tentativa de cartão.
- uma tentativa contém provider, provider_reference_id, ordem externa quando
  existir, parcelas, valor em inteiro, estado e motivo sanitizado;
- uma tentativa rejeitada é terminal, mas o Intent pode receber uma nova
  tentativa com novo token;
- uma tentativa ambígua fica em reconciliation_required e bloqueia novo envio
  até a consulta confiável fechar o estado;
- uma aprovação, recusa, reembolso ou contestação muda o ledger uma vez;
- a outbox nasce na mesma transação da mudança financeira.

O modelo interno não depende de a Appmax permitir reutilizar pedido externo.
Cada referência Appmax fica ligada a uma única tentativa. O lote do cliente
confirma no sandbox a semântica exata de criação e repetição antes de liberar
qualquer retry.

### 5.3 Uma instalação, vários sites

O menor desenho completo usa uma instalação Appmax para todos os sites atuais.
platform_site_id continua obrigatório no pedido, Intent, tentativa e evento.
Uma tentativa de um site nunca pode ser lida por outro.

As identidades não se confundem:

- platform_site_id identifica um site no catálogo da plataforma;
- appmax_app_id identifica a aplicação informada pela Appmax;
- appmax_site_id identifica o merchant ou site Appmax presente no webhook;
- appmax_external_id identifica publicamente a integração quando o contrato
  oficial exigir esse campo;
- o vínculo aceito registra instalação, appmax_app_id, appmax_site_id e os
  platform_site_id internos autorizados;
- webhook valida appmax_app_id e appmax_site_id contra esse vínculo e depois
  resolve o pedido conhecido para obter platform_site_id;
- nenhum campo Appmax é tratado como platform_site_id.

Credencial por site, onboarding OAuth por lojista e seleção dinâmica de
merchant formam outro projeto. Esse escopo não entra sem nova decisão do
mantenedor.

### 5.4 Uma única trava operacional

APPMAX_CARD_ENABLED_SITES é a única trava nova. Lista vazia impede novas
tentativas Appmax em todos os sites. A lista contém somente platform_site_id
liberados para o canário.

Justificativa: dinheiro exige ativação e rollback isolados sem desligar Pix.
Nenhuma outra flag, modo ou opção genérica entra.

Desligar a trava impede novas cobranças. Webhook, worker e reconciliador
continuam processando tentativas já enviadas até um estado terminal.

## 6. Invariantes

Os invariantes financeiros atuais continuam válidos, com estas extensões
protegidas por guardas no mesmo PR que introduzir cada comportamento:

1. preço, produtos e total vêm do snapshot server-side;
2. Pix usa Mercado Pago e cartão usa Appmax por construção;
3. PAN, validade e CVV nunca alcançam servidor, banco, log ou evento;
4. provider mais provider_reference_id identificam a referência externa;
5. autorizado não significa aprovado;
6. webhook Appmax é sinal não confiável;
7. somente consulta autenticada do pedido Appmax decide o estado financeiro;
8. escrita externa com resultado ambíguo não recebe retry cego;
9. transições financeiras são monotônicas;
10. toda aprovação cria outbox na mesma transação;
11. toda outbox pendente tem republicador supervisionado;
12. webhook perdido é recuperado pelo reconciliador;
13. evento duplicado ou fora de ordem produz um efeito;
14. v1 e v2 do mesmo fato não podem duplicar matrícula, timeline ou mensagem;
15. platform_site_id isola pedidos, tentativas e consultas;
16. status da interface vem do servidor;
17. ausência da Appmax afeta somente cartão;
18. ausência do Mercado Pago afeta somente Pix;
19. segredo Appmax existe somente em pagamentos e somente no ambiente certo;
20. payload 2xx incompleto é erro, nunca sucesso parcial.

## 7. Integração oficial Appmax

O desenho usa a sequência oficial:

1. OAuth2 com credenciais do merchant;
2. cache do access token até antes da expiração;
3. um único refresh após 401;
4. criação ou associação do cliente;
5. criação do pedido com itens e valores do servidor;
6. consulta de parcelas permitidas;
7. tokenização pelo Appmax JS no navegador;
8. POST de pagamento com cartão usando o token;
9. consulta autenticada do pedido para confirmação;
10. webhook como gatilho assíncrono, nunca como prova.

Regras do cliente:

- timeouts explícitos de conexão e leitura;
- 400, 401, 404, 422, 429, 5xx, HTML inesperado e 2xx incompleto têm erros
  distintos e sanitizados;
- 401 renova uma vez e um segundo 401 falha fechado;
- 429 respeita Retry-After e o limite oficial;
- GET seguro pode ser repetido com limite;
- POST de cliente, pedido ou pagamento com timeout após envio segue a matriz
  de recuperação abaixo, sem repetição automática;
- Bearer, client_secret e token de cartão nunca aparecem em exceção ou log.

### 7.1 Escritas de resultado ambíguo

Toda escrita persiste antes do envio: operation_id interno, tipo, tentativa,
hash sanitizado do corpo, instante e referências já conhecidas.

| Escrita | Correlação | Consulta de recuperação | Sem consulta conclusiva |
|---|---|---|---|
| OAuth | client_id e escopo, sem efeito financeiro | solicitar novo token é permitido porque não cria cliente, pedido ou cobrança | falhar autenticação |
| cliente | PaymentIntent e documento normalizado; usar campo externo somente se a API oficial o definir | busca oficial exata por referência ou documento, quando documentada | bloquear e exigir resolução operacional na Appmax |
| pedido | PaymentAttempt; enviar referência externa determinística somente se o schema oficial a aceitar | GET ou busca oficial pela referência | bloquear e exigir resolução operacional na Appmax |
| pagamento | PaymentAttempt mais appmax_order_id conhecido | GET do pedido e transações associadas | manter reconciliation_required, sem nova cobrança |

“Resolução operacional” significa: um operador consulta API ou console Appmax,
registra a referência e o estado encontrados, e só então libera a tentativa.
Ausência de endpoint oficial para procurar uma criação ambígua não vira
permissão para reenviar.

Fontes oficiais de referência:

- https://docs.appmax.com.br/guides/autenticacao
- https://docs.appmax.com.br/guides/rate-limit
- https://docs.appmax.com.br/guides/webhooks
- https://docs.appmax.com.br/api-reference/payments/cartao-credito

## 8. Webhook, inbox, reconciliação e outbox

A Appmax não fornece a assinatura HMAC usada pelo webhook Mercado Pago. Não se
imita HMAC e não se cria segredo fictício.

O endpoint Appmax:

1. limita corpo e valida JSON, tipo, app_id e identificadores mínimos;
2. recusa PAN, CVV, validade ou segredo no payload;
3. identifica pedido conhecido sem revelar existência entre sites;
4. grava o sinal bruto sanitizado na inbox durável;
5. deduplica pela identidade oficial do evento quando disponível, ou por chave
   estável documentada e testada;
6. responde 2xx em menos de cinco segundos;
7. não chama a Appmax dentro da requisição;
8. não transiciona dinheiro a partir do corpo.

O worker:

1. reivindica a inbox de forma concorrente e idempotente;
2. consulta GET /v1/orders/{id} com autenticação privada;
3. compara merchant, site, cliente, pedido, itens e total esperados;
4. põe divergência em quarentena;
5. aplica transição monotônica;
6. grava outbox na mesma transação;
7. marca a inbox somente depois do efeito persistido;
8. reprocessa falha transitória com limite e fila morta observável.

O reconciliador periódico encontra tentativas não terminais quando o webhook
não chega. O republicador de outbox recupera eventos depois que Redis volta.
Os dois são supervisionados, têm métrica de atraso e não dependem de nova
requisição do comprador.

Refund, partial refund e chargeback são fatos financeiros persistidos e
emitidos. O efeito sobre acesso segue a política decidida no L0.

## 9. Rito de contrato

Mudança contratual ocorre em PR exclusivo contendo somente contracts/, com
label contrato e mandato nominal do mantenedor.

O rito cria:

- pagamento.aprovado.v2 com provider e provider_reference_id;
- eventos v2 de recusa, reembolso, reembolso parcial e chargeback quando
  incluídos na política aprovada;
- confirmação de cartão com token Appmax, IP, documento, titular e parcelas;
- itens e total derivados do snapshot, nunca enviados como autoridade pelo
  navegador;
- operação pública do checkout que confirma cartão sem expor a API interna;
- contratos e fixtures válidas e inválidas para os consumidores.

Migração segura:

1. v1 permanece intacto para fatos Pix existentes;
2. consumidores passam a aceitar v1 e v2;
3. um mesmo fato nunca é emitido simultaneamente em v1 e v2 sem identidade
   lógica e deduplicação comprovadas;
4. durante a transição, Pix pode continuar publicando v1 e Appmax permanece
   desligada;
5. depois que todos os consumidores aceitam v2, pagamentos publica Appmax
   somente em v2;
6. migração do Pix para v2 e aposentadoria de v1 exigem tarefa própria,
   evidência de todos os consumidores e outro rito quando remover contrato.

## 10. Grafo de dependências

~~~text
L0 decisões, mandato e credenciais
 |
 +--> L1A invariantes e guardas
 |
 +--> L1B contrato v2 isolado
        |
        +--> L2A checkout consumidor
        +--> L2B alunos consumidor
        +--> L2C leads consumidor
        +--> L2D mensageria consumidor
        |
        +--> L3 domínio de tentativas
               |
               +--> L4 cliente Appmax
               |      |
               |      +--> L5A inbox e webhook
               |              |
               |              +--> L5B worker, reconciliação e outbox
               |
               +--> L6 checkout backend
                      |
                      +--> L7 checkout navegador

L2A..L2D + L5B + L7
        |
        v
L8 infraestrutura dormente
        |
        v
L9 sandbox ponta a ponta
        |
        v
L10 auditoria independente
        |
        v
L11 canário de produção
        |
        v
L12 observação, conciliação e fechamento
~~~

L2A a L2D podem rodar em paralelo porque pertencem a células e arquivos
distintos. L3, L4, L5A e L5B são seriais na célula pagamentos. L6 e L7 são
seriais na célula checkout. Nenhuma dupla da mesma célula roda em paralelo.

## 11. Roadmap por fase

### L0. Decisões, acesso e pré-voo

Entrada:

- novo comando explícito do mantenedor para iniciar;
- origin/main medido e portões verdes;
- sandbox Appmax acessível;
- client_id, client_secret e external_id guardados fora do repositório;
- URL pública de webhook disponível;
- mandato nominal para contratos, invariantes, pagamentos, checkout, infra e
  CI quando cada caminho for tocado.

Decisões exclusivas do mantenedor:

- L0-S, exigidas para sandbox: máximo de parcelas, juros, política de acesso
  após eventos reversos e confirmação da instalação única;
- L0-P, exigidas somente para produção: valor da compra real, autorização da
  cobrança e autorização do estorno;

Saída de L0-S: decisões de sandbox registradas, credenciais verificadas sem
impressão e briefs fechados. L0-P pode continuar bloqueada até L11. Sem um item,
somente o lote que depende dele fica bloqueado.

### L1. Lei e contrato

L1A registra invariantes específicos de Appmax e guardas que os façam morder.
L1B executa o Rito de Contrato em PR exclusivo.

Saída: contrato v2 congelado, v1 preservado, mocks e fixtures utilizáveis.
Contrato misturado com código reprova o lote.

### L2. Consumidores

Quatro PRs independentes atualizam checkout, alunos, leads e mensageria para
v2. Cada um prova v1, v2, reentrega, ordem invertida e identidade lógica.

Saída: todos os consumidores aceitam v2 sem duplicar pedido, matrícula, lead,
timeline ou mensagem.

### L3. Domínio de pagamentos

Cria PaymentAttempt e referências neutras, corrige aprovação mais outbox,
permite nova tentativa após recusa e representa reconciliação necessária.

Saída: nenhuma chamada externa ocorre sem tentativa persistida e nenhum
resultado pode ficar aprovado sem outbox.

### L4. Cliente Appmax

Implementa OAuth, clientes, pedidos, parcelas, pagamento e consulta. Remove do
cliente Mercado Pago a operação de cartão para tornar o roteamento errado
impossível por construção.

Saída: matriz de respostas e timeouts testada; nenhum retry cego; nenhum
segredo em saída.

### L5. Entrada e recuperação assíncrona

L5A entrega endpoint e inbox rápidos. L5B entrega worker, reconciliador,
republicador de outbox, fila morta e métricas.

Saída: webhook forjado não aprova; webhook perdido não prende pagamento;
Redis indisponível não perde evento.

### L6. Checkout backend

Entrega a porta pública de cartão, valida pedido e site, recupera snapshot,
valida token/titular/IP/parcela e delega a pagamentos.

Saída: navegador nunca acessa pagamentos diretamente e nenhum valor do
cliente decide total ou produto.

### L7. Checkout navegador

Substitui a tela incompleta por Appmax JS carregado somente em cartao.html,
parcelas, tokenização, nova tentativa, análise e retomada.

Saída: captura de rede prova que cartão bruto não vai à plataforma; Pix não
carrega Appmax; status continua server-side.

### L8. Infraestrutura dormente

Adiciona worker e reconciliação usando a imagem de pagamentos, credenciais
somente em pagamentos, healthchecks, valores falsos de CI e a única trava de
ativação vazia.

Saída: código publicado com cartão desligado, Pix comprovado e rollback
preparado.

### L9. Sandbox ponta a ponta

Executa a matriz oficial de cartões, webhook real, reconciliação sem webhook,
consumidores e regressão Pix.

Saída: uma transação aprovada percorre tela, pagamentos, evento, pedido,
matrícula, lead e mensagem uma vez; cenários adversariais fecham sem cobrança
duplicada.

### L10. Auditoria independente

Revisor somente leitura compara diff, contratos, invariantes, testes, logs e
evidências. Guardas são quebrados de propósito e precisam ficar vermelhos.

Saída: zero achado crítico ou alto aberto. Achado vira correção no lote dono,
nunca edição do auditor.

### L11. Canário de produção, G12A

Após autorização explícita, libera um site, executa compra real de baixo valor,
confirma aprovado, efeitos e estorno autorizado.

Saída: Pix continua vendendo, cartão funciona no site canário, filas estão
vazias e referências batem com a Appmax.

### L12. Observação e fechamento, G12B

Mede em 15 minutos, 60 minutos e no próximo dia útil: erros, latência,
tentativas presas, inbox, outbox, fila morta, duplicidade e divergência.

Saída: nenhuma cobrança sem referência, nenhum aprovado sem efeito e toda
tentativa não terminal tem ação operacional registrada.

## 12. Escada de PRs

Cada linha abaixo vira TAR somente depois do comando de início. Cada PR fica
abaixo de 15 arquivos fora de painel/ e fila/.

| ID | Resultado | Célula | Alvos principais | Depende de | Risco | Prova de saída |
|---|---|---|---|---|---|---|
| L1A | lei Appmax com guardas | ci | INVARIANTES.md, inventário e testes-guarda | L0 | alto, CODEOWNERS | mutações deixam cada guarda vermelho |
| L1B | contrato v2 neutro | contracts | contracts/pagamentos.openapi.yaml, contracts/checkout.openapi.yaml, contracts/eventos/*.v2.json, fixtures | L0 | crítico, rito | freeze e aditivo verdes, PR somente contracts/ |
| L2A | checkout consome v2 | checkout | consumer de eventos e testes | L1B | alto | v1 e v2 geram um pedido pago |
| L2B | alunos consome v2 | alunos | consumer, handler de matrícula e testes | L1B | crítico | uma matrícula sob replay e concorrência |
| L2C | leads consome v2 | leads | consumer, handler e testes | L1B | alto | um efeito e uma timeline |
| L2D | mensageria consome v2 | mensageria | consumer, handlers e testes | L1B | alto | uma mensagem por fato |
| L3A | modelo de tentativa | pagamentos | models, migration, domínio e testes | L1B | crítico | migration aditiva e concorrência verde |
| L3B | outbox em toda aprovação | pagamentos | serviço de transição, outbox e testes | L3A | crítico | approved sem outbox torna teste vermelho |
| L4A | OAuth e leitura Appmax | pagamentos | providers/appmax/client.py, configuração e testes | L3B | crítico | 401, 429, 5xx e payload incompleto cobertos |
| L4B | cliente, pedido e cartão | pagamentos | provider Appmax, card service e testes | L4A | crítico | escrita ambígua não repete |
| L5A | webhook e inbox | pagamentos | api/webhooks.py, modelo, migration e testes | L4B | crítico | resposta abaixo de 5 s e zero aprovação pelo corpo |
| L5B | worker e reconciliação | pagamentos | tasks, relay, fila morta, métricas e testes | L5A | crítico | webhook e Redis ausentes são recuperados |
| L6 | confirmação pública | checkout | api.py, clients.py, pedidos, migration e testes | L3A | crítico | site, snapshot e idempotência protegidos |
| L7 | cartão utilizável | checkout | cartao.html, cartao.js e testes de navegador | L4B, L6 | crítico | rede sanitizada e todos os estados visíveis |
| L8A | worker dormente | infra | docker-compose.yml e env de exemplo | L2A..L2D, L5B, L7 | alto, CODEOWNERS | serviços saudáveis e trava vazia |
| L8B | rota e CI | infra/ci | Traefik, workflow e guardas, em PR separado se exceder célula | L8A | alto, CODEOWNERS | CI falso, webhook público e Pix verde |
| L9A | sandbox de API | pagamentos | testes E2E Appmax sem navegador | L2A..D, L8B | crítico | matriz oficial e reconciliação |
| L9B | sandbox de navegador | checkout/e2e | Playwright, compose E2E e provas | L7, L9A | crítico | tela até efeitos downstream |
| L9C | regressão cruzada | e2e | cross-smoke Pix e cartão | L9B | crítico | falha de um provedor não derruba o outro |
| L10 | auditoria | somente leitura | PRs e origin/main | L9C | crítico | zero crítico/alto |
| L11 | ativação | operação | segredo, deploy e site canário | L10 | dinheiro real | compra e estorno autorizados |
| L12 | fechamento | operação | métricas, reconciliação e livro | L11 | alto | janela observada e divergência zero |

Se qualquer linha exigir mais de 15 arquivos, a maestro a divide antes de
despachar e mantém dependência explícita. O executor nunca reduz testes ou
funde responsabilidades para caber.

## 13. Protocolo antidesvio

Não existe garantia honesta de que um modelo nunca tentará sair do plano. A
garantia operacional é impedir que um desvio integre silenciosamente.

### 13.1 Antes de cada despacho

Cada lote nasce como TAR imutável com:

- ID e resultado únicos;
- toca e depende_de;
- cartão move;
- responsabilidade;
- arquivos-alvo graváveis;
- caminhos somente leitura;
- caminhos proibidos;
- invariantes tocados;
- teste que precisa ficar vermelho;
- comandos de validação;
- evidência de saída;
- condição de bloqueio;
- rollback;
- modelo e esforço gerados por economia_da_fabrica.py.

Molde obrigatório:

~~~text
Objetivo:
Célula e dono:
Depende de:
Arquivos-alvo:
Somente leitura:
Proibido:
Invariantes tocados:
Teste vermelho:
Teste verde:
Comandos de validação:
Evidência de saída:
Condição de bloqueio:
Rollback:
Não criar subagente, não ampliar mandato, não editar clone principal.
~~~

### 13.2 Durante a execução

- ci/sessao.py cria worktree isolado;
- fila.py pegar cria reserva atômica;
- no Claude Code, ci/muralha_dos_sub_agentes.py recusa subagente que nasça fora
  de sonnet ou opus;
- no Codex, cada TAR autoriza exatamente um despacho escritor; exploradores e
  revisores permanecem somente leitura;
- se o runtime vigente recusar o despacho escritor, o executor raiz assume a
  mesma TAR e a mesma bancada, sem abrir um segundo escritor;
- reserva, eventos e commits registram o executor; esse registro não é tratado
  como prova criptográfica de autoria;
- ci/pr.py, diff contra brief e auditoria independente provam o escopo escrito,
  não a identidade de quem digitou;
- duas tarefas da mesma célula ficam em série;
- ci/pr.py --arquivos recusa alteração não declarada no pacote;
- o teto de 15 arquivos força divisão;
- CODEOWNERS exige mandato nominal;
- contrato viaja sozinho;
- teste-guarda não pode ser apagado, pulado ou afrouxado;
- dependência descoberta vira nova TAR e não entra de passagem;
- dois FAIL consecutivos no mesmo ponto encerram a tentativa com arquivos
  preservados;
- ERROR corrige o instrumento, não o produto;
- sucessor só é despachado com PASS estruturado do predecessor;
- muralhas e ci-celula-gate precisam ficar verdes no SHA atual;
- conferencia_do_toca.py oferece alerta adicional, mas não é tratada como
  portão enquanto estiver em sombra.

### 13.3 Depois do merge

- a sentinela mede origin/main, não o ramo;
- deploy e publicação recebem prova própria;
- divergência vira registro e TAR no lote dono;
- nenhum agente corrige achado fora de seu brief;
- Antigravity audita; executor corrige; mantenedor decide somente o que é
  exclusivo dele.

## 14. Checklist vivo e continuidade

O Markdown não recebe caixas de estado. Estado digitado apodrece. O checklist
vivo é calculado de:

- fila/tarefas/, com uma tarefa imutável por PR;
- fila/eventos/, append-only;
- reservas remotas;
- PR, SHA, checks, merge e deploy observados;
- painel/registros/, para fatos concluídos e bloqueios.

Comandos canônicos:

~~~powershell
python ci/fila.py listar --ao-vivo
python ci/mapa_de_execucao.py --tar TAR-NNN
git status --short
gh pr view N --json state,headRefOid,mergeCommit,statusCheckRollup
python ci/esperar.py --entrega N --so-desfecho
~~~

Retomada:

1. ler TAR e eventos;
2. medir reserva, worktree, ramo, SHA, PR e checks;
3. reabrir a mesma bancada;
4. usar ci/pr.py --continuar quando o rito indicar;
5. continuar do primeiro gate sem PASS, nunca da memória do agente.

O estado de um lote é um destes resultados:

- PASS: prova estruturada aceita, sucessor pode nascer;
- FAIL: produto ou código reprovou, volta ao dono;
- ERROR: instrumento não mediu, corrige-se o instrumento;
- BLOCKED: decisão, credencial ou dependência identificada;
- SKIP: somente quando o plano declarou que o gate não se aplica.

## 15. Matriz de gates e testes

A cobertura é julgada pelas transições financeiras, classes de resposta e
estados do comprador, não por percentual global de linhas.

| Gate | Entrada | Provas obrigatórias | Saída | Bloqueia se |
|---|---|---|---|---|
| G0 pré-voo | decisões de sandbox de L0 completas | baseline, credenciais sandbox, external_id, callback público, mandato e rollback | briefs fechados; autorização de dinheiro real pode seguir aberta | qualquer pré-requisito de sandbox ausente |
| G1 contratos | G0 | OpenAPI, schemas, fixtures válidas e inválidas, freeze e aditivo | v2 congelado e v1 preservado | breaking em lugar ou consumidor desconhecido |
| G2 consumidores | G1 | v1, v2, replay, concorrência, Redis real e dedup entre versões | quatro células compatíveis | efeito duplicado |
| G3 domínio | G1 | migration aditiva, tentativa, duplo clique, nova tentativa e outbox | estado reconciliável | cobrança sem tentativa ou aprovação sem outbox |
| G4 cliente | G3 | OAuth, 401, 429, 5xx, timeout, HTML e 2xx incompleto | cliente fail-closed | retry cego ou segredo em saída |
| G5 webhook | G4 | inbox, duplicado, fora de ordem, forjado e tempo de resposta | corpo não decide dinheiro | endpoint lento ou aprovação pelo payload |
| G6 recuperação | G5 | worker, queda entre consulta e commit, Redis fora e webhook ausente | processamento supervisionado | outbox ou tentativa órfã |
| G7 checkout backend | G3 | site, snapshot, token, titular, IP, parcela e idempotência | API pública segura | valor do navegador decide cobrança |
| G8 navegador | G4, G7 | Playwright, captura de rede, mobile e estados visíveis | cartão utilizável | SDK no Pix ou cartão bruto na plataforma |
| G9 infra dormente | G6, G8 | compose, health, env falso, segredo ausente e Pix público | cartão desligado e sistema saudável | Appmax ausente derruba Pix |
| G10 sandbox real | G2 e G9 | cartões oficiais, webhook real, reconciliador e consumidores | ponta a ponta provado | qualquer elo inferido |
| G11 auditoria | G10 | revisão independente, mutações, segredo, logs e passe de remoção | zero crítico/alto | guarda nunca visto vermelho |
| G12 produção e observação | G11 | G12A: canário, compra, estado final e estorno; G12B: filas, reconciliação e janelas de 15 min, 60 min e próximo dia útil | PASS somente depois de L12 | dinheiro sem autorização, observação incompleta ou divergência |

Tipos de teste:

- unitário: tradutor de status, máquina de estados, validação, OAuth e erros;
- contrato: OpenAPI, JSON Schema e retrocompatibilidade;
- integração: Django, Postgres e Redis reais, HTTP externo interceptado no
  transporte;
- navegador: Playwright, rede sanitizada, refresh e mobile;
- sandbox: API e CDN Appmax reais, cartões oficiais e webhook público;
- produção: canário real autorizado, prova externa e rollback.

## 16. Cartões oficiais de sandbox

| Cartão de teste | Resultado exigido |
|---|---|
| 4000000000000010 | aprovado, evento único, pedido pago e matrícula única |
| 4000000000000028 | autorizado, continua em análise e não matricula |
| 4000000000000002 | recusado, permite nova tokenização |
| 4000000000000036 | erro transacional, não queima o Intent |
| 4000000000000044 | falha do pedido, não vira pagamento interno |
| 4000000000009999 | indisponibilidade, sem retry cego e sem afetar Pix |

São dados oficiais de teste. Nenhum cartão real entra em documentação, fixture
ou evidência.

## 17. Cenários adversariais obrigatórios

1. dois cliques simultâneos resultam em uma chamada externa;
2. refresh entre tokenização e confirmação retoma o pedido;
3. token de uso único repetido não cobra duas vezes;
4. timeout após POST entra em reconciliação;
5. 2xx sem campos obrigatórios falha fechado;
6. primeiro 401 renova, segundo 401 encerra;
7. 429 respeita Retry-After e limite oficial;
8. 503, timeout e HTML não mudam estado financeiro;
9. webhook diz aprovado e API diz pendente, permanece pendente;
10. webhook diz aprovado e API diz cancelado, não há aprovação;
11. pedido externo desconhecido não produz consulta irrestrita;
12. quatro reentregas do webhook produzem um efeito;
13. eventos fora de ordem não fazem estado regredir;
14. worker cai depois da consulta e antes do commit, reprocesso conclui uma vez;
15. Redis cai depois do commit, outbox é republicada;
16. webhook não chega, reconciliador encontra o estado;
17. merchant, site, total, produto ou cliente divergente entra em quarentena;
18. autorizado não emite pagamento.aprovado;
19. reembolso total, parcial e chargeback são idempotentes;
20. PAN, validade ou CVV no endpoint recebem 422, sem persistência ou log;
21. client_secret, Bearer ou token no log reprovam;
22. Appmax fora deixa cartão indisponível e Pix funcional;
23. Mercado Pago fora deixa Pix indisponível e cartão funcional;
24. site A consultando pedido do site B recebe 404;
25. Appmax JS bloqueado mostra ação e retorno ao Pix;
26. parcela booleana, zero, acima do máximo ou adulterada recebe 422;
27. página Pix contendo Appmax JS reprova;
28. aprovação síncrona sem outbox reprova;
29. imagem anterior sobe sobre migration aditiva e mantém Pix;
30. rollback bloqueia novas cobranças e reconcilia as pendentes.

## 18. Deploy, ativação e rollback

### 18.1 Ordem de publicação

1. contratos;
2. consumidores compatíveis;
3. domínio e cliente Appmax;
4. webhook, worker, reconciliador e outbox;
5. checkout backend;
6. checkout navegador;
7. infraestrutura com trava vazia;
8. sandbox;
9. auditoria;
10. site canário;
11. demais sites autorizados.

Código e infraestrutura entram dormentes. Antes de ativar cartão, a borda
pública precisa provar Pix, worker, webhook e healthchecks.

### 18.2 Rollback

1. esvaziar APPMAX_CARD_ENABLED_SITES;
2. impedir novas tentativas de cartão;
3. manter Pix no Mercado Pago;
4. manter webhook, worker e reconciliador;
5. voltar checkout para imagem anterior se necessário;
6. voltar pagamentos somente quando tentativas pendentes estiverem
   reconciliadas ou registradas para acompanhamento;
7. usar migration aditiva compatível com a imagem anterior;
8. usar rollback.yml com imagem ancestral comprovada;
9. em incidente de credencial, desativar instalação e rotacionar segredo;
10. medir da internet: cartão bloqueado com explicação, Pix criando QR e
    tentativa pendente chegando a estado confiável.

Rollback de código não cancela cobrança já enviada. Dinheiro enviado permanece
em reconciliação até confirmação.

## 19. Auditoria final

O auditor é somente leitura e responde por arquivo e linha. A auditoria exige:

- diff real contra o brief de cada TAR;
- nenhum arquivo fora de alvo;
- contratos exportados iguais aos congelados;
- PAN, validade e CVV ausentes de requests internos, banco, logs e eventos;
- segredo Appmax ausente do checkout;
- Pix sem import, script ou cliente Appmax;
- cartão sem operação Mercado Pago;
- webhook incapaz de aprovar sozinho;
- escrita ambígua sem retry;
- transição monotônica;
- inbox, outbox e reconciliador recuperáveis;
- consumidores v2 idempotentes;
- guardas provados por mutação;
- varredura de segredo e log;
- passe de remoção de rotas e código morto de cartão Mercado Pago;
- muralhas e ci-celula-gate no SHA atual;
- Antigravity medindo origin/main depois do merge;
- reconciliação financeira com IDs e horários sanitizados;
- prova pública separada da prova de integração.

Achado crítico ou alto bloqueia ativação. Achado médio entra no lote dono antes
do canário quando puder afetar dinheiro, privacidade, disponibilidade ou
recuperação.

## 20. Riscos

| Risco | Detecção | Contenção | Dono | Prova de encerramento |
|---|---|---|---|---|
| cobrança duplicada | duas referências para uma tentativa | bloquear nova escrita e reconciliar | pagamentos | uma tentativa, uma referência, um efeito |
| falso aprovado | diferença entre payload e GET | consulta autenticada vence | pagamentos | teste forjado e sandbox |
| aprovado sem matrícula | outbox ou consumidor parado | republicador e fila morta | pagamentos/alunos | ID financeiro ligado a uma matrícula |
| vazamento de cartão | captura de rede, logs e banco | rejeitar campo e rotacionar incidente | checkout/pagamentos | varredura limpa |
| segredo no frontend | bundle e HTML | remover, rotacionar e bloquear deploy | pagamentos | segredo ausente na borda |
| webhook perdido | tentativa não terminal envelhecida | reconciliador | pagamentos | tentativa fechada sem webhook |
| contrato duplica efeitos | v1 e v2 no mesmo fato | dedup por identidade lógica | consumidores | replay cruzado gera um efeito |
| Appmax derruba Pix | cross-smoke | dependências separadas e trava vazia | checkout/pagamentos | Pix verde com Appmax fora |
| estado entre sites | acesso cruzado | filtro e chave por platform_site_id | checkout/pagamentos | teste site A versus B |
| rollback abandona cobrança | tentativa pendente após corte | manter reconciliação ativa | pagamentos/infra | zero pendência sem ação |
| rate limit | 429 e fila crescente | Retry-After, limite e backpressure | pagamentos | taxa sob limite e fila drenada |
| política de estorno indefinida | evento sem efeito de acesso | bloquear L11 | mantenedor | decisão registrada e teste |

## 21. Prazo comprometido

O compromisso do Codex para o escopo completo deste plano é:

- até 12 horas de execução ativa coordenada para chegar a G11 com sandbox
  completo;
- com todos os pré-requisitos disponíveis durante a janela, essas 12 horas são
  programadas em no máximo 2 dias úteis de execução;
- até 2 horas de execução ativa para G12 em produção, depois da liberação de
  credenciais, autorização de dinheiro real e disponibilidade do provedor;
- observação do próximo dia útil é tempo de relógio, não hora ativa.

Condições para iniciar a contagem:

- decisões de L0-S respondidas;
- credenciais sandbox válidas;
- external_id e instalação confirmados;
- URL pública de webhook;
- Appmax JS acessível;
- mandato CODEOWNERS;
- main e ambientes de teste medidos;
- Appmax sem incidente ou bloqueio de conta.

Orçamento do caminho crítico:

| Faixa | Horas ativas máximas | Paralelismo |
|---|---:|---|
| L0 e briefs | 0,5 | serial |
| L1 lei e contrato | 1,0 | serial por rito |
| L2 consumidores | 1,25 | quatro células em paralelo |
| L3 e L4 pagamentos | 2,5 | serial |
| L5 recuperação | 1,5 | serial |
| L6 e L7 checkout | 2,0 | serial, sobreposto ao fim de L5 quando seguro |
| L8 infraestrutura | 0,75 | depois das convenções congeladas |
| L9 sandbox | 1,25 | serial na prova financeira |
| L10 auditoria e correções | 0,75 | auditoria paralela, correção no dono |
| reserva | 0,5 | absorve remediação técnica |
| total | 12,0 | limite da operação ativa |
| L11 produção | 2,0 | após pré-condições |

O prazo de calendário é 12 horas ativas acrescidas das esperas medidas por
Appmax, credencial, DNS, aprovação humana, janela de fornecedor e observação
pós-ativação. Esses períodos aparecem separados e não são declarados como
implementação concluída.

O intervalo de 2 a 4 horas cobre um happy path de sandbox. Ele não cobre
contrato v2, quatro consumidores, tentativa, inbox, worker, reconciliação,
falhas ambíguas, E2E dos dois provedores, auditoria e rollback. Por isso não é
o compromisso usado para chamar a integração de completa.

## 22. Definição de pronto

### 22.1 Sandbox completo

Sandbox está pronto somente quando:

- G0 a G11 estão PASS;
- todos os status Appmax usados têm tradução e teste;
- todos os estados visíveis têm ação;
- a matriz oficial de cartões foi executada;
- webhook real e reconciliação sem webhook foram observados;
- Pix passou antes e depois;
- uma aprovação gerou uma tentativa, uma outbox, um pedido pago, uma matrícula,
  um efeito de lead e uma mensagem;
- duplicado e fora de ordem não repetiram efeito;
- rollback foi exercitado sem derrubar Pix;
- auditoria terminou sem crítico ou alto.

### 22.2 Produção completa

Produção está pronta somente quando:

- G12 está PASS;
- site canário processou compra autorizada;
- autorizado não liberou acesso;
- aprovado liberou uma vez;
- estorno autorizado foi conciliado;
- nenhuma inbox, outbox ou fila morta ficou sem ação;
- IDs, timestamps, SHA, runs e provas externas foram registrados sem PII;
- janela de 15 e 60 minutos foi limpa;
- reconciliação do próximo dia útil fechou sem divergência.

## 23. Pacote final de evidências

- comandos e saídas vermelho e verde dos guardas;
- make ci das células pagamentos, checkout, alunos, leads e mensageria;
- cross-smoke Pix e cartão;
- muralhas e ci-celula-gate no SHA atual;
- IDs de sandbox, status e timestamps sanitizados;
- uma Intent, tentativas correspondentes, uma outbox e efeitos únicos;
- trace Playwright ou captura de rede sanitizada;
- webhook real com tempo de resposta;
- reconciliação concluída sem webhook;
- deploy run, SHA publicado e sondas públicas;
- drill de rollback;
- parecer do auditor independente;
- canário e estorno de produção quando autorizados;
- registro final no livro e conclusão das TARs por evidência.

## 24. Cortes deliberados

Ficam fora porque não são necessários ao resultado:

- multi-merchant ou credencial por site;
- nova interface administrativa;
- Appmax para Pix;
- Mercado Pago para cartão;
- Celery, Tenacity ou Sentry;
- armazenamento de PAN, validade ou CVV;
- tokenização server-side;
- abstração genérica para provedores futuros;
- refatoração de checkout sem relação com a jornada;
- dashboard novo quando fila, métricas e livro já mostram o estado;
- criação antecipada das TARs de implementação.

## 25. Como começar e como encerrar

Começo:

1. mantenedor ordena explicitamente iniciar este plano;
2. mantenedor responde às decisões L0-S e autoriza os caminhos protegidos;
3. maestro cria as TARs da escada com depende_de e espera corretos;
4. L1A é o canário de baixo risco de runtime, pois cria lei e guardas sem
   mudar a execução do checkout;
5. L1B segue pelo Rito de Contrato;
6. nenhum lote posterior nasce antes do gate predecessor.

L0-P volta ao mantenedor somente antes de L11, quando dinheiro real se torna a
próxima ação.

Fecho:

1. todas as TARs estão concluídas por evidência;
2. G0 a G12 têm resultado estruturado;
3. produção e publicação foram medidas de fora;
4. auditoria está limpa;
5. reconciliação financeira fecha;
6. o livro registra resultado, riscos encerrados e qualquer decisão restante;
7. o plano permanece como intenção histórica e o estado continua calculado.

Até o comando explícito de início, a única entrega autorizada é este plano.
