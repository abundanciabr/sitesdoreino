---
schema_version: 2
armadilha: 356
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum mecanismo reprova esta edição. `python ci/fila.py validar` valida cada arquivo de tarefa em si (molde, campo obrigatório, dependência que existe, ausência de ciclo) e NUNCA o compara com a versão anterior; a `ci/muralha-da-fila.sh` só repassa o veredito desse mesmo comando, e nenhuma outra muralha olha o diff de `fila/tarefas/`. Fechar o buraco exige um guarda NOVO, que leia `git diff origin/main...HEAD -- fila/tarefas/` e recuse mudança em qualquer campo que não seja `depende_de`. Enquanto ele não existir, o que segura a lei é a declaração no corpo do PR, e é por isso que ela é obrigatória aqui
sinal:
  - depende_de
  - corrente errada
  - o arquivo da tarefa nunca muda depois de criado
  - "nada se edita, corrigir"
---

# 356 — Corrente errada na fila: não existe evento que a conserte, e cancelar é pior que editar

**Data:** 05/09/2026 · **Onde:** `fila/tarefas/`, `ci/fila.py` · **Custo
evitado:** catorze tarefas recriadas à mão para consertar duas linhas, e uma
escada inteira travada esperando um número morto

## Sintoma

O `depende_de` de uma tarefa que JÁ EXISTE na fila está errado, e você precisa
consertá-lo. Foi o que aconteceu com as 16 tarefas do portfólio do aluno
(TAR-178 a TAR-193): elas nasceram encadeadas em linha reta, e duas dessas
correntes eram falsas. A TAR-180 (o provisionamento, que o
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §5 manda ser "SOZINHO") estava
pendurada na TAR-179, e a TAR-191 (os guias no editor de documentos) estava
pendurada na TAR-190, com quem não tem relação nenhuma.

O quadro não mente sobre isso: ele calcula certinho a corrente que está escrita.
O que está errado é a corrente.

Aí você abre o `ci/fila.py` para descobrir como se corrige, e a lei fecha a
porta com todas as letras:

```
linha 18:     o arquivo da tarefa nunca muda depois de criado, e a coluna
              do quadro é sempre calculada da cadeia de eventos + reservas + PRs
linhas 31-33: O molde é o do livro: fonte multiescritor (...),
              nada se edita, corrigir é acrescentar.
```

## Causa

**A lei proíbe editar e não oferece caminho nenhum para esta classe de erro.**
Três medições, feitas no código em 05/09/2026, e a conclusão delas inverte a
leitura apressada:

1. **O vocabulário de eventos é FECHADO** (`ci/fila.py` linhas 65-67,
   `EVENTOS_VALIDOS`): `reivindicada`, `devolvida`, `bloqueada`, `concluida`,
   `cancelada`. **Nenhum deles muda uma corrente.** O comentário ali diz que
   evento fora da lista é arquivo inválido, e não vocabulário novo. Não existe
   "acrescentar" que corrija um `depende_de`.

2. **Cancelar e recriar deixa a vizinha travada para sempre.** Em
   `calcular_estados`, a dependência só deixa de bloquear quando está
   CONCLUÍDA:

   ```python
   # ci/fila.py, linha 565
   if dep in tarefas and estado_de(dep)["estado"] != CONCLUIDA
   ```

   Uma tarefa `cancelada` continua existindo em `tarefas` e o estado dela nunca
   é `CONCLUIDA`, então ela bloqueia a vizinha para sempre. E isso não é um
   detalhe de tela: `cmd_pegar` recusa qualquer tarefa cujo estado não seja
   exatamente `NA FILA` ("Só tarefa NA FILA se pega"). Cancelar a TAR-180
   deixaria a TAR-181 literalmente impossível de pegar no balcão, esperando um
   número morto.

3. **Numa escada encadeada o estrago é em cascata.** A corrente do portfólio é
   180 → 181 → 182 → ... → 193, cada uma apontando para a anterior. Recriar a
   TAR-180 com um número novo obriga a TAR-181 a apontar para esse número
   novo — e apontar para outro número é justamente a edição proibida, então a
   181 também tem de ser recriada, e a 182 atrás dela, até a 193.
   **Catorze tarefas recriadas para consertar duas linhas.** O caminho "pelo
   livro" era o mais destrutivo dos dois.

**A leitura que sustenta a edição: a imutabilidade do arquivo é sobre ESTADO,
não sobre DEFINIÇÃO.** A frase vizinha, na mesma linha 18, diz isso: *"não
existe campo `status` em lugar nenhum"*. Quem pega, devolve, bloqueia ou conclui
escreve EVENTO, nunca campo, e é por isso que a fila é imune a conflito e nunca
tem duas versões da verdade. O `depende_de` não é estado: é a definição da
tarefa, escrita por quem a criou, e definição errada não tem evento que a
corrija.

## Solução

**Edite o `depende_de` no arquivo da tarefa, e DECLARE no corpo do PR por que a
edição é legítima.** A declaração não é formalidade: como não há guarda, ela é
a única coisa que impede o precedente de virar licença. O corpo do PR
[#1139](https://github.com/abundanciabr/sitesdoreino/pull/1139) é o exemplo
pronto para copiar. Ela tem três partes:

1. **Por que é legítimo:** estado contra definição, com a citação das linhas 18
   e 31-33, e as três medições acima que mostram que o caminho append-only não
   existe para esta classe.
2. **O que a edição NÃO autoriza.** Só o `depende_de` se corrige assim. Título,
   `evidencia_exigida`, `despacho`, `toca`, `cria`, `move`, `origem` e
   `criada_em` continuam intocáveis: quem editasse um deles mudaria a
   tarefa debaixo de quem já a pegou, ou apagaria a prova que o `concluir` vai
   cobrar. E `depende_de` de tarefa alheia, que outra sessão está tocando, não
   se edita: manda um recado (`armadilhas/349`).
3. **Que a lacuna existe**, dita na cara, com a frase de que nenhum portão
   reprova esta edição.

**O que NÃO fazer:** não emende o cabeçalho do `ci/fila.py` para "abrir exceção"
no meio de uma tarefa de escada. Ele é caminho CODEOWNERS, e mudar a lei da fila
é decisão do mantenedor, não efeito colateral de um conserto de corrente.

**Prova de que o conserto funciona**, e é barata:

```bash
python ci/fila.py validar          # o molde e a ausência de ciclo continuam de pé
python ci/fila.py listar --ao-vivo # a tarefa saiu de "bloqueada" e virou "na fila"
```

No PR #1139: `181 tarefa(s), 294 evento(s)` válidas, TAR-180 e TAR-191 em
`na fila` na hora, `51 passed` em `ci/tests/test_fila.py`, e a corrente
legítima vizinha (TAR-181 esperando a TAR-180) conferida e não presumida.
