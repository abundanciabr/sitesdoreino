---
schema_version: 2
armadilha: 222
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o guarda existente confere PRESENÇA do nome da célula, e a única forma de mecanizar os fatos seria recalcular o mapa do disco — que é exatamente o que ele não é (resumo curado, escrito para ler, com a regra "o original vence")
sinal: null
---

# `test_painel_ia_atualizado.py` diz **2 passed** e o mapa mente sobre metade das células: guarda de presença não protege os fatos

**Sintoma.** O teste-guarda do mapa para IA passa, verde:

```
python -m pytest ci/tests/test_painel_ia_atualizado.py -q
..                                                     [100%]
2 passed in 0.06s
```

E, no mesmo commit, `painel/ia/04-arquitetura-de-celulas-e-contratos.md`
afirmava (medido em 30/08/2026, contra um mapa escrito em 27/08):

- `forum` "nasce em esqueleto", sem `LICOES.md` e sem contrato — quando a
  célula já tinha `apps/forum`, `LICOES.md` e `contracts/forum.openapi.yaml`
  com 3 operações e `freeze: required`;
- `notificacoes` "nasce sem contrato, por lei de gênese" — idem, 4 operações
  congeladas;
- "**7** células têm contrato `required` […] as outras **5** são
  `not-applicable`" — uma soma que dá **12** num projeto de **13** células, e
  cujos números certos eram 9 e 4;
- e o `INDICE.md` do mesmo diretório abrindo com "**12** microsserviços",
  listando doze nomes, sem o `forum`.

Quatro fatos falsos, três dias de idade, um teste verde o tempo inteiro.

**Causa.** O guarda mede **uma** coisa: se o *nome* de cada pasta de
`services/` aparece em algum lugar do texto concatenado de `painel/ia/*.md`.
É um `in` de substring. Ele foi desenhado para o modo de falha mais provável
(célula nova nasce, ninguém cita) e é honesto sobre isso — o próprio docstring
dele diz *"não prova que `painel/ia/` está completo ou correto"*. O perigo não
está no guarda; está no leitor: **assim que a célula é citada uma única vez,
todo fato sobre ela pode apodrecer para sempre sem que nada reprove**, e o
verde na tela convida a não desconfiar.

É o padrão 2 da `RETROSPECTIVA-FASE-D` (garantia sem mecanismo apodrece) na
sua forma mais traiçoeira: aqui **existe** mecanismo, ele **é** verde, e por
isso ninguém abre o arquivo para conferir. Vale para qualquer resumo curado
desta casa cuja lei é "se divergir do original, o original vence" —
`painel/ia/`, os `LICOES.md`, os mapas de `docs/`.

**Solução** (é de disciplina, e cabe em três gestos):

1. **Ao editar um parágrafo de um mapa curado, reconfira os fatos VIZINHOS
   contra o disco, não contra o texto.** Neste caso: `ci/manifesto-de-contratos.json`
   para saber quem tem contrato, `ls services/<celula>/apps` para o domínio,
   `grep -c operationId contracts/<celula>.openapi.yaml` para o tamanho,
   `git ls-files services/` para a contagem. Custou 4 comandos e pegou 4
   mentiras.
2. **Some as contagens escritas.** Um "7 + 5" num projeto de 13 é o detector
   mais barato que existe, não precisa de ferramenta, e estava visível a olho
   nu no documento havia três dias. Onde um texto der um total, confira o
   total.
3. **O que você não consertar, escreva que continua velho, com o número
   medido.** No mesmo PR desta entrada, o `INDICE.md` ganhou uma seção de
   revisões que declara nominalmente o que ficou por corrigir (a contagem de
   armadilhas, "~126" quando já passavam de 200). Buraco assumido é gerenciável;
   meia-verdade não — e a próxima sessão não precisa redescobrir.

**O que NÃO fazer:** apertar o guarda para comparar fatos do disco com o
texto. Isso o transformaria num gerador — e um mapa gerado deixa de ser o
resumo curado, escrito para ser lido por uma IA sem contexto, que é a única
razão de `painel/ia/` existir. O guarda de presença está no tamanho certo; o
que faltava era a entrada que você está lendo.

**Contexto:** achado durante a TAR-033 (PR 626), que acrescentou ao mapa a
célula `gamificacao` — a seção nova falava de uma "14ª célula", o que só faz
sentido se as 13 da tabela logo acima estiverem certas. Não estavam.
