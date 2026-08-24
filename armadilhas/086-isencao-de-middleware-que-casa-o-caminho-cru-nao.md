# Isenção de middleware que casa o caminho CRU não protege a forma reescrita

**Sintoma:** `/healthz` responde 200 (correto), e **`/pt-br/healthz` também responde
200** — com o mesmo JSON da sonda. A rota de máquina ganhou uma gêmea por idioma que
ninguém escreveu, ninguém linka e ninguém queria. Medido no funil em 24/08/2026, nos
três idiomas do meshcraft, e vale para qualquer rota de máquina que a PRÓPRIA célula
sirva.

**Causa:** a isenção roda no topo do middleware, contra o caminho **como ele chega**:

```python
if request.path_info.startswith(CAMINHOS_SEM_SITE):   # ("/healthz", "/static/")
    return self.get_response(request)
```

`"/pt-br/healthz".startswith("/healthz")` é **False** — a requisição não é isenta e
segue o fluxo normal. Mais abaixo, o mesmo middleware **reescreve** `path_info`,
decapando o prefixo de idioma (`/pt-br/healthz` → `/healthz`), e entrega ao urlconf um
caminho que agora casaria a isenção — só que a isenção já passou. O urlconf resolve a
view e devolve 200.

A armadilha é a **ordem**: um middleware que reescreve o caminho tem DOIS caminhos na
mesma requisição, e uma guarda escrita para um deles não vale para o outro. Vale para
qualquer reescrita, não só idioma: prefixo de tenant, de versão, de região.

**Por que escapou da revisão:** as outras rotas de máquina pareciam provar que estava
tudo bem, cada uma por um motivo diferente e **acidental** — `/api/**` e `/webhooks/**`
porque a célula não serve rota nenhuma nesses prefixos (quem 404 é o gateway, não ela),
e `/sitemap.xml` porque a *view* tem guarda própria. Três verdes por três razões que
não eram a regra que se acreditava ter. "Já obedece por construção" é uma afirmação
sobre mecanismo: se você não consegue apontar o mecanismo, não é construção, é sorte.

**O sinal de que a cura estava no nível errado:** o repositório vinha curando isto
**por view**. Tanto o `sitemap_xml` quanto o `servir_estatico` (rota nascida três dias
depois, no despacho funil/static-em-producao) carregam, cada um, a mesma linha escrita
à mão:

```python
if getattr(request, "idioma", None) is not None:
    raise Http404("<rota> não tem prefixo de idioma")
```

Duas views lembraram, uma esqueceu — e a que esqueceu era a mais antiga das três.
Quando a mesma linha aparece em N lugares por disciplina, a pergunta não é "quem
esqueceu", é "por que isto não é do middleware".

**Solução — confira a isenção DEPOIS da reescrita também**, no único ponto em que dá
para ver que o caminho pedido é a rota de máquina:

```python
ROTAS_DE_MAQUINA = CAMINHOS_SEM_SITE + CAMINHOS_DE_MAQUINA   # a união, uma vez

# ... dentro do trecho que decapa o prefixo:
caminho_sem_prefixo = f"/{resto}"
if caminho_sem_prefixo.startswith(ROTAS_DE_MAQUINA):
    raise Http404("rota de máquina não se localiza")
```

A isenção do topo continua onde estava — ela existe para a sonda do container não
depender do catálogo (`armadilhas/024`), e mover a checagem para depois mataria essa
garantia. São **duas** guardas com propósitos diferentes: a de cima isenta o caminho
nu, a de baixo recusa a forma prefixada. As guardas por view ficam como defesa em
profundidade; deixam de ser a única coisa entre o repositório e o bug.

**E cure a classe, não só o caso** — foi isto que faltou da primeira vez. Uma lista de
rotas de máquina só protege quem está nela, e nada avisa quando a rota seguinte nasce
fora. Um teste que varre o urlconf e exige classificação resolve:

```python
ROTAS_LOCALIZAVEIS = ("/", "/leads", "/cadastro")

def test_toda_rota_do_urlconf_e_classificada_maquina_ou_localizavel():
    caminhos = [caminho_literal(padrao) for padrao in urlpatterns]
    sem_classificacao = [
        c for c in caminhos
        if c not in ROTAS_LOCALIZAVEIS and not c.startswith(ROTAS_DE_MAQUINA)
    ]
    assert sem_classificacao == [], ...   # rota nova força a decisão AGORA
```

**Um detalhe que faz o guarda mentir se você errar:** um urlconf tem `path()` **e**
`re_path()`, e `str(padrao.pattern)` devolve a regex crua no segundo caso —
`/^static/(?P<path>.*)$`, que não casa lista nenhuma. Corte no primeiro
metacaractere (`re.split(r"[(\[\?*+{<$]", …)`) para obter o prefixo **literal**
(`/static/`): é exatamente o pedaço sobre o qual o `startswith` do middleware roda. E
teste esse helper — sem isso o guarda pode ficar verde lendo lixo.

**Vale para checkout, quiz, sugestoes e alunos:** pelo D6 do `PLANO-I18N.md`, a
primeira célula multilíngue fora do funil **copia este resolver** (Lei 7). Quem copiar
o middleware sem as duas guardas copia o 200 junto.

**Origem:** despacho funil/desvio-d6-healthz, 24/08/2026 — o desvio foi achado e
fixado como `xfail(strict=True)` no despacho funil/guardas-d6 (PR #117), que não tinha
mandato sobre `apps/**`, e consertado no seguinte (PR #125). O `strict` fez o trabalho:
no dia do conserto o teste ficou vermelho por XPASS e obrigou a apagar o marcador.
