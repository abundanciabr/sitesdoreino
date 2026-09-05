# CS-PAGES-0001, Guia de portfólio com checklist: a reta final deixa de travar

## PORTÃO DE VALIDADE, confira ANTES de mandar para aprovação

- [x] **`FORA DO ESCOPO` não está vazio.**
- [x] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável, uma por uma.**
- [x] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
- [ ] **`APROVADO_POR` está preenchido**, pendente de propósito: quem aprova é
      quem está em `SUGESTOES_APROVADORES` (hoje, só o mantenedor), e a
      assinatura mecânica acontece no formulário da ideia 21 em
      `/admin/caixa/ideia/21/`, citando este CHANGE-ID e este arquivo.

---

## CHANGE-ID

`CS-PAGES-0001`

## SUBSTITUI

`CS-CURSOS-0002`, que mandava construir na célula `cursos`: a casa do guia de
portfólio é `pages`, decidida pelo mantenedor em 01 e 02/09/2026 e reafirmada
por ele em 05/09/2026 (`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §4; registro
`20260903-003` no livro).

## ORIGEM

suggestion_id 21 ("Guias de portifolio com Check-list", Curso e aulas)

## PROBLEMA

O aluno termina as aulas e trava na montagem do portfólio: não sabe o que
entra, o que fica de fora, nem quando está "bom o bastante para mostrar a um
cliente". É o ponto de maior risco de desistência do curso inteiro, com o
primeiro dinheiro já quase na mesa (quem sugeriu descreveu exatamente isso:
terminou as aulas e procrastinou).

## EVIDÊNCIAS

- Votos: 31 (segunda ideia mais votada do quadro)
- Pessoas atrás dela: 31
- Comentários: 0
- Fonte: exportação oficial da Caixa de 05/09/2026, 12:12 UTC

## OBJETIVO

O aluno na reta final abre, em `/pages/`, o "Guia de portfólio": lê os
critérios da equipe (o que entra, quantos itens, em que ordem, o que é
qualidade) e marca um checklist cujo progresso fica salvo, chegando a um
portfólio conferido critério por critério em vez de um "acho que está bom".

## FORA DO ESCOPO

- A fundação da casa `pages` (esqueleto da célula, contrato congelado,
  provisionamento, compose e rota): é o degrau 01 e seguintes da escada do
  `PLANO-PORTFOLIO-DO-ALUNO.md` §5, com tarefa própria. Esta entrega é a tela,
  e ela pressupõe a casa já de pé.
- As peças por link, com legenda, ordem e destaque (degrau 08 da escada).
- O semáforo por peça, calculado das respostas objetivas (degrau 10).
- O pedido de conferência com a tela da equipe (degrau 11) e o selo "conferido
  pela escola" com o evento e o aviso no sininho (degrau 12).
- A vitrine pública `/estudio/<apelido>` (degrau 13).
- O dossiê em PDF montado no servidor (degrau 14).
- Gerador de PDF ou de página pública de portfólio por qualquer outro caminho.
- Filtro automático de qualidade por robô: nesta entrega o filtro são os
  critérios escritos; avaliação de trabalho enviado já tem casa no desenho da
  célula `cursos` (entrega por link com resposta em 24 horas) e não é
  duplicada aqui.
- Qualquer tela fora da célula `pages`.
- Mexer no texto ou nos votos da ideia 21 além do fluxo normal de fases.

## CÉLULA RESPONSÁVEL

`pages` (a nascer: degrau 01 da escada do `PLANO-PORTFOLIO-DO-ALUNO.md` §5).

## CONTRATOS PERMITIDOS

- `identidade`: repassar o cookie da sessão para saber quem é a pessoa. A
  célula `pages` nunca assina sessão própria.
- `alunos`, operação `getStudentStanding`: a matrícula ativa que a porta exige.

Os dois já existem em `contracts/`. Nenhum contrato novo.

## CÉLULAS PROIBIDAS

Toda célula de `celulas.yml`, uma por uma: `admin` (exceto o gesto de mover a
ideia de fase pela tela da Caixa), `alunos` (só pelo contrato acima),
`catalogo`, `checkout`, `cursos`, `encomendas`, `forum`, `funil`,
`gamificacao`, `identidade` (só pelo contrato acima), `leads`, `mensageria`,
`metricas`, `notificacoes`, `pagamentos`, `quiz`, `sugestoes` (leitura direta
proibida; só o fluxo normal de fases pela gestão).

## CRITÉRIOS DE ACEITAÇÃO

- AC-01: aluno com matrícula ativa abre o Guia de portfólio e vê os critérios
  da equipe escritos (o conteúdo vem da Lívia; sem os critérios dela, a obra
  não começa: é pré-requisito, não enfeite).
- AC-02: o aluno marca e desmarca itens do checklist e o progresso persiste
  entre visitas e entre aparelhos (fica no banco, por aluno, não no navegador).
- AC-03: o progresso de um aluno nunca aparece para outro.
- AC-04: quem não tem matrícula ativa não vê o guia (a porta recusa
  explicando, como nas demais telas do site).

## TESTES OBRIGATÓRIOS

- Porta fail-closed: sem sessão e sem matrícula ativa, nada do guia responde.
- Persistência: marcar, sair, voltar; o estado volta igual.
- Isolamento: o checklist de um aluno não vaza para outro.

## RISCO E ROLLBACK

Tela nova e aditiva, atrás da porta da casa `pages`. Rollback é tirar a rota do
ar; as marcações ficam no banco, nada é apagado.

## DEFINITION OF DONE

- [ ] Critérios escritos pela Lívia e revisados pelo mantenedor.
- [ ] AC-01 a AC-04 com teste automatizado onde há código.
- [ ] Prova de fora (a tela vista como aluno) antes de anunciar.
- [ ] Ideia 21 em "Implementado" com nota contando onde o guia mora.
- [ ] Registro no livro de ocorrências com a evidência.

## APROVADO_POR

(vazio até a aprovação humana explícita; a assinatura oficial é o registro no
formulário da ideia 21 em `/admin/caixa/ideia/21/`, citando este CHANGE-ID e
este arquivo, e este campo recebe nome e data no mesmo dia)
