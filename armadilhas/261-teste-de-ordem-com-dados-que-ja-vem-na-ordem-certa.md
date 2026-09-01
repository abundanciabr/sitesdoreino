---
schema_version: 2
armadilha: 261
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `nenhum portao consegue saber que os DADOS de um teste tornam a asserção tautológica: seria preciso entender a regra que o teste quer provar e conferir se a fixture a distingue de uma regra mais fraca. A cura é de METODO, e cabe numa frase: todo guarda de ordenação nasce com a sabotagem rodada, e a fixture é escolhida CONTRA a ordem que se quer provar.`
---

# O teste de ordenação que passa sabotado, porque os dados já vinham na ordem certa

**Sintoma.** Você escreve a regra ("os marcos vêm primeiro, e depois a ordem
alfabética"), escreve o teste, ele fica verde. Depois, por disciplina, você
quebra a regra de propósito para ver o vermelho — e o teste **continua verde**.
Nada estava sendo provado.

**Medido em 01/09/2026**, no motor das conquistas. A regra era ordenar por
classe e depois por slug:

```python
key=lambda c: (c.classe != Classe.MARCO, c.slug)
```

E a fixture do teste criava `aaa-marco` e `zzz-medalha`. Com a chave inteira, a
resposta é `[aaa-marco, zzz-medalha]`. Com a chave sabotada para `key=c.slug`, a
resposta é… `[aaa-marco, zzz-medalha]`. Os dois critérios concordavam, porque os
nomes já estavam na ordem alfabética que a regra queria — o teste media a
coincidência, não a regra.

**Causa.** Ao escrever a fixture, a mão escolhe nomes que "fazem sentido"
(`aaa`, `zzz`), e sentido normalmente quer dizer *já ordenados*. A asserção
então passa por dois caminhos diferentes, e o teste não distingue o certo do
quase-certo. É a mesma família do falso-verde de `ARMADILHAS §5.10` — um
instrumento que responde OK sem ter medido —, mas mais traiçoeira: aqui o
instrumento roda, o dado é real e a asserção é honesta. O que está errado é a
ESCOLHA DO DADO.

Vale para qualquer regra com mais de um critério: ordenação, desempate,
prioridade, precedência de filtro. Sempre que a regra é "A, e depois B", uma
fixture em que A e B concordam prova apenas B.

**Solução.**

1. **Escolha a fixture CONTRA a regra.** Se o teste é "marcos primeiro, depois
   alfabético", o marco tem de se chamar `zzz-marco` e a medalha `aaa-medalha`.
   Se a única ordem que passa é a que a regra produz, a asserção tem dente.
2. **Rode a sabotagem antes de comemorar.** Remova o primeiro critério da chave
   e veja o vermelho. Guarda de ordenação que nunca foi visto vermelho é
   decoração — e este projeto já tem o rito para isso (`armadilhas/195`).
3. **Escreva no teste por que os nomes são feios.** Um comentário de uma linha
   ("os slugs são escolhidos contra a ordem alfabética de propósito") impede que
   a próxima sessão os "arrume" para nomes bonitos e devolva a tautologia.

**Por que esta entrada não tem `sinal`, e a ausência é a decisão:** o sino
reconhece uma armadilha pela SAÍDA de um comando, e a saída desta é um teste
**verde**. Não há texto para casar. A primeira versão deste arquivo tentou
`sorted(` e o gerador a recusou por curta demais — com razão: uma assinatura
assim casaria saída inocente e viraria sino tocando à toa, que é o jeito
conhecido de um sino morrer.

**A pergunta que acha isto em revisão:** *se eu apagar metade da regra, este
teste fica vermelho?* Se a resposta não for um sim óbvio, a fixture está errada.
