---
schema_version: 2
armadilha: 338
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: services/mensageria/tests/test_jornadas_silencio_da_devolucao.py
  motivo: "`test_o_ator_id_chega_ao_handler_pelo_envelope_e_nao_pelo_data` monta o envelope validado contra o contrato em disco (o `ator_id` no nível de cima, `additionalProperties: false` no `data`) e entra por `processar_envelope`; com `aluno_id = data.get(\"ator_id\")` no handler ele cai em `EnvioDeCheckpoint.DoesNotExist`, medido em 05/09/2026"
sinal:
  - "data.get(\"ator_id\")"
  - "sem ator_id"
  - "nao sei de quem e o envio"
---

# O campo do ENVELOPE que o handler da receita R4 nunca vê: `data.get("ator_id")` é `None` em produção, e o teste com envelope de fantasia fica verde

**Sintoma.** Nenhum. O consumidor lê o evento, o handler roda, o evento é
marcado como processado e o `xack` acontece. Só que a tabela que devia guardar
QUEM fez o fato fica vazia (ou o log enche de "sem ator_id" a cada evento), e a
jornada que dependia disso nunca inscreve ninguém. Não há exceção, não há check
vermelho, não há linha na fila morta. Só uma sequência que não acontece.

**Causa.** A receita R4 entrega ao handler o `data` do envelope, e só ele:

```python
handler(envelope["data"], envelope["event_id"])     # mensageria, até 05/09/2026
```

Os campos do NÍVEL DE CIMA (`event_id`, `occurred_at`, `ator_id`) são invisíveis
lá dentro. E em vários contratos desta casa a PESSOA do fato viaja justamente
ali: em `envio.recebido.v1` o aluno está no `ator_id` do envelope e em lugar
nenhum mais (*"E o unico lugar em que o aluno viaja neste evento"*, diz o
contrato). O nome do campo é exatamente o que se procura, então
`data.get("ator_id")` lê natural, passa em revisão, e devolve `None` em toda
entrega real.

**Por que o teste não pega.** Porque o teste chama o handler direto, com um
dicionário montado à mão, e quem monta o dicionário põe o `ator_id` onde o
handler o procura. É a `armadilhas/255` por outra porta: lá o envelope de
fantasia trazia um campo que o contrato PROIBIA; aqui ele traz um campo
verdadeiro no lugar ERRADO, e as duas coisas ficam verdes com a mesma facilidade.

**A forma varia de célula para célula, e é por isso que o reflexo engana.** Na
`gamificacao` o handler recebe o envelope inteiro (`aplicar(envelope, site)`) e
`envelope.get("ator_id")` é o certo. Na `mensageria` recebe `data` mais o
`event_id` (desde 02/09/2026) mais o `ator_id` (desde 05/09/2026). O nome do
campo é o mesmo nas duas; o que muda é o que o consumidor entrega ao handler, e
isso só se descobre lendo o `processar_envelope` da célula em que você está.

**Solução, em três partes.**

1. **O consumidor entrega o campo explicitamente**, como parâmetro com default,
   no mesmo desenho que o `event_id` já usou:

   ```python
   handler(envelope["data"], envelope["event_id"], envelope.get("ator_id"))
   ```

   Todos os handlers da célula ganham `ator_id: str | None = None`; só quem
   precisa o usa, e os testes que chamam os antigos com um argumento continuam
   valendo. `.get`, porque nem todo contrato da célula declara o campo.

2. **O teste monta o envelope EXATAMENTE como o contrato manda e entra pela
   porta real.** `jsonschema.validate(envelope, schema_em_disco)` antes de
   consumir, e `processar_envelope(envelope, STREAMS[...])` em vez do handler
   chamado à mão. Com `additionalProperties: false` no `data`, o `ator_id`
   dentro de `data` nem passa pelo validador: o único envelope possível é o
   que a produção envia, e o teste mede a forma verdadeira.

3. **Antes de ler um campo, pergunte o que o SEU consumidor entrega ao
   handler.** Se a resposta for "só `data`", todo campo de envelope que o
   contrato promete está a uma linha de virar `None` em silêncio.

**Como medir que está curado.** Com a linha errada de volta
(`aluno_id = data.get("ator_id")`), o guarda cai em
`apps.jornadas.models.EnvioDeCheckpoint.DoesNotExist`, e os testes que
inscrevem pela correlação caem em `Inscricao.DoesNotExist`: a pessoa não foi
guardada, então ninguém foi inscrito. Medido em 05/09/2026.

**Origem.** TAR-158 (a jornada do silêncio de 14 e 30 dias, degrau 2.4 da sala
de aula), 05/09/2026: o primeiro handler desta casa a precisar do `ator_id` de
um evento consumido pela `mensageria`. A linha errada chegou a ser escrita e foi
pega na revisão do próprio autor, antes do teste, porque a lição do `event_id`
(`services/mensageria/LICOES.md`, "Todo handler passa a receber o `event_id`")
descrevia o caso e não a classe. Esta entrada é a classe.
