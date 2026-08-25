# Tirar o prefixo do idioma padrão torna o primeiro segmento da URL ambíguo — e a rota perdedora some sem erro nenhum

**Sintoma:** você serve o idioma padrão do site na raiz nua (`/cadastro` = inglês) e
mantém os outros prefixados (`/pt-br/cadastro`). Meses depois alguém acrescenta uma
página `/es` — "Español", a landing de captação em espanhol — e ela responde **404**.
Sem erro de boot, sem 500, sem aviso no CI: a rota está no urlconf, o teste dela até
passa se chamar a view direto, e mesmo assim nenhuma requisição chega lá. O mesmo
vale para `/pt`, `/fr` ou qualquer segmento que colida com um código de idioma que a
célula sabe servir.

**Causa:** enquanto TODOS os idiomas levam prefixo, o primeiro segmento de uma URL é
uma coisa ou a outra, nunca as duas — `/en/x`, `/pt-br/x` são idioma; `/x` é rota. Ao
tirar o prefixo do padrão, os dois passam a morar no mesmo espaço de nomes, e o
resolver precisa escolher quem ganha. Ele escolhe **idioma primeiro** (tem de
escolher: senão `/pt-br/cadastro` viraria uma rota chamada `pt-br`), então a rota
colidente é lida como pedido de tradução e o urlconf nunca a vê.

Não é bug do resolver — é o preço declarado da decisão. O bug é **não ter guarda**:
nada avisa quem escreve a rota, e a falha é silenciosa do lado errado (404 parece
esquecimento de registrar a URL, então a pessoa vai procurar no `urls.py`, onde está
tudo certo).

**Solução — um teste que varre o urlconf e reprova a colisão no PR que a introduz:**

```python
def _codigos_servivies() -> set:
    # o que a CÉLULA sabe renderizar, não o que um site declara hoje: um site
    # que ganhe `es` amanhã não pode transformar uma rota /es já existente em
    # página fantasma.
    return set(cat.IDIOMAS_BASE) | set(cat.VARIANTES)


def test_o_codigo_de_idioma_e_a_rota_nao_colidem_no_primeiro_segmento():
    colisoes = sorted({
        caminho for caminho in (caminho_literal(p) for p in urlpatterns)
        if caminho.strip("/").partition("/")[0] in _codigos_servivies()
    })
    assert colisoes == [], f"rota inalcançável: {colisoes} — renomeie a rota"
```

Reaproveite o `caminho_literal()` que a `armadilhas/086` já obrigou a existir (ele
corta `re_path` no primeiro metacaractere) — e teste o guarda **com uma colisão
fabricada**, senão ele pode ficar verde lendo lixo (RETROSPECTIVA-FASE-D §1: portão
que nunca foi visto reprovando é portão que ninguém sabe se reprova).

**Conserto quando ele reprovar: renomeie a ROTA** (`/es` → `/espanhol`), nunca mexa na
ordem dos ramos do resolver — a ordem é o que faz `/pt-br/cadastro` ser cadastro em
português.

**A armadilha gêmea, no mesmo dia:** ao mesmo tempo, a regra que recusava prefixo
desconhecido precisa **encolher**. Se ela era "primeiro segmento com FORMA de idioma
(2-3 letras) que não é código habilitado ⇒ 404", ela agora condena `/faq`, `/api` e
`/pro` a nunca existirem — e isso passa despercebido porque, com o padrão prefixado,
esses endereços nunca foram alcançáveis mesmo. Troque a adivinhação por normalização:
404 só para o segmento que **normaliza** (minúsculo, `_`→`-`) para um idioma
habilitado — `/PT-BR/`, `/pt_br/`, `/EN/`. O resto vai ao urlconf e leva o 404 dele,
que é o 404 honesto.

**E cuidado com a QUARTA cópia da regra.** Ao virar condicional, a construção do
prefixo tem de morar numa função só (`caminho_publico(cfg, codigo, caminho)`), usada
por canonical, hreflang, sitemap e link interno. Nesta migração havia uma quinta
cópia escondida num fallback: o `?next=` da página de login era
`f"/{request.idioma}/"`, e no idioma padrão devolveria a pessoa, depois de entrar,
para uma URL 404 — atingindo exatamente quem clicou "Entrar" sem vir de outra página.
Só um teste que exercitava o idioma padrão a encontrou. **Grep por `{idioma}` e
`{codigo}` em todo o código da célula antes de fechar o PR.**

**Um efeito colateral que aparece junto:** a raiz de um site multilíngue nunca chegava
às views (era redirecionamento). Servindo-a, o decorador `@require_GET` das views de
página passa a responder **405 a `HEAD /`** — e HEAD na home é o que monitor de
uptime, pré-visualizador de link e crawler usam. Troque por `@require_safe`
(`require_http_methods(["GET", "HEAD"])`) nas views de leitura.

**Origem:** despacho funil/raiz-sem-prefixo, 25/08/2026 — decisão do mantenedor em
`docs/decisoes/DECISAO-raiz-sem-prefixo-do-idioma-padrao.md`, que revogou a parte do
`PLANO-I18N.md` D1 que mandava prefixar todos os idiomas. Parente direto da
`armadilhas/086` (as duas são sobre o resolver ter dois caminhos na mesma requisição)
e da `armadilhas/089` (inventário de rota que reprova quando alguém acrescenta uma).
