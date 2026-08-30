# O balcão da fila não sabe escrever `bloqueada` — o RITOS manda um gesto que o CLI não tem

**Sintoma:** o seu despacho travou em algo que só o mantenedor decide. O
`RITOS.md` §5 item 3 é explícito sobre o que fazer:

> Travou em algo que só o mantenedor decide? Evento `bloqueada` com o motivo e
> devolva à maestro.

Você vai fazer o gesto e não acha o verbo:

```
$ python ci/fila.py --help
usage: fila.py [-h] {criar,listar,pegar,soltar,concluir,validar} ...
```

Nenhum `bloquear`. E `soltar --motivo "..."` **não serve**: ele escreve o evento
`devolvida`, que o `calcular_estados` lê como "voltou para a fila, qualquer um
pode pegar" — exatamente a mensagem errada quando a tarefa está esperando uma
decisão do dono. Duas horas depois outra sessão pega a tarefa, refaz a
investigação inteira e trava no mesmo lugar.

**Causa:** o modelo de estados conhece `bloqueada` — ela está em
`EVENTOS_DE_CICLO`, tem constante própria (`BLOQUEADA`), tem ramo em
`calcular_estados` e o validador até **exige** `detalhe` nela
(`"'bloqueada' sem 'detalhe' não conta a história — diga o motivo"`). O que não
existe é a porta: nenhum `sub.add_parser("bloquear", ...)` em
`construir_parser()`. Os eventos `bloqueada` que já estão em `fila/eventos/`
nasceram todos da sessão de semeadura da fila (29/08/2026), que escreveu em
lote, por dentro — nunca pelo balcão.

É a **Classe 2** da `docs/decisoes/RETROSPECTIVA-FASE-D.md` em estado puro:
garantia declarada (a lei manda o gesto), mecanismo ausente (o balcão não o
oferece). Nada reprova, porque ler nunca dá erro.

**Solução, enquanto o verbo não existe:** chame a mesma função interna que os
outros verbos chamam, em vez de montar o JSON à mão — o formato do nome do
arquivo, o `quando` em UTC com `timespec="seconds"` e o campo `arquivo` idêntico
ao stem são conferidos pelo validador, e errar qualquer um deles reprova a
muralha da fila:

```python
import importlib.util, sys
from pathlib import Path

RAIZ = Path("/caminho/do/seu/worktree")
spec = importlib.util.spec_from_file_location("fila", RAIZ / "ci" / "fila.py")
fila = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(RAIZ / "ci"))
spec.loader.exec_module(fila)

fila._escrever_evento(
    RAIZ, "TAR-NNN", "bloqueada", "sessao-<area>-<data>",
    detalhe="por que travou, e o que destrava",
)
fila._soltar_reserva_se_houver(RAIZ, "TAR-NNN")   # ⟵ NÃO ESQUEÇA
```

**A segunda linha é a que se esquece, e ela morde.** `cmd_soltar` e
`cmd_concluir` soltam a reserva do almoxarife antes de escrever o evento;
escrevendo o evento por fora, a reserva do servidor fica de pé até expirar
sozinha em 3h. Nesse intervalo a tarefa aparece como `bloqueada` para quem lê o
evento e como reservada para quem lê o servidor — duas verdades sobre a mesma
tarefa, que é a doença que a fila inteira existe para não ter.

Depois, confira pelo estado CALCULADO, nunca pelo arquivo que você acabou de
escrever:

```bash
python ci/fila.py validar     # a muralha
python ci/fila.py listar      # a linha da sua tarefa tem de dizer [bloqueada · quem] + motivo
```

**A cura definitiva** é um `sub.add_parser("bloquear", ...)` com `--motivo`
obrigatório (o validador já exige `detalhe`, então o CLI recusar sem motivo só
antecipa a mesma recusa para onde ela ensina), chamando as duas funções acima na
ordem de `cmd_soltar`. Enquanto ela não vier, esta entrada é a ponte — e o
`RITOS.md` §5.3 continua sendo uma lei sem mecanismo.

**Origem:** despacho TAR-014 (`sugestoes`, "aposentar as telas antigas de
moderação da Caixa"), 30/08/2026 — a tarefa travou numa emenda de contrato que
só o mantenedor autoriza, que é o caso exato que a §5.3 nomeia, e o gesto que
ela manda fazer não tinha caminho.
