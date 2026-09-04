---
schema_version: 2
armadilha: 323
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: "nenhum varredor barato distingue um `AGORA` fixo legítimo (o `desde` de um parâmetro, uma data de histórico) de um que será comparado com uma coluna `auto_now_add`; a régua é o PAR (constante fixa, restrição contra coluna automática), e ela mora na cabeça de quem escreve a restrição. O que existe é esta entrada e o comentário no topo dos dois arquivos da célula encomendas."
sinal:
  - "violates check constraint"
  - "auto_now_add"
  - "DETAIL:  Failing row contains"
  - "testes que passavam ontem falham hoje sem nenhum commit no meio"
---

# Instante fixo no teste contra uma coluna `auto_now_add` é bomba-relógio: verde de manhã, vermelho à tarde, sem ninguém tocar no código

**Sintoma.** Você abre uma bancada nova a partir da `main`, roda a suíte da
célula ANTES de escrever a primeira linha, e dez testes estão vermelhos:

```
FAILED tests/test_modelo_de_dados.py::test_uma_oferta_pendente_por_encomenda
FAILED tests/test_modelo_de_dados.py::test_uma_oferta_pendente_por_aluno
FAILED tests/test_maquinas_de_estado.py::test_a_oferta_fechada_e_pedra
...
10 failed, 71 passed
```

O `git log` do arquivo não tem nada de hoje. O último PR que o tocou está verde
no GitHub. Rodar de novo dá o mesmo resultado. E a mensagem do banco não fala do
que o teste está medindo:

```
IntegrityError: new row violates check constraint "oferta_expira_depois_de_oferecida"
DETAIL:  Failing row contains (..., 2026-09-04 15:15:36+00, 2026-09-04 15:00:00+00, ...)
                                     ^ oferecida_em (o relogio real)  ^ expira_em (AGORA + 3h)
```

**Causa.** O arquivo de teste tinha um instante fixo no topo, e ele era o
instante em que o arquivo foi escrito:

```python
AGORA = datetime(2026, 9, 4, 12, 0, tzinfo=fuso.utc)
...
"expira_em": AGORA + timedelta(hours=3),      # 15:00 UTC daquele dia
```

Só que `Oferta.oferecida_em` é `auto_now_add`: **quem o preenche é o relógio da
máquina, não o teste.** E a tabela tem
`CheckConstraint(expira_em__gt=F("oferecida_em"))`. Enquanto o relógio real
estava antes das 15:00 daquele dia, `expira_em` era futuro e tudo passava. Às
15:00 em ponto, `oferecida_em` ultrapassou `expira_em` e a mesma linha virou
proibida.

Medido em 04/09/2026: o PR #990 (TAR-120, as tabelas da célula `encomendas`)
pousou verde por volta das 12h UTC e a suíte adoeceu às 15h UTC do MESMO dia,
três horas depois. Ninguém viu, porque o `ci-celula` só roda a suíte de uma
célula quando o PR toca a célula — e nenhum PR tocou a `encomendas` naquelas
três horas. O degrau seguinte (TAR-121, o motor) encontrou a bomba já
detonada, antes de escrever a primeira linha de código.

**Por que é caro além do vermelho.** A leitura natural quando isso aparece é a
pior possível: *"eu quebrei alguma coisa"*. Quem herda a bancada gasta a
primeira meia hora procurando o próprio erro num código que ainda não escreveu,
e o suspeito óbvio é a restrição do banco — que está certa. Foi o mesmo formato
de engano da `armadilhas/319`: o instrumento mentindo sobre onde está o defeito.

**Solução: o instante do teste é o relógio REAL sempre que ele for comparado
com uma coluna automática.**

```python
# ERRADO — vira passado sozinho, e o teste morre de velhice
AGORA = datetime(2026, 9, 4, 12, 0, tzinfo=fuso.utc)

# CERTO — a distância até `auto_now_add` é sempre a mesma
AGORA = datetime.now(tz=fuso.utc)
```

Nada mais muda: `AGORA - timedelta(days=30)`, `AGORA + timedelta(hours=3)` e
`pagamento_confirmado_em=AGORA` continuam funcionando, porque **todos eram
relativos** — o único absoluto era a âncora.

**A régua, e ela é um PAR, não um caractere.** Instante fixo em teste não é
proibido: o `desde` de um parâmetro semeado, a data de um evento histórico, o
`COMECO_DOS_TEMPOS` de um semeador são fixos de propósito e têm de ser. O que
não pode existir é a combinação:

> um valor **fixo** no teste, comparado por **restrição do banco** com uma
> coluna que o próprio banco preenche (`auto_now_add`, `auto_now`, `now()`).

Antes de escrever a fixture, pergunte: *esta data vai ser comparada com alguma
coluna que eu não controlo?* Se sim, ela é relativa ao relógio real.

**Duas variantes da mesma doença, para reconhecer:** o teste que só falha depois
de meia-noite (data fixa comparada com `date.today()`) e o teste que só falha na
segunda-feira (dia útil fixo). São a mesma coisa — um valor congelado medindo um
relógio que anda — e o mesmo conserto: ancorar no relógio, nunca no calendário.

**Por que não há portão.** Um varredor que acusasse todo `datetime(...)` literal
em `tests/` reprovaria as fixtures legítimas, seria afrouxado na mesma semana, e
a regra morreria por ter medido demais. A régua depende de saber com QUAL coluna
a data será comparada, e isso não se lê do arquivo de teste sozinho. O que
sobra é o sino (as três assinaturas acima) e o comentário no topo dos dois
arquivos consertados, que explica a troca para quem for copiá-los.
