---
schema_version: 2
armadilha: 282
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: teste
  detector: services/mensageria/tests/test_jornadas_voz.py
  motivo: "test_a_carta_chega_ao_stream_logo_depois_do_commit mede o efeito do on_commit (a carta JÁ no stream, published_at preenchido) e afirma que uma chamada extra ao relay devolve 0; test_o_relay_leva_a_carta_que_ficou_pendente cobre o outro caminho, emitindo sem on_commit. Os dois juntos impedem que alguém 'conserte' o relay por causa de um zero que é sucesso."
sinal:
  - "assert 0 == 1" logo depois de um `varrer`/`criar` com `transaction=True`
  - relay que devolve 0 num teste onde o evento existe
---

# Com `transaction=True`, o `on_commit` JÁ rodou — e o relay que você chama depois mede zero

**Sintoma.** Você escreve o teste do relay do jeito óbvio: roda o caminho que
emite o evento, chama o relay, e afirma que ele publicou um.

```
assert tasks.relay_outbox() == 1
E  assert 0 == 1
```

Zero. E a leitura natural é "o relay não achou o evento" — ou seja, defeito no
relay ou na emissão.

**Causa.** Não há defeito nenhum: **o evento já foi publicado.** O código de
produção registra `transaction.on_commit(relay_apos_commit)`, e o teste está
marcado `@pytest.mark.django_db(transaction=True)` — que é COMMIT de verdade.
No instante em que o bloco fechou, o relay rodou sozinho, publicou no stream e
marcou `published_at`. Quando a sua linha chama o relay, não há mais nada
pendente, e `0` é a resposta certa.

**Esta é a IRMÃ INVERTIDA da [`057`](057-transaction-on-commit-nunca-dispara-no-teste.md)**,
e é por isso que as duas confundem tanto:

| | marca do teste | o que acontece | o que parece |
|---|---|---|---|
| `057` | `django_db` (padrão) | o `on_commit` **nunca** dispara | "o código não publicou" |
| esta | `django_db(transaction=True)` | o `on_commit` **já** disparou | "o relay não achou nada" |

Nas duas o teste fica vermelho, nas duas o código está certo, e nas duas o
reflexo é mexer no código. A `057` empurra você a ligar `transaction=True` — e
aí você cai nesta, que é o degrau seguinte.

**Solução — dois testes, porque são dois caminhos de verdade.**

```python
def test_a_carta_chega_ao_stream_logo_depois_do_commit():
    antes = cliente.xlen(stream)
    caminho_que_emite()                      # o on_commit publica sozinho
    assert cliente.xlen(stream) == antes + 1
    assert OutboxEvent.objects.get().published_at is not None
    assert tasks.relay_outbox() == 0         # e chamar de novo não republica

def test_o_relay_leva_a_carta_que_ficou_pendente():
    with transaction.atomic():
        emitir(...)                          # sem on_commit: é o Redis fora do ar
    assert OutboxEvent.objects.get().published_at is None
    assert tasks.relay_outbox() == 1
```

O primeiro mede o caminho quente (latência sub-segundo). O segundo mede a rede
de segurança — o que a task periódica faz quando o publish do commit falhou. Um
teste só não consegue medir os dois, e escolher o errado deixa a rede de
segurança sem guarda nenhum.

**A regra curta:** num teste com `transaction=True`, o efeito de um `on_commit` é
passado, não futuro. Meça o EFEITO (a linha no stream, o `published_at`
preenchido), não a chamada que você ia fazer depois.

**Origem:** TAR-076, a voz da célula `mensageria`
(`services/mensageria/apps/jornadas/tasks.py`).
