---
schema_version: 2
armadilha: 388
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - docs/decisoes/PLANO-PAINEL-DE-GESTAO.md
  - docs/decisoes/
guarda:
  tipo: nenhum
  motivo: o conserto e tirar o estado dos planos e faze-los apontar para o livro, e isso e uma passada por todos os docs/decisoes/ que ainda nao foi feita; ate la o que existe e esta licao
sinal:
  - "espera pel[oa] mantenedor"
  - "pend[eê]ncia dele"
licao: Plano da casa descreve o que se PRETENDIA, nunca o que aconteceu. Antes de pedir qualquer coisa ao mantenedor por causa de uma lista de "o que espera por ele" num `docs/decisoes/`, procure no livro (`grep -rl` em `painel/registros/`) se ele ja fez. Duas vezes eu pedi o que estava pronto ha cinco dias.
---

# O plano guarda estado, o mundo anda, e você cobra do dono uma pendência já paga

**Sintoma.** Você lê um plano da casa, encontra a seção "o que espera pelo
mantenedor", e abre uma caixa pedindo aquilo. Ele responde que já fez. Ou pior:
responde *"eu já disse"*, porque a decisão que o plano ainda registra como
aberta foi tomada por ele dias atrás, em sentido contrário.

Nada fica vermelho. Nenhuma muralha reprova. O plano está versionado, foi
escrito pela casa, e você acabou de lê-lo inteiro.

Medido em 07/09/2026: o `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §10 listava
"a chave da Anthropic" como item 5 da lista de pendências dele. A chave estava
instalada e **respondendo em produção desde 02/09** (registros `20260902-046` e
`20260902-048`, três `POST /forum/t/11/gerar-resposta` com 200). Cinco dias. No
mesmo passo, o §10 item 4 me fez reabrir a pergunta "como você conheceu a
escola?", que ele havia recusado em 05/09.

**Causa.** É a lei do livro violada por dentro de um documento que ninguém
suspeita: **"nenhum fato mora em dois lugares"**. A seção "o que espera pelo
mantenedor" de um plano é uma LISTA PARALELA do que já mora em
`painel/registros/` como registro `pendencia` com `precisa_do_dono: true`. A
lista do livro se fecha sozinha (o registro de `resposta` com `responde_a`
apaga a cobrança na Central de Pendências); a lista do plano não se fecha
nunca, porque fechá-la exigiria alguém abrir um PR só para isso, e ninguém abre
PR para consertar uma frase que não está quebrando nada.

Prosa de plano é intenção. Só o livro é acontecimento.

E há uma segunda perda, silenciosa e do lado bom: **enquanto a pendência falsa
está escrita, o trabalho que ela bloqueava fica invisível.** O degrau 16 do
mesmo plano ("o robô analista") tinha as três dependências no ar desde 05/09 e a
chave desde 02/09. Ele estava livre, e ninguém percebeu, porque o plano dizia
que ele esperava por ele.

**Solução.**

1. Antes de pedir QUALQUER coisa ao mantenedor com base num plano, procure o
   desmentido no livro. Custa segundos:

   ```bash
   grep -rli "<a coisa que voce ia pedir>" painel/registros/ | sort | tail -5
   ```

2. Quando o plano e o livro discordam sobre o que ACONTECEU, **o livro vence,
   sempre.** Quando discordam sobre o que se PRETENDE, o plano vence. A régua é
   o tempo verbal da frase.

3. Achou a divergência? Corrija o plano no mesmo PR do trabalho, como a lei do
   mapa para IA já manda para o `painel/ia/INDICE.md`. Um plano que mente uma
   vez vai mentir para o próximo robô também.

4. E procure o presente escondido: pendência falsa costuma estar segurando um
   degrau que já podia ter sido construído. Depois de derrubar a pendência,
   releia as dependências dos degraus bloqueados por ela.

**Primo de:** `armadilhas/148` (o reconhecimento acontece no espelho velho e
você projeta para um sistema que não existe mais) e `armadilhas/378` (o número
de alunos lido de um arquivo do disco em vez do sistema). A família toda é a
mesma: **uma fonte que parece autoridade porque está no repositório, e que
descreve um mundo que já mudou.**
