# `{# … #}` do Django comenta UMA linha — a de baixo vai para a página

**Sintoma:** um comentário de template escrito em várias linhas **aparece na tela do
usuário**. Sem erro, sem aviso, sem log: a página renderiza normalmente e o texto do
comentário está lá, no meio do conteúdo.

```django
{# comentário de quatro linhas
   escrito assim vai INTEIRO
   para dentro da página, e o
   navegador mostra o texto #}
```

**Causa:** `{# … #}` é comentário **de uma linha só**. O Django fecha o comentário no
fim da linha; tudo que vem depois é conteúdo comum de template. Multi-linha exige
`{% comment %} … {% endcomment %}`.

**O que torna isto caro é o modo de falha:** silencioso e visível. Nenhum portão de
CI olha para prosa dentro de HTML, então só um teste que por acaso procure aquele
texto pega — ou o usuário.

**Solução:**

```django
{% comment %}
comentário de quantas linhas você quiser,
e nada disto chega ao navegador
{% endcomment %}
```

**Por que isto merece entrada própria** (medido em 24/08/2026, despacho EVO-13 da
célula `sugestoes`): o comentário vazado explicava **o crachá da equipe**, e vazou
para dentro da página do **aluno**. Quem pegou foi um teste-guarda que procurava
outra coisa — ele afirmava que o aluno não vê o link de moderação, e conferia pelo
**texto** "moderação" no corpo da resposta. **Se a asserção fosse só pelo `href`, teria
passado**, e a página do aluno teria ido para produção explicando como funciona o
controle de acesso da equipe.

**A lição que generaliza, e vale mais que a sintaxe:** guarda de "o usuário X não vê
Y" deve afirmar sobre o **corpo renderizado**, não sobre o elemento que você imagina
que carrega o Y. Vazamento não escolhe a tag que você previu.

**Origem:** despacho EVO-13 (`sugestoes`, moderação da equipe), 24/08/2026 — não coube
no orçamento daquele PR, registrada pela sessão-maestro no fechamento do Lote 1.
