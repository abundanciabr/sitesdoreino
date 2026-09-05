# CS-PAGES-0001 — O portfólio do aluno: roteiro, curadoria, conferência da escola e o link para mandar ao cliente

## PORTÃO DE VALIDADE — confira ANTES de mandar para aprovação

- [x] **`FORA DO ESCOPO` não está vazio.**
- [x] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável, uma por uma.**
- [x] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
- [ ] **`APROVADO_POR` está preenchido** — pendente de propósito: quem aprova é
      quem está em `SUGESTOES_APROVADORES` (hoje, só o mantenedor), e a
      assinatura mecânica acontece no formulário da ideia 21 em
      `/admin/caixa/ideia/21/` (rota `caixa_assinar`), que pede o número do
      documento, onde ele está, quem aprovou e quando.

> **De onde este corredor sai.** Ele é derivado, ponto a ponto, do estudo de
> viabilidade `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`, que já carrega duas
> decisões do mantenedor tomadas em 01 e 02/09/2026 (registros `20260901-023`,
> `20260902-061` e `20260903-003`): a casa é a célula `pages`, e as fotos entram
> por link colado. Nada aqui é escopo novo: o que não estiver no plano não está
> neste corredor.
>
> **Ele supera o `CS-CURSOS-0002.md`**, escrito em 05/09/2026 sem citar o plano,
> que punha o guia na célula `cursos` e cortava a vitrine pública, o selo da
> escola e o dossiê. Aquele documento nunca foi assinado e não deve ser.

---

## CHANGE-ID

`CS-PAGES-0001`

## ORIGEM

suggestion_id 21 ("Guias de portifolio com Check-list", Curso e aulas)

## PROBLEMA

O aluno termina as aulas e trava na montagem do portfólio. Ele não sabe o que
entra, o que fica de fora, nem quando a peça está boa o bastante para mostrar a
um cliente pagante, e não tem para onde mandar o resultado quando termina. É o
ponto de maior risco de desistência do curso inteiro, com o primeiro dinheiro
já quase na mesa: quem sugeriu descreveu exatamente isso, terminou as aulas e
procrastinou.

## EVIDÊNCIAS

- Votos: 31 (segunda ideia mais votada do quadro)
- Pessoas atrás dela: 31
- Comentários: 0
- Fonte: exportação oficial da Caixa de 05/09/2026, 12:12 UTC

## OBJETIVO

Os cinco pedidos decompostos no §1 do plano, e não só o primeiro:

1. **Roteiro** — o aluno abre a Prancheta e vê as listas de conferência de como
   estruturar o portfólio, escritas pela escola.
2. **Curadoria** — as listas dizem o que entra e o que fica de fora, peça por
   peça, em vez de deixar a decisão no escuro.
3. **Filtro de qualidade** — o semáforo por peça mostra o que falta, e o aluno
   manda o portfólio para a equipe conferir de verdade, pela mesma fila humana
   que já atende os marcos.
4. **Gerador final** — a vitrine em `meshcraft.top/estudio/<apelido>`, com
   versão de impressão, e o dossiê em PDF montado no servidor.
5. **O empurrão da reta final** — quem termina as aulas recebe o convite para
   começar, em vez de encarar a montanha sozinho, e o marco acende na trilha
   quando o selo sai.

## FORA DO ESCOPO

- **Envio de imagem hospedada por nós** (degrau 09 da escada do plano). Fora por
  decisão do mantenedor de 01/09/2026: a foto entra por link colado. A porta de
  volta está descrita no §6.2 do plano e é barata, mas **não se constrói antes
  de ele pedir**.
- Nota, estrela, ranking ou voto popular em portfólio ou em peça de aluno.
- Detecção de "isto foi feito por IA".
- Trancar aula ou conteúdo do curso atrás de check-list, ponto ou nível.
- E-mail, telefone ou nome completo na página pública.
- Guardar a peça em duas células.
- Marco real pagando XP (ele vale zero, de propósito).
- Mexer no texto ou nos votos da ideia 21 além do fluxo normal de fases.

## CÉLULA(S) RESPONSÁVEL(IS)

**`pages`** — célula nova, a nascer no degrau 01 da escada do §5. É a casa do
portfólio, das Páginas do aluno e da vitrine pública, com dois endereços
(`/pages` para o aluno logado, `/estudio/<apelido>` para o link que ele manda ao
cliente) apontando para a mesma célula no Traefik.

Os degraus vizinhos que a escada já prevê são autorizados **em PR próprio, um
por degrau**, e cada um toca só a sua célula:

- **`gamificacao`** (degrau 15) — escutar o evento de portfólio conferido e
  acender o marco na trilha. Nada além disso.
