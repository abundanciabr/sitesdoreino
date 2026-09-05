# CS-CURSOS-0001 — Aula de acessórios: o par que faltava dos cabelos

## PORTÃO DE VALIDADE — confira ANTES de mandar para aprovação

- [x] **`FORA DO ESCOPO` não está vazio.**
- [x] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável, uma por uma.**
- [x] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
- [ ] **`APROVADO_POR` está preenchido** — pendente de propósito: quem aprova é
      quem está em `SUGESTOES_APROVADORES` (hoje, só o mantenedor), e a
      assinatura mecânica acontece no formulário da ideia 20 em
      `/admin/caixa/ideia/20/`, citando este CHANGE-ID e este arquivo.

---

## CHANGE-ID

`CS-CURSOS-0001`

## ORIGEM

suggestion_id 20 ("tutorial de chapéu / acessórios", Curso e aulas)

## PROBLEMA

Os cabelos que os clientes encomendam quase sempre vêm com acessório junto
(chapéu, principalmente), e o curso não ensina a modelar acessórios. O aluno ou
recusa metade do trabalho ou entrega o acessório sem técnica, abaixo do padrão
do resto do curso.

## EVIDÊNCIAS

- Votos: 40 (a ideia mais votada do quadro inteiro)
- Pessoas atrás dela: 41 (quase um quarto da turma)
- Comentários: 0
- Fonte: exportação oficial da Caixa de 05/09/2026, 12:12 UTC

## OBJETIVO

A pessoa matriculada encontra, no mesmo lugar onde assiste às demais aulas, uma
aula de acessórios que a leva do zero a um chapéu vendável: modelagem, encaixe
na cabeça do avatar do Roblox, versão leve e versão detalhada, textura.

## FORA DO ESCOPO

- Mais de um pacote de gravação: esta entrega é chapéu + fundamentos de
  encaixe. Óculos, brincos e afins são candidatos a uma aula seguinte, medida
  pela procura depois desta.
- Qualquer mudança de código no player ou na estrutura da área de cursos: esta
  obra é CONTEÚDO. Se a publicação exigir código novo, isso é outro ChangeSpec.
- Marketplace, venda de modelos prontos ou distribuição de arquivos .blend
  fora do padrão que as aulas atuais já usam.
- Mexer no texto ou nos votos da ideia 20 além do fluxo normal de fases.

## CÉLULA RESPONSÁVEL

`cursos` (publicação de conteúdo pelo caminho normal de aulas; nenhuma
migração, nenhum contrato novo)

## CONTRATOS PERMITIDOS

Nenhum novo. A aula entra pelo caminho de publicação de conteúdo que a célula
já tem; o acesso do aluno passa pela porta normal (matrícula ativa).

## CÉLULAS PROIBIDAS

`admin` (exceto o gesto de mover a ideia de fase pela tela da Caixa),
`alunos`, `catalogo`, `checkout`, `encomendas`, `forum`, `funil`,
`gamificacao`, `identidade`, `leads`, `mensageria`, `metricas`,
`notificacoes`, `pagamentos`, `quiz`, `sugestoes` (leitura direta proibida;
só o fluxo normal de fases pela gestão).

## CRITÉRIOS DE ACEITAÇÃO

- AC-01: a aula de chapéu está publicada e acessível a quem tem matrícula
  ativa, no mesmo lugar onde a turma assiste às demais aulas.
- AC-02: quem não tem matrícula ativa não acessa a aula (a porta recusa
  explicando, como nas demais).
- AC-03: a ideia 20 está em "Em desenvolvimento" durante a produção e em
  "Implementado" no dia da publicação, com a nota contando onde a aula está —
  os 41 que acompanham são avisados por esse gesto.

## TESTES OBRIGATÓRIOS

Nenhum código novo, nenhum teste novo: obra de conteúdo. Se no meio do caminho
aparecer necessidade de código na célula `cursos`, este ChangeSpec não cobre —
nasce o CS seguinte, e valem os testes de porta fail-closed da célula.

## RISCO E ROLLBACK

Risco baixo: conteúdo aditivo. Rollback é despublicar a aula; nenhum dado de
aluno é tocado.

## DEFINITION OF DONE

- [ ] Aula gravada (Lívia) e publicada onde a turma assiste.
- [ ] AC-01 a AC-03 conferidos de fora, com o link da aula como evidência.
- [ ] Ideia 20 em "Implementado", com nota apontando a aula.
- [ ] Registro no livro de ocorrências com a evidência.

## APROVADO_POR

— (vazio até a aprovação humana explícita; a assinatura oficial é o registro
no formulário da ideia 20, e este campo recebe nome e data no mesmo dia)
