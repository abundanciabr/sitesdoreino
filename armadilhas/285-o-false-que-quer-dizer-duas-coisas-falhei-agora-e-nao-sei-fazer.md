---
schema_version: 2
armadilha: 285
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: nenhum portão consegue ler a INTENÇÃO de um `return False`; o guarda é o par de testes que fixa os dois significados (o transitório continua sendo retentado, o definitivo segue em frente) — e é o par, não cada um sozinho, porque um teste só permite trocar um pelo outro sem ninguém notar
sinal:
  - retentativa que nunca vai ter sucesso, repetida em toda passada de uma varredura
  - `return False` num ponto de extensão onde uma das causas é "esta versão não faz isso"
---

# O `False` que quer dizer duas coisas: "falhei agora" e "não sei fazer isso"

**Sintoma.** Uma varredura retenta a mesma coisa para sempre, e a retentativa
**nunca poderia** dar certo. Não há erro, não há log — só trabalho repetido em
toda passada, e uma linha que nunca sai do lugar.

**Causa.** Um ponto de extensão com contrato `bool`:

```python
def despachar(inscricao, passo, canal) -> bool:
    if canal not in CANAIS_QUE_SEI_ENTREGAR:
        return False          # "não sei entregar por aqui"
    ...
    return False              # "o Redis caiu agora"
```

Os dois `False` são o mesmo valor e **exigem coisas opostas de quem chama**:

| o que aconteceu | muda com o tempo? | o que o chamador deve fazer |
|---|---|---|
| o provedor caiu, o Redis sumiu | sim | **retentar** — a próxima passada tenta |
| esta versão não entrega por esse canal | **não** | **seguir em frente** — retentar é laço infinito |

Um booleano tem espaço para uma pergunta só, e a pergunta que ele respondia era
*"deu certo?"*. A informação que faltava é *"e vale a pena tentar de novo?"*.

**Por que isso quase sempre passa despercebido.** O caso definitivo costuma ser
**inalcançável quando o código nasce** — aqui, nenhum passo usava e-mail, porque
o canal ainda não existia. O defeito fica dormindo até alguém configurar
exatamente o caso que o autor tinha em mente ao escrever a linha. E aí ele não
falha: ele **repete**.

**Solução: exceção para o definitivo, `False` para o transitório.**

```python
class CanalNaoSuportado(Exception):
    """Esta versão da plataforma não entrega por aqui. Retentar não muda isso."""

# no despachante
if canal not in CANAIS_QUE_SEI_ENTREGAR:
    raise CanalNaoSuportado(f"a plataforma ainda nao entrega pelo canal {canal}")

# em quem chama
except CanalNaoSuportado as motivo:
    registrar(resultado="pulada", motivo=str(motivo))   # a pergunta tem resposta
    avancar(...)                                        # e a fila anda
```

**Exceção, e não um terceiro valor de retorno** (`"ok" | "falhou" | "nao_sei"`),
por um motivo prático: quem esquecer de tratar a exceção **falha alto**, e quem
esquecer de tratar um terceiro valor de string o compara com `if resultado:` e
segue em silêncio pelo ramo errado. O contrato `bool` continua valendo inteiro
para o caso normal.

**E registre o definitivo.** "Seguir em frente" não pode virar "esquecer": a
pergunta *"por que fulano não recebeu no e-mail?"* precisa continuar com resposta
na tela. Aqui a entrega é gravada como `pulada`, com o motivo por extenso.

**A régua que generaliza:** todo ponto de extensão que pode responder "não"
precisa dizer **se o não é de agora ou de sempre**. Vale para despachante de
canal, adaptador de provedor de pagamento, conversor de formato, verificador de
condição — qualquer lugar onde uma implementação pode legitimamente não saber
fazer o que foi pedido.

**Mãe:** `armadilhas/283`, a lei geral do lado de quem chama — *toda passada que
examina uma linha termina tendo mexido no relógio dela, ou tendo dito por que
não*. Esta entrada é o mesmo problema visto do lado de quem responde. **Irmã:**
`armadilhas/284`, da mesma revisão.