- **`admin`** (degrau 16) — os guias no editor de documentos, com o rascunho
  pronto para o texto do mantenedor. E o degrau 00, o mapa para IA citando a
  célula que nasce.
- **`mensageria`** (degrau 17) — a sequência que convida quem terminou as aulas.
  O gatilho é **declarado**, nunca inferido: o plano é explícito em que a
  plataforma não serve aula e não sabe sozinha quando alguém terminou.
- **`funil`** (degrau 18) — o caminho no menu e na home logada.

Fora de célula, e também em PR próprio: **`contracts`** (degrau 03, o contrato
congelado e os eventos `pages.portfolio.*`) e **`infra`** (degrau 04, o script de
provisionamento sozinho; degrau 05, o compose, o Traefik e o inventário de rotas
no mesmo PR). Os dois são caminho CODEOWNERS e pedem mandato escrito no despacho.

## CONTRATOS PERMITIDOS

- O contrato de identidade, para saber quem é a pessoa. A célula `pages` repassa
  o cookie à `identidade` e **nunca assina sessão própria** (degrau 06).
- O contrato de matrícula ativa, o caminho normal da porta, igual ao das demais
  telas de aluno.
- `pages.portfolio.*` — os eventos que a própria célula publica, congelados no
  degrau 03. É por eles que a gamificação sabe do selo.

Nenhum outro contrato novo. A tela que precisar de dado de duas células pergunta
por HTTP com **falha aberta**, o mesmo desenho já usado entre o fórum e a
gamificação, e nunca por chave estrangeira cruzando banco de célula.

## CÉLULAS PROIBIDAS

Toda célula do sistema fora das autorizadas acima, nominalmente:

`alunos`, `catalogo`, `checkout`, `cursos`, `encomendas`, `forum`,
`identidade` (escrita proibida; só a leitura de quem é a pessoa pelo contrato),
`leads`, `metricas`, `notificacoes`, `pagamentos`, `quiz`,
`sugestoes` (leitura direta proibida; só o fluxo normal de fases pela gestão).

## CRITÉRIOS DE ACEITAÇÃO

Um por degrau entregável da escada do §5.

- **AC-01** (degrau 01) — a célula `pages` existe em `celulas.yml`, responde
  `/healthz` com 200 e tem constituição, manifesto e rollback próprios.
- **AC-02** (degrau 02) — portfólio, peça, item de conferência e estado do aluno
  são gravados no banco da própria célula, sem nenhuma chave estrangeira
  apontando para banco de outra.
- **AC-03** (degrau 03) — o contrato e os eventos `pages.portfolio.*` estão
  congelados, com versão, e o teste de contrato reprova quem mudar campo sem
  Rito.
- **AC-04** (degrau 05) — `meshcraft.top/pages` e `meshcraft.top/estudio`
  respondem em produção, e as duas rotas aparecem no inventário de rotas.
- **AC-05** (degrau 06) — **porta fail-closed**: quem não tem sessão, ou não tem
  matrícula ativa, não vê nada do portfólio, e a recusa explica em português o
  que aconteceu e o que fazer.
- **AC-06** (degrau 07) — o aluno abre a Prancheta, vê as cinco etapas com as
  listas de conferência lidas do banco, marca e desmarca itens, e **o progresso
  persiste entre visitas e entre aparelhos** (fica no banco, por aluno, nunca no
  navegador).
- **AC-07** (degrau 07 e 08) — **isolamento**: o progresso e as peças de um aluno
  nunca aparecem para outro, em nenhuma tela e em nenhuma resposta de API.
- **AC-08** (degrau 08) — o aluno cadastra uma peça colando o link, com legenda,
  ordem e destaque; a Prancheta confere o link no momento em que ele é colado e
  recusa o que não responde, dizendo o motivo.
- **AC-09** (degrau 08) — quando um link que já funcionava para de responder, o
  aluno é avisado pelo sininho e a peça é marcada como quebrada. **O sistema
  nunca apaga a peça sozinho.**
- **AC-10** (degrau 10) — cada peça mostra um semáforo calculado só das respostas
  objetivas do aluno, e a tela lista, item a item, o que ainda falta naquela
  peça.
- **AC-11** (degrau 11) — o aluno pede a conferência e o pedido aparece na fila
  da equipe, com prazo, aceite e devolução com motivo escrito em português, pelo
  mesmo molde da tela de marcos.
- **AC-12** (degrau 12) — aceita a conferência, o portfólio recebe o selo
  "conferido pela escola", o evento é publicado e o aluno recebe a carta no
  sininho. O texto do selo diz que ele vale para o que o monitor viu no dia da
  conferência.
