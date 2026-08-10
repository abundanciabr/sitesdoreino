# Template de Célula — cada célula é um projeto Django COMPLETO e autônomo

## Árvore canônica

```
services/<celula>/
├── manage.py
├── requirements.txt          # dependências pinadas
├── Makefile                  # a Definição de Pronto local: make ci
├── Dockerfile
├── docker-compose.dev.yml    # SÓ esta célula + banco + redis + MOCKS das dependências
├── .env.dev                  # dev local (no .gitignore)
├── config/                   # o projeto Django chama-se SEMPRE config (uniformidade)
│   ├── settings.py           # SECRET_KEY sem valor ⇒ ImproperlyConfigured (sem fallback)
│   ├── urls.py               # a célula é dona do próprio prefixo (SCRIPT_NAME)
│   └── asgi.py
├── apps/                     # apps de domínio DESTA célula
├── templates/  static/       # base própria — não existe base.html compartilhado na plataforma
└── tests/
```

## Convenções obrigatórias (herdadas + novas)

- **Estilo:** Black · imports padronizados (stdlib → Django/terceiros → locais) ·
  type hints em views e utilitários novos · comentários em PT, identificadores em EN.
- **Settings fail-hard:** `SECRET_KEY`, `DATABASE_URL` (quando houver banco) sem valor
  ⇒ `ImproperlyConfigured`. Nunca fallback silencioso.
- **Prefixo público:** ler `SCRIPT_NAME` do env e aplicar `FORCE_SCRIPT_NAME` — mover a
  célula de URL é editar o Traefik + este env, nunca cirurgia em urls.
- **Dinheiro:** `amount_cents` inteiro em models, APIs e eventos. Float é proibido.
- **Migrations:** Expand-and-Contract (nunca remover coluna/tabela usada por código em
  produção; remoção só na release seguinte). Nunca deletar/renomear migration aplicada.
- **API:** Django-Ninja. Toda célula com contrato implementa o management command
  `export_openapi` (imprime `api.get_openapi_schema()` em YAML) — o freeze depende dele.
- **Outbox (células emissoras):** tabela `outbox_event(event_id, event, version,
  payload, published_at NULL)` gravada NA MESMA transação do estado; task Huey
  (relay) publica no Redis Streams (`XADD eventos.<nome> ...`) e marca `published_at`.
- **Consumer (células ouvintes):** management command `consume_eventos` com
  consumer group = nome da célula; deduplicação por `event_id` em tabela própria;
  roda como processo da célula (mesmo container, supervisionado pelo CMD ou Huey).
- **Testes:** pytest; smokes marcados (`@pytest.mark.smoke_pix` etc. na fortaleza);
  todo invariante da célula tem seu teste-guarda referenciado em INVARIANTES.md.
