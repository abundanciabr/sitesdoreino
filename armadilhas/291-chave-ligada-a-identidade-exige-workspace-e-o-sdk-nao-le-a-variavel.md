---
schema_version: 2
armadilha: 291
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: `services/forum/tests/test_agente_de_ia.py` mede o cabeçalho no REQUEST que o SDK monta, com o transporte dublado, nos dois sentidos (com a variável e sem ela). Portão nenhum consegue ver isto de fora: sem a chave real, a chamada nunca é feita, e com ela o defeito só aparece em produção.
sinal:
  - "HTTP 400 com anthropic-workspace-id is required when authenticating with an identity-linked API key"
  - variável de ambiente que o SDK documenta e mesmo assim não chega no request
  - chave de API criada hoje que é recusada enquanto a de ontem funciona
---

# Chave da Anthropic ligada à identidade é recusada com HTTP 400, e a variável de ambiente do workspace NÃO chega ao request quando a chave é passada no código

**Sintoma.** A chave está no lugar certo, o container a enxerga, a rede sai
perfeitamente, e toda chamada volta assim:

```
HTTP 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
 'message': 'anthropic-workspace-id is required when authenticating with an
 identity-linked API key; send the id of the workspace this request acts in.'}}
```

Pôr `ANTHROPIC_WORKSPACE_ID` no `env` da célula **não muda nada**, e é aí que se
perde a tarde: a variável tem exatamente esse nome no SDK, aparece na
documentação dele, e mesmo assim o cabeçalho continua não saindo.

**Causa, e são duas empilhadas.**

**A primeira: existem dois tipos de chave.** A clássica é de *workspace* e
carrega o workspace dentro de si. A nova é ligada à *identidade* de quem a
criou, e por isso não sabe sozinha em qual workspace agir: a API exige o
cabeçalho `anthropic-workspace-id` e recusa sem ele. Quem cria a chave no
console não escolhe isso conscientemente, então o tipo é uma surpresa.

**A segunda: o SDK só lê `ANTHROPIC_WORKSPACE_ID` pela corrente de credenciais,
e passar `api_key=` no construtor sai dessa corrente.** Medido em 02/09/2026,
com o transporte trocado por um dublê que grava os cabeçalhos:

| como o cliente é montado | manda `anthropic-workspace-id`? |
|---|---|
| `Anthropic(api_key=...)`, sem a variável | não |
| `Anthropic(api_key=...)`, **com** `ANTHROPIC_WORKSPACE_ID` no ambiente | **não** |
| `Anthropic(api_key=..., default_headers={"anthropic-workspace-id": ...})` | sim |

A linha do meio é a armadilha inteira. O SDK **tem** a constante
(`anthropic/lib/credentials/_constants.py`) e **tem** o código que monta o
cabeçalho a partir dela (`_providers.py`), mas esse caminho pertence aos
provedores de credencial, e uma chave literal no construtor não passa por lá.

**Solução.** Ler a variável no ponto de uso e mandar o cabeçalho à mão, e
**apenas quando ela existe** (vazia significa chave de workspace, onde o
cabeçalho seria ruído):

```python
workspace = (os.environ.get("ANTHROPIC_WORKSPACE_ID") or "").strip()
cliente = anthropic.Anthropic(
    api_key=chave,
    default_headers={"anthropic-workspace-id": workspace} if workspace else None,
)
```

**A parte que não é código, e é a que mais custou:** a recusa chega como **400**,
não como 401. Num `except` que trate "todo o resto que veio com resposta HTTP"
com uma frase só, ela vira *"pode ser a internet do servidor"* — e manda quem lê
para o lado oposto do conserto, porque a rede funcionou perfeitamente. **Conta
sem crédito também chega como 400**, pelo mesmo caminho e com o mesmo destino.
Quem escreve a frase da tela tem de olhar o CORPO da recusa, não só o número.

**A régua que fica:** variável de ambiente que uma biblioteca documenta não é
promessa de que ela chega ao pedido. Antes de confiar, **meça o request** —
trocar o transporte por um dublê que grava os cabeçalhos custa dez linhas e
responde a pergunta em segundos, em vez de responder na primeira chamada paga,
em produção, na frente do mantenedor.
