---
schema_version: 2
armadilha: 268
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `nao ha como um portao saber que a mutacao que voce escolheu foi interceptada por OUTRO guarda antes de chegar ao seu teste: as duas coisas produzem exatamente o mesmo desfecho na tela (vermelho). A cura e de METODO: ler a mensagem do vermelho e conferir que ela veio do SEU teste, e nao de um guarda anterior.`
sinal:
  - `ImproperlyConfigured` durante uma mutacao deliberada
  - `catálogo inválido — célula não sobe` num teste que nao e de catalogo
---

# A mutação deu vermelho, e mesmo assim não provou nada: outro guarda matou antes do seu teste rodar

**Sintoma.** Você está fazendo a prova por mutação que o rito exige: apaga a
regra, roda a suíte, confirma o vermelho, restaura. O vermelho aparece. Você
marca a guarda como provada e segue.

Só que a saída não é uma falha de teste. É isto:

```
django.core.exceptions.ImproperlyConfigured: [i18n] catálogo inválido — célula não sobe (D4 fail-closed):
  - avisos.js.nivel_titulo: placeholders de `pt-br` divergem do en (['nivel'] × [])
```

Nenhum `FAILED tests/...` na última linha. Nenhum nome de teste. O seu teste
**não rodou uma linha** — a célula nem subiu.

**Causa.** A mutação que você escolheu quebrou uma regra **anterior** à sua. Na
`funil` isso é quase o caso normal, porque o catálogo de traduções é
fail-closed no `ready()` (`apps/i18n/validador.py`, `armadilhas/210`): qualquer
inconsistência no YAML derruba o processo antes de o primeiro teste importar
alguma coisa. Guarda em camadas é bom desenho; o problema é que **a camada de
fora e a sua produzem o mesmo pixel vermelho na tela**, e o rito da mutação só
pede "ficou vermelho?".

É o padrão 1 da `RETROSPECTIVA-FASE-D.md` (falso-verde) virado do avesso:
falso-VERMELHO. A cerimônia foi cumprida, a conclusão está errada, e o teste
que você acabou de declarar provado pode não estar medindo nada.

**Solução, em uma frase: leia a mensagem do vermelho, não só a cor.** Na
prática:

1. **Rode a mutação com `-k <o nome do seu teste>`.** Se o desfecho é
   `1 failed`, com o nome do seu teste na linha do `short test summary`, ele
   pegou. Se é um traceback de `ImproperlyConfigured`, `ImportError` ou
   `errors during collection`, ele não chegou a rodar.
2. **Se outro guarda interceptou, escolha uma mutação MENOR — uma que o guarda
   anterior aceite.** O ponto da prova não é "quebrar de qualquer jeito", é
   chegar ao seu teste com a regra dele ausente. No caso medido, a mutação
   original punha `{nivel}` só no `pt-br`, e o validador reprovava por
   divergência de placeholder entre idiomas. A mutação que serviu punha
   `{nivel}` nos **três** idiomas e **recalculava o `_fonte`**: aí o catálogo
   fica coerente, o validador deixa passar, e só o teste novo pode pegar.
3. **Conte as duas no relatório.** A primeira também é informação boa: ela
   provou a camada de fora. O que não se pode é apresentá-la como prova da
   camada de dentro.

**A régua final:** uma mutação prova o seu teste quando o vermelho **diz o nome
dele**. Vermelho anônimo é vermelho de outra pessoa.

**Origem.** 01/09/2026, no degrau 21b da gamificação (PR #835, TAR-100), ao
provar a guarda que impede a frase do aviso do celular de pedir um parâmetro
que o `sw.js` nunca vai interpolar. Sete das oito mutações do lote nomearam o
teste que caiu; a oitava caiu no `ready()` da célula e teria sido contada como
prova se a saída não tivesse sido lida linha a linha.