- **AC-13** (degrau 13) — `/estudio/<apelido>` só existe se o aluno ligar
  (**opt-in**), sai com `noindex`, mostra apenas apelido, obras aprovadas e
  marcos escolhidos, e despublicar tira a página do ar imediatamente.
- **AC-14** (degrau 13) — a página pública **não expõe e-mail, telefone nem nome
  completo**, e a política de conteúdo da página permite imagem de domínio de
  terceiro de forma controlada, com teste.
- **AC-15** (degrau 13) — existe uma versão de impressão da página, que o
  navegador salva sozinho.
- **AC-16** (degrau 14) — o aluno baixa o dossiê em PDF montado no servidor, com
  as peças aprovadas na ordem que ele escolheu.
- **AC-17** (degrau 15) — recebido o evento do selo, a gamificação acende o marco
  "portfólio" na trilha, **sem pagar XP** (o marco real vale zero, de propósito).
- **AC-18** (degrau 16) — os guias existem no editor de documentos do admin, e o
  mantenedor os edita sem abrir PR.
- **AC-19** (degrau 17) — a sequência que convida para a Prancheta dispara por um
  fato **declarado** (liberação, marco, ou o botão "terminei as aulas"), e nunca
  por inferência de progresso.
- **AC-20** (degrau 18) — o caminho para a Prancheta aparece no menu e na home
  logada, e o aluno chega lá sem digitar endereço.

## TESTES OBRIGATÓRIOS

- **Porta fail-closed**: sem sessão e sem matrícula ativa, nenhuma rota de
  `/pages` responde conteúdo.
- **Persistência**: marcar, sair, voltar de outro aparelho; o estado volta igual.
- **Isolamento**: nada do portfólio de um aluno aparece na resposta pedida por
  outro.
- **Contrato congelado**: mudar campo de `pages.portfolio.*` sem Rito reprova.
- **Link quebrado**: link que para de responder marca a peça e avisa, e nunca
  apaga.
- **Vitrine**: a página pública não devolve e-mail, telefone nem nome completo, e
  sai com `noindex`; despublicar responde 404 na mesma hora.
- **Opt-in**: aluno que nunca ligou a vitrine não tem página pública.
- **Marco sem XP**: o evento do selo acende o marco e o saldo de XP não muda.
- **Gatilho declarado**: a sequência não dispara sem o fato declarado chegar.

## RISCO E ROLLBACK

A célula é nova e aditiva: nada do que já está no ar depende dela, e cada degrau
entra atrás do anterior. O rollback tem três camadas, da mais barata para a mais
cara:

- **Uma tela** — tirar a rota do ar. As marcações e as peças ficam no banco, nada
  é apagado.
- **A vitrine pública** — despublicar é imediato e por aluno, e o degrau 13 já
  exige isso como critério.
- **A célula inteira** — o rollback próprio da gênese, escrito no degrau 01, tira
  o serviço do compose e do Traefik. Como a peça mora em uma casa só, nenhuma
  outra célula fica com dado órfão.

O risco declarado e aceito pelo mantenedor está no §6.2 do plano: link de aluno
quebra, e quando quebra a escola não consegue consertar. A mitigação está nos
critérios AC-08 e AC-09.

## DEFINITION OF DONE

- [ ] Cada degrau em PR próprio, dentro do orçamento de 15 arquivos, na ordem da
      escada do §5 do plano.
- [ ] AC-01 a AC-20 com teste automatizado onde há código.
- [ ] O passo manual da VPS (banco, role e env) entregue ao mantenedor como bloco
      único de colar, fail-closed, com a janela rotulada.
- [ ] Nenhuma chave estrangeira cruzando banco de célula.
- [ ] Nenhum texto que o aluno lê com travessão (`ci/travessao.py`).
- [ ] Prova de fora: a Prancheta e a vitrine vistas como aluno, antes de anunciar.
- [ ] Guias escritos pela escola e revisados pelo mantenedor.
- [ ] Ideia 21 em "Implementado" com nota contando onde o portfólio mora.
- [ ] Registro no livro de ocorrências com a evidência, a cada degrau.

## APROVADO_POR

— (vazio de propósito, até a aprovação humana explícita)

A assinatura mecânica não é este campo: é o formulário da ideia 21 em
`/admin/caixa/ideia/21/`, rota `caixa_assinar`, que registra o número do
documento, onde ele está, quem aprovou e quando. A célula de sugestões reconhece
como aprovador apenas quem estiver em `SUGESTOES_APROVADORES`, e a lista vazia é
fail-closed. Enquanto essa assinatura não existir, **nenhuma linha de código
deste corredor pode ser escrita**.
