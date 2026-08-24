# `httpx.get()` direto constrói um `SSLContext` por chamada (0,4 s cada)

**Sintoma:** a suíte de uma célula que fala com outra célula demora **dezenas de
segundos** sem nenhum teste lento aparente, e cada requisição de usuário que atravessa
duas células paga quase **um segundo** de espera pura. Ninguém suspeita da rede,
porque em teste a rede está dublada — e mesmo dublada o custo continua lá.

Medido no despacho EVO-12a (`sugestoes`), 24/08/2026: **0,4 s por chamada** com
cliente novo, contra **0,000 s** com cliente reaproveitado. A suíte da célula caiu de
**85 s para 2 s** com a troca.

**Causa:** `httpx.get(...)` / `httpx.post(...)` no nível do módulo cria um `Client`
descartável a cada chamada, e cada `Client` constrói um `ssl.SSLContext` que **carrega
os certificados raiz do sistema**. O custo é do carregamento dos certificados, não da
conexão — por isso aparece igual em teste com dublê.

**Solução:** um `httpx.Client` **preguiçoso por processo**, num módulo de clientes da
célula:

```python
# apps/core/clients.py
import httpx
_cliente: httpx.Client | None = None

def http() -> httpx.Client:
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=httpx.Timeout(5.0, connect=2.0))
    return _cliente
```

`httpx.Client` é seguro entre threads, que é o que o uvicorn precisa. **Mantenha o
timeout explícito** — a receita R2 do `CAMINHO-DOURADO.md` exige, e ele não pode se
perder na troca.

**Isto é dívida de mais de uma célula, não peculiaridade de uma.** O padrão R2 e o
`clients.py` do `checkout` usam a forma direta; o `funil` também. O custo está lá,
só que escondido em suítes menores — a `sugestoes` só o tornou visível porque faz
**dois** saltos por login (o provedor de identidade e a célula `alunos`).

**Como confirmar antes de mexer:** cronometre uma chamada dublada isolada. Se der
centenas de milissegundos com a rede dublada, é isto — não é a rede, é o `SSLContext`.

**Origem:** despacho EVO-12a (`sugestoes`, "Entrar com Google"), 24/08/2026.
