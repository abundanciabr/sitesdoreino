---
schema_version: 2
armadilha: 487
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - packages/outbox-relay/*
  - services/alunos/vendor/*
  - services/identidade/vendor/*
sinal:
  - "test_wheel_de_alunos_corresponde_ao_fonte_do_pacote"
  - "test_wheel_de_identidade_corresponde_ao_fonte_do_pacote"
guarda:
  tipo: sino
  dono: ci/consultar_armadilhas.py
  detector: gatilho por caminho (packages/outbox-relay, vendor de alunos e identidade)
licao: "Mudou packages/outbox-relay? NENHUMA suite roda: celulas.yml nao mapeia packages/, o ci-celula-gate fica SKIP verde e o pouso automatico integra sem um unico teste. As duas guardas que comparam wheel e fonte moram em services/alunos/tests/ e services/identidade/tests/, entao so mordem no PROXIMO PR de outra pessoa. Reconstrua as duas wheels no MESMO PR."
---

# O pacote compartilhado nao e de celula nenhuma, e por isso nao roda suite nenhuma

Medido em 18/09/2026 contra `origin/main`. `packages/outbox-relay` e a unica
biblioteca compartilhada da plataforma, consumida por `alunos` e `identidade`
como wheel vendorizada. Ela transporta os eventos de matricula e de cadastro,
ou seja, o elo que entrega a matricula depois do pagamento aprovado.

Ela nao pertence a celula alguma, e a fabrica inteira deriva o que testar e o
que publicar da pergunta "de que celula e este arquivo?".

## O que acontece hoje

```
$ python -c "... mapa_de_celulas.celulas_do_diff(['packages/outbox-relay/src/outbox_relay/relay.py'], mapa)"
celulas do diff (so packages): []
  packages/outbox-relay/src/outbox_relay/relay.py -> None
controle (services/alunos): ['alunos']
```

Com a lista vazia, o job `rodar` do `ci-celula.yml` e pulado e o `gate` imprime
`SKIP, a deteccao concluiu e nenhuma celula foi tocada`, que e verde. Com
`muralhas` verde tambem, o `pouso.yml` integra. Nenhum teste rodou.

O `deploy-celula.yml` nem comeca: seu gatilho e
`paths: ['services/**', 'painel/**', 'fila/**', 'documentos/**', 'docs/decisoes/**']`.
A producao continua rodando a wheel antiga, porque a imagem instala
`services/<celula>/vendor/outbox_relay-0.3.1-py3-none-any.whl`, e essa wheel
nao mudou. A correcao de bug fica na main e nunca chega a ninguem.

## Onde o sino toca, tarde

As duas guardas que provam que a wheel nao divergiu do fonte existem e mordem:

```
$ python -m pytest tests/test_relay_outbox_comum.py::test_wheel_de_alunos_corresponde_ao_fonte_do_pacote -q
E       AssertionError: assert 'import json\... publicados\n' == 'import json\...uir a wheel\n'
FAILED tests/test_relay_outbox_comum.py::test_wheel_de_alunos_corresponde_ao_fonte_do_pacote
```

So que elas moram em `services/alunos/tests/` e `services/identidade/tests/`.
Quem mexeu no pacote nunca as ve. Quem as ve e a proxima pessoa que mexer em
`alunos` ou em `identidade` por um motivo sem relacao nenhuma, e vai receber
uma falha que nao e dela, num arquivo que ela nao tocou.

## O que fazer

Enquanto o pacote nao tiver dono declarado em `celulas.yml`, todo PR que mexer
em `packages/outbox-relay` precisa, no MESMO PR: reconstruir a wheel,
copia-la para `services/alunos/vendor/` e `services/identidade/vendor/`, e
rodar as duas suites a mao. Assim o diff toca `services/**`, as duas guardas
rodam e o deploy dispara.

Conserto de verdade e decisao de fronteira do mantenedor, registrada na fila.
