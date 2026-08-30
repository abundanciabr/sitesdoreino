---
schema_version: 2
armadilha: 229
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/indice_de_armadilhas.py
sinal:
  - `casa sa[íi]da BENIGNA do dia a dia`
---

# O sino toca em cima de um PASS, porque a assinatura foi ancorada no RÓTULO de uma linha de relatório

**Sintoma.** O sino das armadilhas dispara em saída **feliz**. Você roda um
comando que terminou bem, e no meio do sucesso aparece o alarme mandando ler uma
lição sobre uma falha que não aconteceu:

```
  dívida do livro       PASS   livro em dia
🔔 SINO DAS ARMADILHAS: ... Casou: 'dívida do livro'
   LEIA armadilhas/185 ANTES de tentar de novo
```

Pior: ele toca também quando você só **lê o código-fonte** com `grep` ou `cat`,
porque a frase está escrita numa docstring. O guarda `LENDO_O_CATALOGO` cobre
`armadilhas/`, e mais nada.

**Causa.** A assinatura foi copiada do **rótulo da linha**, e não da mensagem de
falha. Um relatório desta casa (`ci/_nucleo.py::Relatorio.render`) imprime uma
linha por checagem com a forma `nome  ESTADO  resumo` — e o **nome é o mesmo nos
dois estados**:

```
  dívida do livro       PASS   livro em dia
  dívida do livro       FAIL   2 merge(s) sem registro
```

Ancorar em `d[íi]vida do livro` casa as duas. O que distingue não é o rótulo: é o
**resumo**, e o bloco de detalhe que só o FAIL imprime.

O mesmo vale para o vocabulário do domínio em geral. Uma frase que existe em
docstring, comentário ou nome de arquivo aparece toda vez que alguém lê o código,
e leitura de código não é sintoma de nada. Se a frase escolhida nunca aparece
numa mensagem de tela, a assinatura não tem verdadeiro-positivo possível: ela só
sabe errar.

**Por que importa mais do que parece.** Sino que toca à toa é sino que todo robô
aprende a ignorar — e aí ele deixa de proteger no dia em que estiver certo. É a
`armadilhas/174` na mesma família, e é exatamente o que o `CORPUS_FELIZ` de
`ci/indice_de_armadilhas.py` existe para impedir ("sino que toca à toa é ruído
que ninguém mais lê"). O buraco não estava no mecanismo: estava no **corpus**. A
saída feliz do `ci/mergear.py --conferir` não constava dele, então o gerador não
tinha como reprovar a assinatura ruim.

**Solução, em três passos — e o segundo é o que cura a classe:**

1. **Ancore no que SÓ a falha diz.** Meça, não invente: rode o comando nos dois
   estados e compare. Sirva-se do resumo (`merge\(s\) sem registro`) ou do rótulo
   **com** o estado colado (`d[íi]vida do livro +FAIL`). Prefira espaço literal a
   `\s+`, senão a assinatura atravessa a quebra de linha e casa o `FAIL` de outra
   checagem.
2. **Acrescente a saída feliz ao `CORPUS_FELIZ`.** Enquanto ela não estiver lá, o
   gerador aceita a próxima assinatura ruim do mesmo jeito. Copie o texto do que o
   programa imprime de verdade (monte com as funções de produção), não do que você
   acha que ele imprime.
3. **Varra o catálogo inteiro contra o corpus ampliado.** Uma entrada consertada
   não cura a classe.

**Como saber se a assinatura presta, numa pergunta:** *esta frase pode aparecer
num dia em que está tudo certo?* Se puder — inclusive por alguém dar `cat` no
arquivo onde ela está escrita —, ela não serve.

**Origem.** 30/08/2026, TAR-038. A `armadilhas/185` declarava
`d[íi]vida do livro` e `merges que ningu[ée]m contou`. O primeiro tocou 3 vezes
numa sessão (TAR-033 / PR 626) e mais 4 na sessão do conserto, sempre sobre um
`PASS`; o segundo só existe em docstring de `ci/divida_do_livro.py` e num
comentário de `services/admin/config/urls.py`, e foi removido por não ter acerto
possível. Conserto e provas no PR
<https://github.com/abundanciabr/sitesdoreino/pull/642>; registro
`painel/registros/20260830-080-o-sino-de-alerta-tocava-em-cima-de-mensagem-de-sucesso.js`.
