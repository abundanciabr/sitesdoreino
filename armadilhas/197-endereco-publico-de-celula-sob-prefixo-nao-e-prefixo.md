---
schema_version: 2
armadilha: 197
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/mapa_do_site.py
sinal:
  - `endere[çc]o (p[úu]blico )?(da|do) c[ée]lula`
  - `prefixo dobrado`
---

# O endereço público de uma célula sob prefixo NÃO é "prefixo + rota" — ele dobra num caso e duplica noutro

**Sintoma.** Você precisa do endereço público de uma rota (para um link numa
tela, uma linha de documentação, um `curl` de conferência, um teste de fumaça),
compõe `SCRIPT_NAME + rota` — e uma destas duas coisas acontece:

- o endereço devolve **404**, embora a rota exista e a célula esteja no ar; ou
- o endereço funciona, e você **não descobre** que a mesma rota também responde
  num segundo endereço, mais curto, que é o que o mundo de fora usa.

Medido em 30/08/2026, na internet pública, ao construir o mapa do site:

| Rota, no `urls.py` | Célula | Endereço que RESPONDE |
|---|---|---|
| `quiz/<slug:slug>/` | `quiz` (`SCRIPT_NAME=/quiz`) | `/quiz/quiz/<slug>/` — o prefixo **dobra** |
| `docs/` | `admin` (`SCRIPT_NAME=/admin`) | `/admin/docs/` **e** `/docs/`, as duas com 200 |
| `mapa-ia/` | `admin` | `/admin/mapa-ia/` **e** `/mapa-ia/` |
| `api/checkout/` | `checkout` (`SCRIPT_NAME=/checkout`) | `/checkout/api/checkout/` **e** `/api/checkout/` |

**Causa.** Duas peças se somam, e cada uma sozinha parece inofensiva:

1. **O Traefik NÃO remove o prefixo** (`armadilhas/029`). Quem o remove é o
   Django, por `FORCE_SCRIPT_NAME` — e ele só remove **quando o caminho começa
   pelo prefixo**. É literalmente um `if path.startswith(script_name)` dentro do
   `ASGIRequest`.
2. **Um mesmo serviço pode receber mais de um prefixo do roteador.** Os routers
   `docs` e `mapa-ia` de `infra/traefik/dynamic/plataforma.yml` apontam para o
   serviço `admin`, o mesmo de `/admin`.

Daí os dois desfechos. Se a rota **repete** o prefixo no `urls.py`
(`quiz/<slug>/` numa célula servida em `/quiz`), o Django tira `/quiz` e sobra
`/<slug>/`, que não casa — só a URL **dobrada** casa. Se o Traefik entrega à
célula um **segundo** prefixo (`/docs`), o caminho não começa por `/admin`,
nada é removido, e a rota `docs/` casa com o caminho inteiro: a mesma view
responde nos dois endereços.

**Solução.** Não componha o endereço de cabeça — pergunte ao cartógrafo, que
deriva das três fontes reais (roteamento, `urls.py`, `SCRIPT_NAME`):

```bash
python ci/mapa_do_site.py --mostrar
```

Ele imprime, por rota, **todos** os endereços em que ela responde. É a mesma
medição que a muralha `mapa-do-site` usa para reprovar um endereço inventado no
mapa do dono (`painel/mapa-do-site.json`), então o que ele diz é o que o portão
cobra.

**De quebra:** a linha do `quiz` acima é uma pergunta em aberto, não um defeito
provado — hoje **nenhum quiz está publicado**, então nenhum dos dois endereços
tem conteúdo para devolver, e não dá para decidir pela borda qual era a
intenção. Está anotado como observação na entrada do quiz no mapa; quem
publicar o primeiro quiz confere lá.
