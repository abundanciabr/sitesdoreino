# A API "interna" de uma célula sob `SCRIPT_NAME` responde pela internet — e o plano que diz "rede interna do Docker" está errado

**Sintoma:** não há erro nenhum. Você escreve — num plano, num despacho, numa
constituição de célula — que a superfície de máquina de uma célula
(`/interno/...`, `/api/<celula>/...`) *"não tem rota no Traefik"* ou *"só é
alcançável pela rede interna do Docker"*, porque nenhum router do
`infra/traefik/dynamic/plataforma.yml` nomeia aquele caminho. Medido de fora, em
25/08/2026:

```
GET https://meshcraft.top/forms/sugestoes/interno/sessao   → 401 {"detail": "Unauthorized"}
GET https://meshcraft.top/alunos/api/alunos/matriculas     → 405
GET https://meshcraft.top/interno/sessao                   → 404
```

As duas primeiras **existem e respondem** pela internet pública. A terceira, não.
O 401 é a prova de que a rota chegou até o Django e o `auth` recusou — 404 seria
a prova de que não chegou.

**Causa:** o router da célula casa por **prefixo**, e **o Traefik não remove o
prefixo** — a célula o conhece por `SCRIPT_NAME` no env dela. Logo o router
`PathPrefix(/forms/sugestoes)` entrega à célula **tudo** que ela serve sob aquele
prefixo, inclusive o que o autor considerava privado. A única coisa que separa
"interno" de "público" não é a rota: é o `auth` do django-ninja e o Bearer
estático do par.

A célula `identidade` é a exceção que confunde — ela **não tem** `SCRIPT_NAME`
(`infra/env/identidade.env.exemplo:10`, "NÃO tem SCRIPT_NAME de propósito") e o
Traefik só lhe manda `/entrar/*`. O comentário no código dela diz isso com uma
palavra que carrega todo o peso e é fácil de ler por cima
(`services/identidade/config/api.py:12-15`): *"nada em `/interno` resolve pela
borda pública **AQUI**"*. Quem copia a frase sem copiar o **AQUI** herda uma
afirmação falsa.

Quem está de que lado, hoje:

| Célula | mount da API | `SCRIPT_NAME` | alcançável de fora? |
|---|---|---|---|
| `sugestoes` | `interno/` | `/forms/sugestoes` | **sim** |
| `alunos` | `api/alunos/` | `/alunos` | **sim** |
| `checkout` | `api/checkout/` | `/checkout` | **sim** |
| `quiz` | — | `/quiz` | — |
| `identidade` | `interno/` | **nenhum** | não |
| `leads`, `catalogo` | `api/<celula>/` | nenhum (sem router) | não |

**Solução:**

1. **Nunca afirme privacidade de caminho a partir do nome do caminho.** A
   pergunta certa é: *esta célula tem `SCRIPT_NAME` e um router de prefixo?* Se
   tem, tudo que ela serve é alcançável de fora. Confira no env exemplo e no
   `plataforma.yml`, e **meça** — `curl -o /dev/null -w "%{http_code}"` de fora
   distingue 401 (existe, trancada) de 404 (não existe) em um segundo.
2. **Toda operação de máquina numa célula sob prefixo nasce com o guarda de
   401-sem-Bearer**, medido pela borda e não pelo cliente de teste. O molde
   existe: `services/sugestoes/tests/test_inv_sem_sessao_nada.py` deriva as rotas
   do próprio urlconf e confere o conjunto isento por **igualdade exata**, então
   rota nova não escapa em silêncio.
3. **O Bearer estático é a única defesa dessas rotas** — ele não expira e não
   rotaciona. Isso muda o peso de um vazamento de env (`armadilhas/090`): não é
   só "alguém leu um segredo", é "alguém tem a API de matrícula de um café".
   Escreva isso onde o token for concedido.

**Isto não é uma brecha aberta hoje** — o 401 prova que o `auth` faz o trabalho.
É uma afirmação de topologia que envelheceu errado e que, repetida num plano,
faria nascer um endpoint novo com o modelo de ameaça errado.

**Origem:** banca de auditoria do `PLANO-AREA-ADMIN.md`, 25/08/2026. O plano
propunha `GET /interno/metricas` em cinco células afirmando "sem rota no
Traefik, rede interna do Docker"; a cadeira de segurança apontou a contradição
lendo os envs, e a medição de fora confirmou. Parente do `armadilhas/102` e do
`083` (a família "`SCRIPT_NAME` faz a célula ser servida num lugar diferente do
que o código supõe") e caso novo do padrão 8 da `RETROSPECTIVA-FASE-D.md` —
*não afirme viabilidade, nem privacidade, sem ler a configuração real*.
