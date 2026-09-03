---
schema_version: 2
armadilha: 294
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/funil/tests/test_categorias_na_home.py
sinal:
  - `Pedir entrada` aparece para quem já entra na Caixa
  - o botão de pedir entrada abre a Caixa direto, sem formulário
---

# A tela pergunta a categoria e esquece o crachá de equipe: duas telas discordam sobre a mesma pessoa

**Sintoma:** a home oferece "Pedir entrada" a alguém que já tem acesso, e o
clique prova o erro na hora, porque o destino abre direto em vez de mostrar
formulário nenhum. Nenhum teste falha, nenhum log acusa nada, e a `alunos`
responde certo. O mantenedor encontrou isso com a conta dele em 02/09/2026,
depois de a mesma tela já ter sido consertada duas vezes por defeitos vizinhos
(28/08 e 29/08).

**Causa:** a escada de categorias (`GET /alunos/{email}/situacao`) responde
`aluno · na_fila · pausado · ex_aluno · reembolsado · cadastrado`, e **não
carrega o crachá de equipe de propósito** (`DECISAO-categorias-de-usuario`
§2.1: quem decide quem é da equipe é a lista da célula dona do recurso, na
porta dela). Quem é da equipe e nunca comprou nada é `cadastrado` de verdade.
A `alunos` não errou; a PERGUNTA da tela é que estava incompleta.

A porta linkada, porém, sabia o que a tela não sabia: o `resolver()` da Caixa
confere equipe **antes** de conferir matrícula. Enquanto as duas ordens
diferirem, a tela é capaz de discordar do próprio destino, e vai discordar.

**Solução:** a tela que oferece um caminho **espelha a ordem de conferência da
porta que ela linka**. Na prática, o ramo de equipe vem primeiro:

```django
{% if request.ator.papel == "staff" %}   {# a mesma ordem do resolver() da Caixa #}
{% elif request.ator.categoria == "aluno" %}
```

O sinal já existia e não custa consulta nova: `papel` vem da `identidade`, é
declaradamente de EXIBIÇÃO (nunca autoriza), e é o MESMO que
`apps/core/menu.py` lê para desenhar o atalho da administração. Compare contra
a string exata: qualquer outro valor cai na escada de sempre, fail-closed como
o `_plateia_confere` do menu.

**A generalização, que é o que vale para a próxima célula:** *tela que decide
o que oferecer perguntando só uma das listas que a porta consulta é uma tela
que promete o que a porta desmente.* Não é caso de home, nem de equipe: é o
padrão "garantia sem mecanismo" da `RETROSPECTIVA-FASE-D` visto de perto. A
régua ao escrever qualquer convite: **liste as conferências da porta e refaça
todas, na mesma ordem** — ou não ofereça.

**Ganho de brinde, e ele indica que a ordem está certa:** decidido o ramo pelo
crachá, a categoria nunca é lida, e o e-mail (que só era buscado para
calculá-la) deixa de atravessar a célula. Quando a ordem correta também é a
mais barata, costuma ser porque a pergunta cara era desnecessária.

**Contexto:** PR do dia 02/09/2026, célula `funil`. As três correções da mesma
tela em seis dias têm a mesma forma — a home afirmando sobre acesso algo que
outra célula decide — e é essa forma, não o caso, que a próxima tela deve
lembrar.
