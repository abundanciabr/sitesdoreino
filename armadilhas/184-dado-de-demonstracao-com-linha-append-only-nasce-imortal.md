# Dado de demonstração que toca tabela append-only nasce imortal — e a "vitrine" vira produção para sempre

**Sintoma:** você semeia dado de vitrine numa célula para o dono ver a tela cheia,
ele aprova, e na hora de limpar o `delete()` estoura:

```
django.db.utils.InternalError: HistoricoStatus e append-only; UPDATE e DELETE sao recusados pelo banco
```

Não é a sua linha que o banco recusa: é uma **linha-filha** que o `CASCADE` do
Django tentou apagar junto. O objeto que você quer remover fica preso a ela, e a
demo passa a fazer parte da produção — com voto inventado ao lado de dado de
gente de verdade.

**Causa:** a célula tem tabelas append-only defendidas por trigger no Postgres
(`BEFORE UPDATE OR DELETE`), e **um trigger não distingue cascade de comando
direto**. Na `sugestoes` são duas: `HistoricoStatus` (migration `0001`) e
`ChangeSpecAprovado` (migration `0004`). Basta o seu seed **transicionar um
status** — o caminho natural de "criar em análise e depois mover para planejado" —
para que uma linha de histórico nasça, e ela é imortal por desenho.

É `armadilhas/079` vista do outro lado: lá o problema era o cascade apagando o
que devia sobreviver; aqui é o cascade **não conseguindo** apagar o que devia
sumir. A mesma raiz — o collector do `CASCADE` não passa pelos guardas Python —
com o sinal invertido.

**Solução:** dado de demonstração **nasce no estado final, por INSERT, e nunca
transiciona.**

Na `sugestoes` isso funciona porque a trava é `BEFORE UPDATE OF status` e a
guarda do `save()` (INV-SUG10) só olha `not self._state.adding`. Criar
diretamente em `em_desenvolvimento` não fura o corredor do ChangeSpec: o corredor
guarda a **transição** `planejado → em_desenvolvimento`, que é onde o risco mora.

Três regras que fazem a demo ser removível de verdade:

1. **Marque a demo por um dado que o filtro de remoção enxerga.** Aqui é o
   domínio de e-mail `@demo.invalid` — a RFC 2606 o reserva, ele nunca resolve, e
   nenhuma pessoa real pode nascer nele por engano. Sem uma marca assim, "apagar
   a demo" vira uma lista de ids que envelhece.
2. **Apague uma a uma, com `atomic()` por item.** Em lote, UMA linha presa
   derruba a transação inteira e nada sai.
3. **Tenha um plano B que não seja o `delete()`.** Se o dono mexeu no status pelo
   painel enquanto olhava, aquela ideia ganhou histórico e é imortal — arquivá-la
   (`arquivada_em`) tira do quadro do aluno do mesmo jeito. Melhor sumir da vista
   por um segundo caminho do que ficar visível por falta dele.

E um teste-guarda que vale mais que o comentário, porque pega quem "melhorar" o
seed depois:

```python
def test_nao_cria_nenhuma_linha_append_only():
    semear()
    assert HistoricoStatus.objects.count() == 0
    assert ChangeSpecAprovado.objects.count() == 0
```

**Bônus, e é onde quase se perde tempo:** a `sugestoes` também tem
`test_so_um_modulo_cunha_identidade_no_codigo_de_producao`, que recusa **por AST**
qualquer `Identidade.objects.create/get_or_create/...` fora de
`apps/core/sessao.py`. A saída errada é acrescentar o seu arquivo à lista de
exceções — isso alarga o buraco que o invariante existe para fechar. A certa é
**passar pela porta**: `cunhar_ou_recuperar(email=…, nome=…, id_da_plataforma=…)`.
De brinde, as pessoas fictícias saem com a MESMA forma das de verdade, que é
justamente o ponto de uma vitrine.

**Visto em:** 29/08/2026, ao montar `semear_demo` para o mantenedor avaliar a
Caixa cheia dois dias antes da inauguração (`infra/semear-demo-caixa.sh` e
`.github/workflows/semear-demo-caixa.yml`).
