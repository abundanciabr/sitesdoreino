---
schema_version: 2
armadilha: 487
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - packages/outbox-relay/*
  - services/alunos/vendor/*
  - services/identidade/vendor/*
sinal:
  - "test_as_wheels_vendorizadas_sao_as_wheels_deste_fonte"
  - "test_wheel_de_alunos_corresponde_ao_fonte_do_pacote"
  - "test_wheel_de_identidade_corresponde_ao_fonte_do_pacote"
guarda:
  tipo: CI
  dono: ci/tests/test_portao_do_pacote_compartilhado.py
  detector: test_as_wheels_vendorizadas_sao_as_wheels_deste_fonte
licao: "Mudou packages/outbox-relay? celulas.yml nao mapeia packages/: o ci-celula-gate fica SKIP verde e o deploy-celula nem comeca. Quem fecha isso e o portao do pacote compartilhado, no muralhas de TODO PR, e ele reprova enquanto as wheels de alunos e identidade nao forem refeitas. Conserto: python ci/portao_do_pacote_compartilhado.py --reconstruir, que faz o diff tocar services/** e o deploy sair."
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

## O que guarda isto desde 18/09/2026 (TAR-465)

`ci/portao_do_pacote_compartilhado.py`, provado por
`ci/tests/test_portao_do_pacote_compartilhado.py`. A suite `ci/tests/` roda no
`muralhas.yml`, que e o unico workflow sem filtro de caminho, entao o portao ve
o PR que so mexe em `packages/` (o SKIP verde do `ci-celula-gate` continua la, e
deixou de ser suficiente para integrar).

O portao compara cada wheel de `services/*/vendor/` com
`packages/outbox-relay/src/`, modulo a modulo, e confere que a versao do nome,
a versao da METADATA e a versao do `pyproject.toml` sao a mesma, e que o
`requirements.txt` da celula instala aquela wheel. Quem consome o pacote nao e
lista escrita a mao: e quem tem a wheel na pasta `vendor/`.

```
$ python ci/portao_do_pacote_compartilhado.py
  alunos/outbox_relay-0.3.1-py3-none-any.whl      FAIL   1 divergencia(s) entre a wheel e o fonte
  identidade/outbox_relay-0.3.1-py3-none-any.whl  FAIL   1 divergencia(s) entre a wheel e o fonte
RESULTADO  FAIL
CONSERTO: python ci/portao_do_pacote_compartilhado.py --reconstruir
```

Fonte divergindo da wheel e FAIL; o que impede a MEDICAO (pacote fora do lugar,
wheel ilegivel, zero consumidores) e ERROR, nunca PASS. Apagar a wheel nao e
caminho para o verde.

O conserto em um comando existe porque ate hoje esse passo nao tinha comando
nenhum no repositorio: `--reconstruir` constroi a wheel do fonte e a entrega a
todos os consumidores. Como so isso deixa o portao verde, o PR passa a tocar
`services/**`, e ai as duas suites de celula rodam e o `deploy-celula` dispara.

O pacote continua sem celula em `celulas.yml`: declarar uma so celula deixaria a
outra sem testar, e criar uma celula `packages` pede entrada no manifesto,
`make -C services/packages ci` e `docker build services/packages`, que nao
existem. Isso continua sendo decisao de fronteira do mantenedor.
