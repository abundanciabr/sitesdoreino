# Guarda que usa o objeto medido como régua não mede nada

**Sintoma:** existe um teste-guarda, ele passa, o documento diz que a garantia está
"corrigida com guarda que morde" — e sabotar a coisa guardada **não deixa nada
vermelho**. Diferente do teste que não existe (que ao menos se percebe pela ausência),
este é pior: ele ocupa o lugar do guarda de verdade e faz a auditoria seguinte pular a
linha.

**O caso, medido em 26/08/2026 com Postgres real.** O guarda do fuso da célula
`sugestoes` — justamente a célula onde o defeito do fuso foi DESCOBERTO (EVO-21) —
comparava a página renderizada com o resultado de `timezone.localtime(...)`:

```python
corpo = dentro.client.get(reverse("avisos")).content.decode()
esperado = timezone.localtime(aviso.criado_em).strftime("%d/%m/%Y %H:%M")
assert esperado in corpo
```

Apagando `TIME_ZONE` do `config/settings.py`, os dois lados vão juntos para
`America/Chicago` e a igualdade se mantém:

```
guarda ancorado (novo) → 1 failed: offset -1 day, 19:00:00 (America/Chicago)
guarda pela régua      → 1 passed          ← o falso-verde
```

**Causa:** o valor esperado foi calculado com **a mesma função** cujo comportamento o
teste quer provar. A régua se move junto com a peça medida, e a comparação vira uma
tautologia — sempre verdadeira, independentemente da configuração.

Repare que o teste não estava *errado*: ele prova o **formato** (`d/m/Y H:i` em vez de
`Aug. 24, 2026, 9 a.m.`) e prova que o template respeita o fuso configurado, seja ele
qual for. O defeito é o **nome e a promessa** — ele se chamava
`test_a_data_do_aviso_sai_no_fuso_...` e a tabela de dívidas acreditou.

E o motivo pelo qual alguém escreve isso é sensato, o que torna a armadilha traiçoeira:
o próprio docstring dizia *"nunca com uma string escrita à mão, que envelheceria no dia
seguinte"*. Fugir de um valor fixo que envelhece é bom instinto — mas a saída certa não
é usar a conversão como régua; é ancorar num instante ESCOLHIDO, que não envelhece
porque não depende de hoje.

**A regra, em uma frase: o valor esperado de um guarda nunca pode ser produzido pelo
mecanismo que o guarda existe para vigiar.**

**A cura, em três perguntas antes de dar o teste por pronto:**

1. **A régua é independente?** Se o valor esperado sai de uma função da coisa testada,
   pare — escreva o valor à mão, ancorado (`timedelta(hours=-3)`, `"25/08/2026 01:00"`).
2. **Eu sabotei e vi vermelho?** Não "eu acho que ficaria vermelho". Apague a linha,
   rode, LEIA a mensagem, reponha. É a evidência vermelho→verde da Lei 6, e ela existe
   exatamente para pegar isto.
3. **A mensagem de falha aponta o conserto?** `assert local.utcoffset() == timedelta(
   hours=-3), 'Falta TIME_ZONE = "America/Sao_Paulo" em config/settings.py?'` manda a
   próxima pessoa direto ao arquivo.

**A família.** É o mesmo gênero do `@if [ -f .importlinter ]` que o guarda-dos-guardas
fechou em 25/08 (apagar o arquivo apagava o guarda junto) e do teste que afirma
`settings.TIME_ZONE == "America/Sao_Paulo"` (prova que a linha existe, não que a hora
sai certa — `armadilhas/099`). Nos três, a garantia é circular: quem sabota a peça
sabota a medição no mesmo gesto. **Categoria** (`RETROSPECTIVA-FASE-D`): falso-verde,
lado *garantia sem mecanismo*.

**E a lição de auditoria, que é a parte cara:** a tabela de dívidas §9 dizia
"corrigidas **com guarda que morde**" para uma célula cujo guarda não mordia. Frase de
documento não é medição. Ao declarar uma dívida fechada, **conte os guardas em disco e
sabote um por um** — foi assim que este apareceu, dois dias depois de ter sido escrito.

**Origem:** auditoria de fechamento da dívida do fuso, 26/08/2026 — 5 células ganharam
a linha (PRs #233–#238) e a conferência final encontrou 2 células sem guarda nenhum
(#239, #240) e 1 com guarda que não mordia (#241).
