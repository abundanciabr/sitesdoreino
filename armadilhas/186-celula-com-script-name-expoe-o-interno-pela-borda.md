# Célula com `SCRIPT_NAME` expõe o `/interno` dela pela borda pública — e a irmã sem `SCRIPT_NAME` não

**Sintoma:** você copia da `identidade` o comentário que diz *"nada em `/interno`
resolve pela borda pública"*, cola na célula nova, e a frase fica **falsa** sem
que nada acuse. O contrato passa, os testes passam, o deploy fica verde. A porta
de máquina da célula nova está publicada na internet, e o comentário no arquivo
afirma o contrário.

Medido em 30/08/2026, na gênese da porta de máquina do `forum`.

## Causa

Duas células, dois comportamentos, e a diferença é uma linha de `settings.py`.

| | `identidade` | `forum` |
|---|---|---|
| `FORCE_SCRIPT_NAME` | **não tem** | `/forum` |
| O que o Traefik roteia | `PathPrefix(/entrar)` | `PathPrefix(/forum)` |
| Onde mora o `/interno` | na raiz — prefixo que o Traefik **nunca** roteia | **debaixo** do prefixo roteado |
| `/interno` pela borda | inalcançável | **alcançável**, em `/forum/interno/...` |

O que faz o corte é o handler ASGI do Django, e está no código dele:

```python
self.script_name = get_script_prefix(scope)   # = settings.FORCE_SCRIPT_NAME
if self.script_name:
    self.path_info = scope["path"].removeprefix(self.script_name)
```

**A prova mais curta de que isso acontece já estava à vista o tempo todo:** o
`urls.py` do `forum` declara `path("healthz", ...)` — sem prefixo nenhum — e
`https://meshcraft.top/forum/healthz` responde **200**. Se o prefixo não fosse
removido, aquilo seria 404. O mesmo corte que entrega o `healthz` entrega
`/forum/interno/areas`.

E o Traefik **não** remove o prefixo (é decisão da casa, `armadilhas/029`), o que
fecha a conta: o caminho chega inteiro, e quem o corta é o Django.

## Por que isto engana com facilidade

1. **O teste local não reproduz.** O `Client()` de teste do Django não aplica o
   `removeprefix` do caminho ASGI — pedir `/forum/interno/areas` nele dá 404, e
   pedir `/interno/areas` dá 401. Quem medir só pelo teste conclui, de boa-fé,
   que a rota pública não existe. A produção roda `uvicorn config.asgi`, e lá o
   corte acontece.
2. **O comentário da `identidade` é verdadeiro lá.** Copiar de um vizinho certo é
   o hábito correto neste repositório (Lei 3: copia-se o padrão). O que não
   viaja junto com o padrão é a *premissa* dele — e aqui a premissa era a
   ausência de `FORCE_SCRIPT_NAME`.
3. **Nada quebra.** A porta segue fechada pelo Bearer. O erro é só de crença — e
   é o tipo que sobrevive por meses, porque ninguém testa uma frase.

## Solução

**Não confie na topologia para fechar porta de máquina. Feche no Bearer, e teste
o 401.** Vale para as duas famílias: na célula sem `SCRIPT_NAME` a topologia
ajuda, mas ela pode mudar num PR de `infra/` que ninguém relacionou com aquela
célula.

Ao escrever (ou copiar) a ressalva no `config/api.py`, faça a pergunta de uma
linha:

```
esta célula tem FORCE_SCRIPT_NAME?
  não  -> /interno mora na raiz; o Traefik não o roteia. A frase da identidade vale.
  sim  -> /interno mora sob o prefixo ROTEADO. A frase é FALSA — corrija-a.
```

E o guarda que importa não é sobre roteamento, é sobre autenticação: teste 401
**em todas as operações** e no caso do **env ausente** (conjunto de tokens vazio
⇒ ninguém entra). É o que `services/forum/tests/test_porta_de_maquina.py` faz.

## A regra que generaliza

**Comentário que descreve uma garantia é código que ninguém executa.** Quando a
garantia vem da topologia (roteador, rede, prefixo) e não do código da célula,
ela some sem avisar — e o comentário fica, com autoridade, ensinando errado
quem chegar depois. Ou a garantia é medida por um teste, ou o comentário diz
qual é a camada que realmente fecha a porta.

**Origem:** PR #552, a porta de máquina do `forum`, 30/08/2026. O comentário
errado foi escrito e corrigido na mesma sessão — a conferência veio de perguntar
"como o `/forum/healthz` pode responder 200 se o `urls.py` não tem esse prefixo?".
