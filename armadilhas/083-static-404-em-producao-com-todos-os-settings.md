# `/static/**` responde 404 em produção com TODOS os settings de estático certos

**Sintoma:** a página sobe, o HTML chega inteiro, e o `<script src="/static/...">`
dela devolve **404** só em produção. No navegador do visitante não aparece erro
nenhum de servidor — aparece um formulário que não envia, um botão que não faz nada.
Medido ao vivo em 24/08/2026, com o funil no ar:

```
https://basileiatoutheou.org/static/funil/api.js  -> 404
https://meshcraft.top/static/funil/api.js         -> 404
https://basileiatoutheou.org/healthz              -> 200   (mesmo host, mesma célula)
```

`STATIC_URL`, `STATIC_ROOT` e `STATICFILES_DIRS` estavam **certos** no `settings.py`,
`django.contrib.staticfiles` estava em `INSTALLED_APPS`, o arquivo existia no
repositório e o `{% static %}` gerava a URL correta. Em `make ci`, tudo verde.

**Causa — são DOIS elos, e consertar só um mantém o 404:**

1. **Com `DEBUG=0` o Django não serve estático por conta própria.** O
   `staticfiles` só entrega arquivo pelo `runserver` em modo DEBUG; sob
   `uvicorn`/`gunicorn` ele não instala rota nenhuma. Numa célula que está
   **sozinha atrás do Traefik** — sem nginx, sem CDN e sem router `/static` no
   gateway (o catch-all `PathPrefix(/)` manda tudo para a célula) — não sobra
   ninguém para servir o arquivo. O contraste do `/healthz` a 200 no mesmo host é
   o que localiza a falha: os dois caminhos saem pela mesma isenção do CONV-SITE,
   e a única diferença é que `/healthz` tinha rota no urlconf.

2. **O `collectstatic` do Dockerfile FALHA em todo build, e o `|| true` engole.**
   Todas as nove células têm a mesma linha:

   ```dockerfile
   RUN python manage.py collectstatic --noinput || true
   ```

   O `settings.py` de todas elas é fail-hard (`env("DJANGO_SECRET_KEY")`), e em
   tempo de `docker build` não existe segredo nenhum — o comando morre em
   `ImproperlyConfigured: variável obrigatória ausente: DJANGO_SECRET_KEY` e o
   `|| true` transforma isso em sucesso. Provado dentro da imagem construída:

   ```
   $ docker run --rm --entrypoint sh <imagem> -c 'ls -la /app/staticfiles'
   ls: cannot access '/app/staticfiles': No such file or directory
   ```

   Ou seja: **`STATIC_ROOT` está VAZIO na imagem de produção.** Qualquer solução
   que sirva de `STATIC_ROOT` — o default do whitenoise, entre outras — continua
   devolvendo 404, agora com uma dependência a mais e a suíte igualmente verde.

**Solução (a que já está viva em duas células):** uma rota explícita no urlconf da
célula, servindo do **diretório-fonte**, nunca de `STATIC_ROOT`:

```python
# config/urls.py
re_path(r"^static/(?P<path>.*)$", servir_estatico, name="static"),

# apps/core/views.py
def servir_estatico(request, path):
    return serve_do_django(request, path, document_root=settings.STATICFILES_DIRS[0])
```

O diretório-fonte entra na imagem pelo `COPY . .`, então funciona sem depender do
`collectstatic`, e é o mesmo caminho em dev e em produção. `django.views.static.serve`
não é servidor de alta performance (lê o arquivo pelo processo Python), e é por isso
que ele cabe aqui: o volume é o punhado de `.js`/`.css` das páginas da própria célula.
No dia em que houver CDN de verdade, esta rota sai — até lá, ela é a diferença entre
a página funcionar e não funcionar. A travessia de diretório já vem barrada: o
`safe_join` do Django devolve **400** (`SuspiciousFileOperation`, logado em
`django.security`), não 404.

**Se a célula tem resolver de idioma (i18n), a rota precisa de mais uma linha.** O
resolver decapa `/pt-br` de `request.path_info` ANTES da resolução de URL, então uma
rota ingênua nasce alcançável por `/{idioma}/static/...` — uma URL de máquina por
idioma, conteúdo duplicado para robô. A guarda é a mesma do `sitemap.xml`:

```python
if getattr(request, "idioma", None) is not None:
    raise Http404("estático não tem prefixo de idioma")
```

**Como PROVAR que fechou (e por que os testes óbvios não provam nada):** um teste que
verifica `STATIC_URL`/`STATICFILES_DIRS` fica verde **com o bug vivo** — os settings
sempre estiveram certos. Um teste que exercita o middleware com um espião no lugar da
view também: ele mede a isenção, não a resposta. A prova é uma requisição HTTP real
pelo urlconf real com `DEBUG=0`, comparando o corpo com os bytes do arquivo — e vale
travar `assert settings.DEBUG is False` no próprio arquivo de teste, senão um dia ele
volta a medir o modo DEBUG. Melhor ainda: varra o HTML servido atrás de
`src=`/`href="/static/..."` e busque **cada um** — assim a página que amanhã carregar
um `.css` novo entra na prova sem ninguém lembrar de atualizar o teste.

**Estado das outras células em 24/08/2026 (levantado por leitura, não corrigido):**
só `checkout` e `funil` têm páginas e diretório `static/` — as duas já têm a rota.
As outras sete (`alunos`, `catalogo`, `leads`, `mensageria`, `pagamentos`, `quiz`,
`sugestoes`) têm o **mesmo `collectstatic || true` quebrado e o mesmo `STATIC_ROOT`
vazio**, mas nenhum arquivo estático para servir — o buraco está lá, latente. A
primeira página que qualquer uma delas ganhar nasce com este 404, a menos que o
despacho que a criar já traga a rota.

**Origem:** despacho funil/static-em-producao, 24/08/2026 (o formulário "Quero
receber novidades" das duas landings estava quebrado no navegador). O mesmo bug já
tinha sido resolvido na célula `checkout` em 22/08/2026, com o mesmo diagnóstico
escrito num comentário do `config/urls.py` de lá — e mesmo assim voltou no funil,
porque a lição morava dentro de uma célula. Por isso esta entrada é transversal.
