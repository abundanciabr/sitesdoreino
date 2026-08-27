# O guarda de fail-closed que nasceu verde sem encenar falha nenhuma

**Sintoma:** você escreve o guarda de um caminho de recusa, ele passa de
primeira, e você segue em frente satisfeito. Ele nunca provou nada: a falha que
ele deveria encenar **não aconteceu**, e o teste passou pelo caminho feliz.

**O caso, medido em 26/08/2026.** O guarda novo era: *"quem modera sem id da
plataforma não muda status nenhum"*. A primeira versão fazia o óbvio —
zerava a coluna e mandava o POST:

```python
equipe = caixa.equipe.identidade
equipe.id_da_plataforma = None
equipe.save(update_fields=["id_da_plataforma"])
resposta = caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)
assert resposta.status_code == 409      # veio 302
```

Veio **302** — sucesso. Motivo: toda requisição da Caixa atravessa
`obter_sessao`, que chama `cunhar_ou_recuperar` e **regrava** o id na reentrada
(INV-SUG11). Entre o `save()` do teste e a linha que o guarda queria medir, a
porta havia reposto o dado. O teste zerava um estado que o sistema restaura
sozinho no caminho até o ponto medido.

**A causa, em uma frase:** *o teste sabotou um estado DERIVADO, e não a fonte
que o deriva.*

**A cura: encene pelo CONTRATO, na fronteira.** A resposta de `getSessionFull`
declara `id` opcional e nulável (`anyOf: [string, null]`). Fazer o dublê
responder **sem** o `id` é a única encenação que a porta não desfaz — porque é
exatamente o que aconteceria em produção:

```python
sem_identidade = entrar_como_staff("outro@meshcraft.test", com_id=False)
resposta = sem_identidade.client.post(...)
assert resposta.status_code == 409
```

**A regra, para qualquer guarda de recusa:** pergunte *"o que, no mundo real,
produziria este estado?"* e encene ISSO. Se a resposta for "nada — este estado
não pode existir", então o guarda não tem o que provar e o código de recusa é
morto: descubra qual dos dois está errado antes de escrever o teste.

**E o sinal que teria pego mais cedo:** um guarda de fail-closed que passa **de
primeira** merece desconfiança, não comemoração. Antes de aceitá-lo, inverta a
asserção (`assert resposta.status_code == 302`) e confirme que ela passa — se
passar, o teste está medindo o caminho feliz. É a versão barata da prova por
mutação, e custa trinta segundos.

**Família:** é a `armadilhas/129` (guarda que usa o objeto medido como régua)
vista pelo outro lado — lá a régua se movia junto com a peça; aqui a peça volta
sozinha ao lugar antes da medição. **Categoria** (`RETROSPECTIVA-FASE-D`):
falso-verde.

**Origem:** despacho da adoção do formato novo na Caixa, 26/08/2026 (PR #245),
guarda do INV-SUG12.
