---
schema_version: 2
armadilha: 342
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  detector: services/admin/tests/test_caixa_analise.py::test_o_voto_que_muda_na_caixa_muda_na_tela
  motivo: pede a mesma tela duas vezes com números diferentes na fonte e exige que a segunda não repita a primeira
sinal:
  - `analise as sugestões e liste tudo num documento`
  - `me manda um relatório com os números`
---

# Análise entregue como documento congelado mente no dia seguinte

**Sintoma.** O mantenedor pede uma análise ("liste as sugestões da turma, da
mais votada para a menos votada, com o que precisa ser feito"). Você entrega um
documento bonito e correto. Uma semana depois ele abre o mesmo documento para
decidir alguma coisa e decide pelo número errado: dois alunos votaram, uma ideia
foi arquivada, três chegaram novas. Nada acusa nada. O documento continua
bonito e correto sobre um dia que passou.

**Causa.** Análise mistura duas coisas de naturezas opostas, e entregar as duas
juntas congela a que não podia congelar:

    FATO        voto, plateia, etapa, o texto do aluno, quem comentou
                muda sozinho, sem ninguém tocar no documento

    JULGAMENTO  por que isto importa, o que é preciso, com o que se junta
                só muda quando alguém pensa de novo

Um documento guarda os dois do mesmo jeito. E a lei anti-duplicação do
`CLAUDE.md` já dizia o que ia acontecer: *nenhum fato do projeto mora em dois
lugares*. Um "40 votos" escrito na prosa é a segunda cópia de um número que já
mora na Caixa, e ela deriva no primeiro voto.

O caso que gerou esta entrada, em 05/09/2026: 28 ideias analisadas e entregues
como página fora do site. Ela nasceu certa e com data de validade — a mais
votada tinha 40 votos naquele minuto, e a frase "72% dos votos pedem gravação"
era verdade sobre aquele minuto.

**Solução: fato vivo, julgamento guardado.** A entrega vira uma tela; o texto
escrito à mão nunca contém um número:

```python
# apps/core/analise_da_caixa.py — o julgamento, sem um único número
ANALISE = {
    20: {"familia": "cabelos", "mesa": "gravacao",
         "importa": "Acessório é o par natural do produto que a escola mais "
                    "ensina a vender...",
         "precisa": "Gravar uma ou duas aulas e publicar..."},
}

# e os números, todos calculados na abertura:
familia["votos"] = sum(i["votos"] for i in membros)
```

Três consequências que vêm de graça, e que o documento nunca teria:

1. **a ordem se refaz sozinha** quando a turma vota de novo;
2. **ideia que chega depois aparece**, na própria seção, dizendo que ainda não
   foi lida (o laço é sobre o que a fonte responde, nunca sobre o dicionário);
3. **ideia arquivada some**, porque a fonte deixou de respondê-la.

**A régua, para a próxima vez.** Antes de escrever qualquer entrega, pergunte:
*este texto tem número dentro?* Se tem, ele não é documento — é tela. E a
frase que fica: **prosa com número dentro é fotografia; quem pede análise quer
espelho.**

**Onde a lei mora:** `docs/decisoes/DECISAO-onde-mora-o-que-eu-entrego.md` e a
seção correspondente do `CLAUDE.md`.
