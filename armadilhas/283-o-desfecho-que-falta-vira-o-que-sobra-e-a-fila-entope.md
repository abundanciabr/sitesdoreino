---
schema_version: 2
armadilha: 283
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  motivo: o guarda é por caso, não por portão — `services/mensageria/tests/test_jornadas_canais_e_fila.py` prova que a recusa definitiva avança e que a falha transitória NÃO avança; nenhum varredor genérico sabe dizer quais desfechos uma máquina de estado deveria ter
sinal:
  - inscrição/pedido/tarefa com `estado` parado e o relógio (`proximo_em`, `next_run_at`) intacto depois de várias passadas
  - a varredura processa sempre as mesmas linhas e quem chegou depois nunca é alcançado
  - nenhuma exceção, nenhum log de erro — só uma fila que não anda
---

# O desfecho que você não nomeou vira "o que sobra", e é ele que entope a fila

**Sintoma.** Uma varredura periódica roda, não dá erro nenhum, e mesmo assim
parte das linhas nunca progride. Depois de dias:

```
estado='andando'  passo_atual=0  proximo_em=(não mudou)
```

E, do lado de fora, o estrago que ninguém liga ao primeiro: **quem entrou depois
para de ser atendido**. Encenado com uma fila de 3 vagas e 3 linhas presas na
frente, o registro novo foi atendido `[]` — zero vezes em 14 passadas, sem uma
linha de erro.

**Causa.** A varredura tinha dois desfechos escritos e **três acontecendo**:

```python
if entregou_algum:
    avancar(...)                    # saiu
elif adiar_para is not None:
    inscricao.proximo_em = adiar_para   # foi adiado
# e o terceiro caso cai aqui, no vazio, sem ninguém tocar no relógio
```

O terceiro caso era **a pessoa ter recusado** (preferência silenciada). A régua
barra por preferência **sem** reagendar, e isso é deliberado: *"silenciado é
silenciado, remarcar para amanhã seria insistir"*. A intenção estava certa e o
efeito era o oposto dela — sem desfecho próprio, "não reagenda" virou
**"reexamina e rebarra de cinco em cinco minutos, para sempre"**.

O que torna isto caro não é a linha presa: é que ela fica **na frente da fila**.
A varredura ordena pelo mais antigo e leva as primeiras `LOTE` (200 aqui). Linha
presa é sempre a mais antiga e está sempre na hora, então ocupa a vaga
permanentemente. No dia em que `LOTE` pessoas silenciarem alguma coisa, o motor
**para de atender gente nova, em silêncio**.

E há um efeito de terceira ordem que só aparece quando se conhece o modelo: a
trava parcial da `Inscricao` vale enquanto o estado é `andando`. Uma linha presa
nesse estado tranca a pessoa **fora** daquela jornada para sempre — desfazendo
justamente a correção que a `condition=Q(estado="andando")` existia para
garantir (VEREDITO das sequências, §1.1).

**A distinção que resolve, e ela é o conserto inteiro:** "nada saiu" tem duas
causas, e elas pedem coisas opostas.

| causa | natureza | o que fazer com o relógio |
|---|---|---|
| a pessoa **recusou** (preferência, opt-out) | definitiva | **avance** — não insista, e não a sequestre na sequência |
| o **despacho falhou** (Redis fora, provedor mudo) | transitória | **não avance** — o passo continua devendo, a próxima passada tenta |

Tratar as duas como a segunda prende quem recusou. Tratar as duas como a
primeira é pior: uma queda de minutos faria a plataforma **pular avisos em
silêncio**. Por isso o conserto nomeia as duas, e o teste guarda os dois lados.

**Solução.**

```python
entregou_algum = False
adiar_para = None
falhou_o_despacho = False      # a terceira coisa, com nome próprio
...
if entregou_algum:
    avancar(inscricao, passo)
elif adiar_para is not None:
    inscricao.proximo_em = adiar_para
    inscricao.save(update_fields=["proximo_em"])
elif falhou_o_despacho:
    pass                        # transitório: o relógio NÃO anda, de propósito
else:
    avancar(inscricao, passo)   # recusa definitiva: segue a jornada
```

**A régua que generaliza, e vale para qualquer varredura desta casa** (relay de
outbox, fila de merge, reprocesso de PEL): **toda passada que examina uma linha
precisa terminar tendo mexido no relógio dela — ou tendo dito, em código, por que
não mexeu.** O `else` implícito é onde mora o laço infinito silencioso, e ele não
aparece em teste de caminho feliz porque o caminho feliz sempre mexe no relógio.

**Como isto foi achado.** Revisão pedida pelo mantenedor logo depois de três PRs
grandes entrarem no mesmo dia (#845, #851, #854, o motor das jornadas). Nenhum
teste da suíte original cobria o caminho da recusa por preferência ponta a ponta
— os 108 testes estavam verdes, e estavam certos sobre o que mediam. É o padrão
"falso-verde" da `RETROSPECTIVA-FASE-D.md` na sua forma mais barata de evitar:
não um teste errado, um caminho **não testado**.

**Irmã:** `armadilhas/284` (a mesma revisão, o mesmo dia) — o teto que contava a
própria mensagem. As duas nasceram do mesmo hábito de leitura: perguntar, de cada
guarda, *"o que ele faz quando NADA acontece?"*
