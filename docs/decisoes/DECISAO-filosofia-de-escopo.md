# DECISÃO — este projeto é para ser feito completo, não minimalista

> **Sessão com o mantenedor presente**, 25/08/2026, logo depois de a banca de
> auditoria do `PLANO-AREA-ADMIN.md` incluir, entre quatro pareceres, uma
> recomendação de começar por uma versão reduzida ("O Mirante" —
> `PARECER-BANCA-AREA-ADMIN.md` §4). O mantenedor reagiu, palavras dele,
> preservadas porque a intensidade é parte do conteúdo:
>
> *"Quero registrar em algum lugar que eu estou criando um projeto GRANDE E
> IMPORTANTE e que eu sempre vou optar por fazer algo completo, a despeito da
> demora ou do trabalho (…) foi essa a justificativa para investir os mais de
> R$ 1.000,00/mês na assinatura do Claude Code Max (…) para que os próximos
> agentes não fiquem perdendo tempo com propostas de fazer coisas que só me
> fizeram perder meses de trabalho e muito dinheiro em outros projetos que
> falharam miseravelmente devido a seguir esses conselhos tolos que apelam
> para o nosso lado de fazer as coisas rápido e fácil, mas que no final se
> revela construir sobre a areia."*
>
> Este documento é a **lei permanente** desse assunto. Ela vale para toda
> sessão, toda célula, todo despacho — não só para a área admin que a
> disparou.

---

## 1. A decisão

**Entre uma opção completa/robusta e uma opção reduzida/rápida, a opção
completa é a escolhida por padrão — mesmo custando mais tempo, mais PRs, mais
sessões do mantenedor. Isto não é ingenuidade sobre o custo: é decisão
informada, com histórico de perdas reais em outros projetos que escolheram o
caminho barato.**

**Não é decisão de agente algum reabrir isto a cada despacho.** Propor
"vamos fazer a versão mínima primeiro" como recomendação já não é mais uma
opção neutra sobre a mesa — é a opção que este documento fecha.

## 2. O que isto MUDA, concretamente

- **Nenhum agente — nem um subagente convocado para dar segunda opinião —
  recomenda escopo reduzido como forma de "economizar tempo/esforço".**
  Se um agente (ou uma "banca" com várias cadeiras) enxergar essa opção,
  pode registrá-la como análise, mas a recomendação final não a escolhe só
  por ser mais rápida.
- **Tempo estimado em "dias" ou "semanas" não é motivo para reduzir escopo.**
  O mantenedor já mediu, na prática, robôs deste projeto fazendo em minutos
  o que a estimativa tradicional chamaria de dias — não use o vocabulário de
  cronograma de equipe humana para desencorajar ambição.
- **`PARECER-BANCA-AREA-ADMIN.md` §7, pergunta 1 ("plano completo ou o
  Mirante?") está RESPONDIDA: plano completo.** A análise técnica da cadeira
  de produto continua válida como registro (o que ela descreveu sobre custo
  de oportunidade é fato, não opinião), mas a recomendação de adiar/reduzir
  está substituída por esta decisão.

## 3. O que isto NÃO muda (a ambição não é desculpa para descuido)

- **A disciplina de entrega do projeto continua inteira.** PRs pequenos,
  orçamento de 15 arquivos, uma célula por PR, Ritos de Contrato, evidência
  vermelho→verde — nada disso é "fazer rápido e fácil", é engenharia séria
  fatiada em passos seguros. Fatiar em fases não é reduzir escopo: é a forma
  responsável de construir algo grande sem quebrar o que já funciona.
  "Completo" descreve o **destino**; a escada de PRs descreve o **caminho**
  — os dois continuam de pé.
- **Bloqueio real continua sendo bloqueio real.** Custo de serviço pago,
  credencial que só o mantenedor tem, limite legal/de conformidade, ou uma
  vulnerabilidade de segurança não são "conselho de ir devagar" — são fatos
  sobre o que é possível, e continuam sendo reportados como sempre
  (`ARMADILHAS-OPERACAO.md` §1). Esta decisão é sobre **ambição de escopo**,
  não sobre fingir que restrições reais não existem.
- **A diretiva "pagamento por último" continua valendo.** Ela não é sobre
  fazer menos — é sobre ORDEM (o site vem antes da venda), decidida pelo
  mesmo mantenedor por outro motivo. As duas convivem sem conflito.

## 4. Por que isto é do tamanho de uma lei, não de uma preferência de estilo

O `CAMINHO-DOURADO.md` §0 já avisa: contexto é orçamento, e decide
arquitetura antes do código. Uma preferência tão fundamental quanto "este
projeto não aceita fundação provisória" também decide arquitetura antes do
código — por isso mora aqui, num documento que todo agente encontra, e não
só na memória de uma conversa.

## 5. Estado

**Decidido em 25/08/2026.** Vale a partir de agora, retroativo ao
`PARECER-BANCA-AREA-ADMIN.md` (a pergunta 1 do §7 dele está fechada por este
documento) e para todo despacho futuro.
