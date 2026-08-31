---
schema_version: 2
armadilha: 237
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: "nenhum portao consegue saber que um fato dito em conversa contradiz um paragrafo de outro documento; so quem esta lendo os dois no mesmo dia percebe. Degrau 1: leitura."
sinal: null
---

# A resposta do mantenedor invalidou uma lei promulgada horas antes — e o agente nem estava perguntando sobre ela

**Sintoma.** Você faz uma pergunta rotineira de escopo ("para quem vai a
mensagem quando o aluno tem menos de 13 anos?") e a resposta não escolhe nenhuma
das opções: ela **derruba a premissa** ("só temos alunos acima de 18 anos, não
temos e nem teremos alunos menores de idade"). O trabalho da sua tarefa fica
mais simples. E, sem que nada acuse, **um documento-lei em outra pasta do
repositório acabou de ficar sem sujeito** — inteiro.

**Caso medido — 30/08/2026.** Durante o plano das sequências de mensagens, a
quarta pergunta ao mantenedor era sobre menores. A resposta acima chegou com
pedido explícito de registro. No mesmo dia, horas antes, `DECISAO-gamificacao.md`
§9 (*"Menores, e o que isso obriga"*) tinha sido promulgado depois de seis
rodadas de consultoria externa, construindo **Modo Júnior como trava de
sistema**, marcos de dinheiro restritos a 13+ e validação sempre por adulto da
equipe. Nenhuma das duas coisas sabia da outra.

**Por que passa despercebido.** As três formas de errar aqui são todas
confortáveis:

1. **Não notar.** Você atende o pedido, o plano fica correto, e a contradição
   dorme até um robô chegar na escada da gamificação — semanas depois, sem esta
   conversa no contexto — e construir dezenas de arquivos de proteção de criança
   para uma escola sem crianças. É a Classe 8 (mapa velho) com um agravante:
   o mapa envelheceu em **horas**, não em meses.
2. **Revogar sozinho.** Você percebe, acha óbvio, e reescreve o §9 no mesmo PR
   "já que é evidente". Não é evidente: aquele parágrafo também guardava regras
   que **nada tinham a ver com idade** (moderação humana antes de publicar, sem
   mensagem privada entre alunos, links só de lista permitida). Revogar em bloco
   teria levado junto proteções boas para adulto — e teria feito o agente
   legislar.
3. **Só registrar e seguir.** Abrir a pendência no livro e ir embora parece
   correto e é meio-correto: o pedido fica na caixa "Precisa de você", mas o
   mantenedor não vê o **custo** de deixá-lo parado, e a lei continua mandando
   construir.

**Solução — os quatro passos, nesta ordem:**

1. **Obedeça a resposta na SUA tarefa**, imediatamente. Ela é fato do negócio.
2. **NÃO revogue a lei alheia.** Enquanto o mantenedor não decidir, ela é lei
   escrita — mesmo contradita por ele em conversa. Uma frase no chat não é uma
   emenda.
3. **Abra a pendência com o custo de não decidir escrito** (`precisa_do_dono:
   true`, e o campo `se_eu_nao_decidir` dizendo *o que os robôs vão construir* se
   ficar parado). Foi isso que transformou a pendência em decisão no mesmo dia,
   e não em item de caixa.
4. **Ofereça a régua da revisão, não só a revisão.** A pergunta que funcionou
   não foi *"revogo o §9?"* — foi *"revisar guardando o que serve para adulto,
   apagar tudo, deixar como está, ou depois?"*. Separar "o que era sobre idade"
   de "o que era sobre comunidade" é o trabalho, e é o que evita o erro 2.

**A dívida que sobra, e que também é regra:** o mesmo fato costuma estar escrito
em `contracts/`, e contrato **não se corrige de carona** — só por Rito de
Contrato (RITOS §3), em PR só de `contracts/` com a etiqueta `contrato`. Anote a
dívida dentro da lei que você emendou, para o próximo rito. No caso medido, a
descrição de `notificacao.devida.v1.json` continua dizendo *"nunca em horário
escolar"*.

**E o que você NÃO conferiu, diga.** Uma emenda pontual não é uma varredura: no
caso medido, nenhum outro documento foi lido atrás da palavra "menor". Dizer
isso no registro é o que impede a próxima sessão de acreditar que o repositório
inteiro já foi limpo.

**Origem.** 30/08/2026, sessão do plano das sequências de mensagens para os
alunos. Pendência: `painel/registros/20260831-008`; emenda e fechamento:
`20260831-009`.
