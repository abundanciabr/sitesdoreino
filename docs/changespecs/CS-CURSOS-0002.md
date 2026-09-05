# CS-CURSOS-0002 — Guia de portfólio com checklist: a reta final deixa de travar

> ## SUPERADO. NÃO ASSINE ESTE DOCUMENTO.
>
> Substituído por [`CS-PAGES-0001.md`](CS-PAGES-0001.md) em 05/09/2026, antes de
> qualquer assinatura: o `APROVADO_POR` abaixo continua vazio, e o §4 do
> `FORMATO-CHANGESPEC.md` só torna imutável o ChangeSpec que já foi aprovado.
>
> **O motivo, em uma frase:** este corredor punha o portfólio na célula `cursos`
> e cortava a vitrine pública, o selo da escola e o dossiê, contrariando a
> decisão do mantenedor de 01 e 02/09/2026, que já tinha escolhido a célula
> `pages` como casa do portfólio (`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`
> §4, e `docs/decisoes/PLANO-CELULA-CURSOS.md` §3.3, que diz o mesmo).
>
> O corpo abaixo fica intacto, como registro do que foi escrito. A ideia 21 se
> assina pelo `CS-PAGES-0001`.

## PORTÃO DE VALIDADE — confira ANTES de mandar para aprovação

- [x] **`FORA DO ESCOPO` não está vazio.**
- [x] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável, uma por uma.**
- [x] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
- [ ] **`APROVADO_POR` está preenchido** — pendente de propósito: quem aprova é
      quem está em `SUGESTOES_APROVADORES` (hoje, só o mantenedor), e a
      assinatura mecânica acontece no formulário da ideia 21 em
      `/admin/caixa/ideia/21/`, citando este CHANGE-ID e este arquivo.

---

## CHANGE-ID

`CS-CURSOS-0002`

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

O aluno na reta final abre, dentro da área de cursos, o "Guia de portfólio":
lê os critérios da equipe (o que entra, quantos itens, em que ordem, o que é
qualidade) e marca um checklist cujo progresso fica salvo, chegando a um
portfólio conferido critério por critério em vez de um "acho que está bom".

## FORA DO ESCOPO

- Gerador de PDF ou de página pública de portfólio (é ideia futura própria,
  que conversa com "Criações do mês" e com o selo de entregas).
- Filtro automático de qualidade por robô: nesta entrega o filtro são os
  critérios escritos; avaliação de trabalho enviado já tem casa no desenho da
  célula (entrega por link com resposta em 24 horas) e não é duplicada aqui.
- Qualquer tela fora da célula `cursos`.
- Mexer no texto ou nos votos da ideia 21 além do fluxo normal de fases.

## CÉLULA RESPONSÁVEL

`cursos`

## CONTRATOS PERMITIDOS

Os que a célula já usa para saber quem é a pessoa e se a matrícula está ativa
(o caminho normal da porta). Nenhum contrato novo.

## CÉLULAS PROIBIDAS

`admin` (exceto o gesto de mover a ideia de fase pela tela da Caixa),
`alunos`, `catalogo`, `checkout`, `encomendas`, `forum`, `funil`,
`gamificacao`, `identidade`, `leads`, `mensageria`, `metricas`,
`notificacoes`, `pagamentos`, `quiz`, `sugestoes` (leitura direta proibida;
só o fluxo normal de fases pela gestão).

## CRITÉRIOS DE ACEITAÇÃO

- AC-01: aluno com matrícula ativa abre o Guia de portfólio e vê os critérios
  da equipe escritos (o conteúdo vem da Lívia; sem os critérios dela, a obra
  não começa — é pré-requisito, não enfeite).
- AC-02: o aluno marca e desmarca itens do checklist e o progresso persiste
  entre visitas e entre aparelhos (fica no banco, por aluno, não no navegador).
- AC-03: o progresso de um aluno nunca aparece para outro.
- AC-04: quem não tem matrícula ativa não vê o guia (a porta recusa
  explicando, como nas demais telas da célula).

## TESTES OBRIGATÓRIOS

- Porta fail-closed: sem sessão e sem matrícula ativa, nada do guia responde.
- Persistência: marcar, sair, voltar; o estado volta igual.
- Isolamento: o checklist de um aluno não vaza para outro.

## RISCO E ROLLBACK

Tela nova e aditiva, atrás da porta que já existe. Rollback é tirar a rota do
ar; as marcações ficam no banco, nada é apagado.

## DEFINITION OF DONE

- [ ] Critérios escritos pela Lívia e revisados pelo mantenedor.
- [ ] AC-01 a AC-04 com teste automatizado onde há código.
- [ ] Prova de fora (a tela vista como aluno) antes de anunciar.
- [ ] Ideia 21 em "Implementado" com nota contando onde o guia mora.
- [ ] Registro no livro de ocorrências com a evidência.

## APROVADO_POR

— (vazio até a aprovação humana explícita; a assinatura oficial é o registro
no formulário da ideia 21, e este campo recebe nome e data no mesmo dia)
