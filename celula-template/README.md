# Template de célula

Ponto de partida para um serviço Django independente. Ajuste a estrutura e as
integrações ao que a célula realmente precisa.

## Estrutura sugerida

```text
services/<celula>/
├── manage.py
├── requirements.txt
├── Makefile
├── Dockerfile
├── docker-compose.dev.yml
├── .env.dev
├── config/
├── apps/
├── templates/
├── static/
└── tests/
```

## Dicas técnicas

- Mantenha segredos fora do Git e sem valor padrão silencioso. Django pode
  recusar a inicialização quando `SECRET_KEY` ou a configuração de banco
  necessária estiver ausente.
- Se a célula for publicada sob um prefixo, configure `SCRIPT_NAME` e
  `FORCE_SCRIPT_NAME` junto da rota no proxy.
- Represente valores monetários em centavos inteiros nas APIs, modelos e
  eventos.
- Ao mudar dados usados pela versão em produção, faça a transição em etapas:
  primeiro compatibilize o código com os dados existentes e remova o formato
  antigo depois.
- Se a célula expõe uma API, um comando de exportação OpenAPI pode ajudar a
  comparar o contrato publicado.
- Para eventos entre células, uma outbox transacional e consumidores idempotentes
  são opções para não perder eventos nem processá-los duas vezes.
- Os testes da célula ficam em `tests/` e podem ser executados com `make ci`.
