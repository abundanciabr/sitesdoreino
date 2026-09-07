---
schema_version: 2
armadilha: 378
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
sinal:
  - `turmas\.txt`
gatilho:
  - sitesdoreino-docs/turmas.txt
licao: turmas.txt e a lista ANTIGA de WhatsApp, nao a matricula da escola. O numero de alunos se le em /admin/escola/alunos/, e so o mantenedor abre essa tela: pergunte a ele em vez de estimar.
---

# O número de alunos lido de um arquivo do disco, e afirmado com voz de medição

**Sintoma:** um plano inteiro se apoia numa frase como *"a escola tem ~30
pessoas (`turmas.txt`, 30 linhas)"*, com a fonte citada entre parênteses, o que
faz a afirmação parecer uma medição. O mantenedor lê, e responde com raiva:
*"olha para um documento antigo e gritar sobre o mesmo como verdade? Ignorando o
SISTEMA que mostra que já temos mais de 140 alunos!"*.

Medido em 07/09/2026: a escola tinha **133 alunos ativos e 9 aguardando
aprovação**, lidos em `/admin/escola/alunos/`. O arquivo dizia 30. O erro não foi
de 10%, foi de 4 vezes, e ele carregava dois argumentos do plano: "faixas
visíveis fazem mal numa turma pequena" e "quórum de pares só a partir de ~150
ativos". Os dois caíram junto com o número.

**Causa:** o robô tem acesso de leitura ao disco e **não tem acesso ao banco de
produção**. Então, quando precisa de um número da operação, o que está ao alcance
da mão é um arquivo, e um arquivo com um nome plausível (`turmas.txt`, a lista
que o mantenedor usou uma vez para liberar uma turma) parece fonte. Não é: ele é
uma fotografia de um dia, de um recorte (só a lista de WhatsApp), e não envelhece
com aviso. Pior, citá-lo entre parênteses **transfere para o número a
credibilidade de uma medição** que nunca houve.

Isto é a `armadilhas/148` (ler do clone principal em vez do `origin/main`) na
camada de DADOS em vez da de código, e é primo do erro de repassar achado de
sub-agente sem conferir: em todos, o sintoma é uma frase minha saindo com a voz
de um instrumento.

**Solução:** número da operação (alunos, matrículas, pedidos na fila, dinheiro)
**se lê no sistema, e o sistema é o site**. Os endereços:

- alunos: `meshcraft.top/admin/escola/alunos/`
- a meta e a curva: `meshcraft.top/admin/placar/`
- filas de trabalho da escola: as telas de cada célula (`/pages/equipe`, `/conquistas/interno`, `/cursos/plantao`)

Nenhum deles abre para um agente: **todos exigem o crachá do mantenedor.** Então
a regra prática é esta, e ela é curta:

> Se o número decide alguma coisa no que você está escrevendo, e você não
> consegue medi-lo, **pergunte ao mantenedor em vez de estimar.** Uma caixa de
> pergunta custa segundos; um plano com o número errado por 4 vezes custa a
> confiança dele.

E se o número entrar mesmo assim, ele entra **com a fonte e a data coladas**
("133 alunos ativos, lidos em `/admin/escola/alunos/` em 07/09/2026"), nunca como
fato solto. Fonte que é arquivo do disco não vale para dado da operação, e
escrever `turmas.txt` entre parênteses não conserta isso, só disfarça.

**O que NÃO é a lição:** o problema não foi ter aberto o `turmas.txt`. Ele é
legítimo para o que ele é (a lista que ele usa para liberar gente pelo WhatsApp,
registrada na memória do projeto). O problema foi tratá-lo como censo.
