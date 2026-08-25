# `USE_TZ = True` não escolhe fuso: a célula mostra hora de Chicago e nada acusa

**Sintoma:** não há erro nenhum. O CI está verde, o deploy sobe, o `/healthz`
responde 200 — e a data na tela está cinco horas atrás. Pior: perto da virada do
dia ela mostra o **dia errado**. Um usuário que respondeu ao quiz às 01:00 do dia
25 lê "24/08/2026 23:00" e conclui que o site perdeu a resposta dele.

A falha fica invisível pelo tempo que a célula levar até renderizar a primeira
data. Enquanto nenhuma tela mostra hora, o defeito já está lá, dormindo no
`settings.py` — foi exatamente esse o caso da `sugestoes` (EVO-21, 24/08/2026):
o bug nasceu com a célula e só apareceu quando a tela de avisos ficou pronta.

**Causa:** `USE_TZ = True` e `TIME_ZONE` respondem a perguntas diferentes, e é
fácil ler o primeiro como se resolvesse os dois:

| Setting | Pergunta que responde | Sem ele |
|---|---|---|
| `USE_TZ` | Como eu **guardo**? | naive, sem fuso |
| `TIME_ZONE` | Que hora eu **mostro**? | `America/Chicago` (default de fábrica) |

`USE_TZ = True` só garante que o banco recebe UTC. Quem converte UTC → hora do
leitor é `TIME_ZONE`, e o default de fábrica do Django é `America/Chicago` —
uma escolha que nunca foi decisão de ninguém neste projeto, só a ausência de uma
linha. O motor de template converte `datetime` aware sozinho, em silêncio: não
há warning, não há check do `manage.py check`, não há nada que reprove.

Toda célula gerada pela receita CONV herda a omissão. Não é dívida de uma célula.

**Solução — a linha, junto do `USE_TZ`, com o motivo escrito:**

```python
USE_TZ = True

# O fuso em que a célula MOSTRA hora — o armazenamento continua em UTC (USE_TZ).
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`.
TIME_ZONE = "America/Sao_Paulo"
```

**E o guarda, que é a parte que não pode ser tautologia.** Um teste que afirma
`settings.TIME_ZONE == "America/Sao_Paulo"` prova que a linha existe, não que o
comportamento está certo — e um teste desses passa até num projeto que renderiza
tudo errado por outro motivo. O truque é escolher um **instante que muda de dia**
entre o fuso certo e o default: `04:00 UTC` é 01:00 do dia 25 em São Paulo
(−03:00) e 23:00 do dia **24** em Chicago (−05:00). Apagou a linha, o teste não
muda só um número — ele acusa a data errada, que é o estrago real:

```python
from datetime import datetime, timedelta, timezone as tz_stdlib
from django.template import engines
from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=tz_stdlib.utc)


def test_a_data_que_o_usuario_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)
    assert local.utcoffset() == timedelta(hours=-3)
    assert local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"


def test_template_renderiza_a_data_no_formato_brasileiro():
    # o caminho REAL do usuário: o motor converte datetime aware sozinho
    t = engines["django"].from_string('{{ quando|date:"d/m/Y H:i" }}')
    assert t.render({"quando": INSTANTE_UTC}).strip() == "25/08/2026 01:00"
```

Vale o par: o `localtime` prova a conversão, o template prova o caminho que o
usuário percorre. E convém uma contraprova de que o fuso de **exibição** não
virou fuso de **gravação** (`settings.USE_TZ is True` e
`timezone.now().utcoffset() == timedelta(0)`) — senão o remédio vira outro bug.

**Fica de fora de propósito:** `LANGUAGE_CODE` continua `en-us` nas células. Ele
não afeta formato explícito (`date:"d/m/Y"` é numérico e independe de locale),
mas afeta nome de mês e dia da semana — `{{ d|date:"F" }}` sai "August". É dívida
separada, com correção separada; não a resolva "de passagem" num PR de fuso.

**Origem:** despacho de fuso da célula `quiz`, 25/08/2026 — o guarda nasceu
vermelho mostrando `24/08/2026 23:00` onde a tela devia mostrar
`25/08/2026 01:00`. Precedente: `sugestoes`, EVO-21, 24/08/2026.
