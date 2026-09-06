---
schema_version: 2
armadilha: 371
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: ci/tests/test_preco_da_conversa.py
gatilho:
  - ci/preco_da_conversa.py
  - ci/sino_das_armadilhas.py
licao: gancho que fala "uma vez por sessão" guarda o estado AO LADO do transcript (`transcript.with_suffix(...)`), nunca em `tempfile.gettempdir()` — em temp ele sobrevive à conversa e o gancho cala para sempre naquela chave. Com vários patamares, guarde o MAIS ALTO já dito, não a lista.
---

# 371 — Estado de gancho em temp cala o gancho para sempre

**Sintoma.** Um gancho `PostToolUse` que deve avisar uma vez por sessão passou a
não avisar nunca mais. Nos testes, a primeira rodada passava e a segunda
falhava, com 8 testes vermelhos que estavam verdes um minuto antes, sem nenhuma
mudança no código entre as duas.

**Causa.** O estado do "já avisei" morava numa pasta própria dentro de
`tempfile.gettempdir()`, chaveado pelo `session_id`. Esse arquivo sobrevive ao
processo, à sessão e à suíte de testes. Uma chave usada uma vez fica marcada
para sempre, e o gancho cala para sempre naquela chave. Nos testes, a chave era
literal (`"cara-1"`), então a segunda rodada da suíte encontrava tudo já dito.

**Solução.** O estado mora ao lado do arquivo que ele mede:

```python
def estado_do_arquivo(transcript: Path) -> Path:
    return transcript.with_suffix(transcript.suffix + ".preco.json")
```

O ciclo de vida passa a ser o mesmo da conversa: o teste isola sozinho pelo
`tmp_path` do pytest, e nada se acumula em temp. Some junto a sanitização do
`session_id`, que existia só para virar nome de arquivo.

**A segunda metade, que a prova de fora pegou depois do teste verde.** Com
vários patamares (300k, 500k, 700k), marcar só o patamar cruzado deixa os de
baixo por dizer. Uma conversa retomada em 967k cruza os três de uma vez: o
gancho avisa pelo de 700k, e na chamada seguinte encontra o de 500k ainda por
dizer e avisa de novo, a cada comando, para sempre. Guarde o patamar MAIS ALTO
já dito, um inteiro, e compare com ele:

```python
alcancado = max((p for p in PATAMARES if contexto >= p), default=0)
if alcancado > int(estado.get("contexto_dito") or 0):
    estado["contexto_dito"] = alcancado
```

**A lição que atravessa as duas metades:** teste de unidade verde não prova
gancho vivo. Os dois defeitos apareceram fora do pytest, um ao rodar a suíte
duas vezes seguidas e o outro ao apontar o gancho para um transcript real de
9,1 MB. Rode o gancho contra um transcript de verdade, três vezes seguidas, e
confira que ele fala uma vez e cala duas.
