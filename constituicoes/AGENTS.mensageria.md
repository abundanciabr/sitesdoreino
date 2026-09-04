# Constituição da Célula: mensageria
> **Jurisdição:** governa apenas `services/mensageria/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
Comunicação com quem usa a plataforma, em duas formas que convivem:

1. **Transacional — um fato, um envio, agora.** E-mail e WhatsApp disparados por
   eventos: boas-vindas no `pagamento.aprovado`, recuperação no `pix.expirado` e
   no `pagamento.recusado`. Esta metade é a original desta célula e não muda.
2. **Sequências que ESPERAM (jornadas)** — emenda de 31/08/2026, decisão do
   mantenedor em 30/08 (`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §4.1):
   uma inscrição, vários passos, dias de espera entre eles, e a condição
   reavaliada na hora de enviar. **Uma sequência que espera dois dias não é
   transacional**, e sem esta linha a missão recusaria como fora de escopo o
   trabalho que o mantenedor pediu. O motor mora AQUI, e não numa célula nova:
   foi a escolha dele, com os custos dos dois lados na mesa.

Templates versionados dentro da célula. Nunca toca dinheiro, nunca bloqueia dinheiro.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/mensageria/**`
- **SOMENTE LEITURA:** `contracts/eventos/`
- **PROIBIDO (nem ler):** as demais células, `infra/`

## Comunicação
- **Escuta:** `pedido.criado.v1`, `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1`, `quiz.completado.v1`, `identidade.pessoa-cadastrada.v1` (consumer group `mensageria`). O último entrou em 02/09/2026: é o gatilho da primeira sequência de verdade, e sem ele o pedido mais óbvio do mantenedor ("após o cadastro, mandar boas-vindas") não teria o que escutar.
- **Publica:** `notificacao.devida.v1` — a carta de um passo de sequência, pela outbox de `apps/jornadas`. Até 02/09/2026 esta célula só escutava. O assunto é `jornada.passo` e **o texto não viaja**: o sininho o busca pelo `passo_id` na hora de ler, no idioma de quem lê (modelo híbrido, Rito de 31/08/2026).
- **Pergunta à `identidade`** (a partir das jornadas): traduz o id de PLATAFORMA
  em e-mail e idioma **na hora do envio**, nunca antes. Guardar o e-mail aqui
  seria uma segunda casa do dado que vive numa linha só (`DECISAO-EVO-01` §3), e
  o idioma gravado na inscrição congelaria a língua de quem se inscreveu. A linha
  `consome:` em `celulas.yml` entra no PR que escrever o cliente, não neste: o
  varredor reprova declaração órfã.
- **Expõe:** nada público. A porta de MÁQUINA `/api/mensageria` nasceu em
  04/09/2026 (degrau 6c do `PLANO-SEQUENCIAS-DE-MENSAGENS.md`) e vive só na rede
  interna: esta célula não tem rota no Traefik nem prefixo público. Por ela a
  tela do mantenedor lê as jornadas, os passos com o texto por idioma, quem está
  dentro e **o que não foi entregue, com o motivo**; e por ela ele grava uma
  frase nova, o que **publica versão nova** e nunca edita a publicada. Quem
  fecha é o Bearer do par, em DOIS graus: `TOKENS_SOMENTE_LEITURA_<PAR>` lê, e
  publicar exige `TOKENS_PUBLICACAO_<PAR>`, porque grau plano daria a escrita de
  uma sequência que fala com alunos a quem só precisava desenhar uma consulta.
  A linha original desta constituição dizia "API interna opcional para reenvio
  manual": esse reenvio continua não existindo, e o que existe é isto.
- **Banco:** `mensageria_db` (role `mensageria_user`) — log de envios e templates

## Invariantes desta célula
- **Multissítio:** template e remetente escolhidos pelo `site_id` do evento
  (fallback padrão da plataforma) — e-mail de um site jamais sai com a marca de outro.
- Consumo idempotente por `event_id`: evento reentregue ⇒ UM envio (tabela de deduplicação).
- Falha de provedor (SMTP/WhatsApp fora) ⇒ retry com backoff via Huey; jamais propaga erro para quem emitiu.
- Todo envio registra: evento de origem, template+versão, destinatário, resultado.

### A régua de quem recebe (jornadas, 31/08/2026)
A régua é UMA SÓ, por pessoa, e atravessa toda entrega desta célula — um teto por
canal seria um teto por caixa de entrada, e a pessoa é uma só. O plano
(`PLANO-SEQUENCIAS-DE-MENSAGENS.md` §6) é a lei; aqui fica o que nenhum PR desta
célula pode afrouxar:

- **A classe de entrega decide ANTES de tudo.** `crítica` e `transacional`
  passam **por fora da régua inteira** — não esperam vaga, não esperam janela e
  não somem porque alguém silenciou incentivo. `relacional` e `engajamento`
  passam por ela. O cenário que essa ordem conserta é real: medalha às 10h
  barrando a liberação de matrícula às 18h.
- **Teto de 1 por dia por pessoa.** Passo barrado **reagenda**, nunca se perde.
  Duas jornadas disputando a vaga: ganha a inscrição mais antiga (sem ordem
  definida, o guarda do teto não teria o que afirmar).
- **Janela com hora de abrir E de fechar: nunca depois das 20h, nunca antes das
  8h**, em `America/Sao_Paulo`. O piso não é zelo: sem ele, "reagenda para a
  próxima janela válida" manda a mensagem às 6h e a régua que existe para não
  incomodar acabaria de incomodar.
- **Só boa notícia.** Nenhuma jornada de culpa, cobrança ou "você está
  perdendo". O vocabulário de assuntos é fechado para que uma jornada nova não
  consiga inventar um assunto ruim.
- **Fail-closed:** régua indisponível ou preferência ilegível ⇒ **não envia**, e
  registra o motivo. Mesma escolha que a Caixa já fez com a lista de aprovadores.
- **A idempotência existente não se altera.** A trava
  `unique(order_id, tipo, canal)` de `EnvioRegistrado` continua exatamente como
  está; o motor escreve `order_id` sintético (`jornada:<inscricao_id>:<passo_id>`),
  que nunca colide com um `order_id` real do checkout. A trava passa a proteger as
  duas coisas sem uma linha de migração e sem risco para o fluxo de dinheiro.

## Definição de Pronto
`make ci` verde · teste de reentrega duplicada verde · diff no escopo.

## Ritos
RITOS.md §1, §2.
