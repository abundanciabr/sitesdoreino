---
schema_version: 2
armadilha: 290
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  motivo: nenhum portão sabe distinguir "este stub é andaime declarado" de "este stub virou produção" — o que se pode exigir é que o REGISTRO não afirme sucesso, e isso é teste por caso (services/mensageria/tests/test_email_de_verdade.py)
sinal:
  - "\"\"\"Stub: loga o envio\"\"\" num caminho que grava status de entrega"
  - tabela de auditoria com 100% de sucesso e nenhuma entrega verificável de fora
---

# O stub que marca como `enviado` é o falso-verde mais caro da casa

**Sintoma.** Ninguém reclama, nada falha, e a tabela de auditoria diz que está
tudo entregue. Você só descobre quando alguém pergunta *"o aluno recebeu?"* e a
única fonte capaz de responder é a que mente:

```
o que o registro de auditoria AFIRMA:
      status   = 'enviado'
      resultado= 'ok'
o que REALMENTE saiu:
      cartas na caixa de saida = 0
```

Medido em 02/09/2026, contra o código que estava em produção desde que a célula
`mensageria` existe.

**Causa.** Um stub honesto no nome e desonesto no efeito:

```python
def enviar_email(destinatario, assunto, corpo):
    """Stub: loga o envio. Provedor SMTP real fica para depois."""
    logger.info("EMAIL -> %s | %s\n%s", destinatario, assunto, corpo)   # e volta SEM ERRO
```

Quem chama trata "voltou sem exceção" como sucesso — que é a leitura correta de
qualquer função — e grava `status="enviado", resultado="ok"`. **O stub não
mentiu; ele deixou o chamador mentir.** A docstring dizia a verdade para quem
abrisse o arquivo, e o banco dizia o contrário para todo o resto da empresa.

**Por que isto é pior que um erro.** Um envio que falha grita: o registro fica
`falhou`, o retry acontece, alguém olha. Um envio que finge produz uma base de
dados com **100% de sucesso** — o número que ninguém investiga. E o dano cresce
em silêncio: quanto mais tempo passa, mais linhas afirmam entregas que nunca
existiram, e nenhuma delas é distinguível de uma real.

É o padrão **falso-verde** da `RETROSPECTIVA-FASE-D.md` na sua forma mais
duradoura: não um teste que passa errado, um SISTEMA que registra errado.

**Solução, em duas partes — e a segunda é a que quase não se faz.**

**1. Stub que grava estado precisa FALHAR, não voltar em silêncio.** Se o
transporte não existe neste ambiente, a função levanta com nome próprio:

```python
class EmailNaoConfigurado(RuntimeError):
    """Não há provedor neste ambiente — e isso não é defeito de código."""

if not (settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL):
    raise EmailNaoConfigurado("SMTP_HOST/SMTP_FROM ausentes …")
```

O nome próprio importa: a AÇÃO que ele pede (configurar o provedor) é diferente
da que um erro de rede pede (esperar o retry). Num log às duas da manhã, essa
diferença é a distância entre minutos e horas.

**2. "Sem exceção" não é prova de entrega.** É a `armadilhas/028` na forma SMTP,
e ela reaparece com transporte de verdade por baixo:

```python
quantos = send_mail(..., fail_silently=False)
if quantos != 1:
    raise EnvioRecusado(f"{quantos} mensagem(ns) enviada(s), esperava 1")
```

`send_mail` devolve QUANTAS saíram, e `0` sem levantar é desfecho real do
backend do Django. Sem ler esse número, o conserto recria a mesma mentira —
agora com um provedor de verdade do outro lado, o que a torna mais crível.

**A régua que generaliza:** **um stub pode fingir o EFEITO, nunca o REGISTRO.**
Logar em vez de enviar é andaime legítimo; deixar o chamador gravar "entregue" é
corromper a única fonte que responderá a pergunta depois. Se a função não pode
cumprir o que promete, ela levanta — e quem grava o resultado grava a verdade.

Vale para todo stub que participa de um caminho auditado: pagamento, emissão de
nota, WhatsApp, push, webhook de saída.

**A dívida que ficou declarada, de propósito:** `enviar_whatsapp` **continua**
stub nesta célula. A diferença é que agora está escrito, e o despachante das
jornadas recusa o canal `whatsapp` (`CanalNaoSuportado`, `armadilhas/285`) — então
nenhuma jornada consegue marcar como entregue o que aquele stub não entregou. O
caminho transacional antigo ainda o chama, e isso é dívida nomeada, não descuido.
