# Alarme cujo CONSERTO é um deploy tranca a porta por dentro se ele barrar deploys

**Sintoma (o que você quase constrói):** você acrescenta um workflow novo que
mede produção e grita quando algo está errado — um vigia de certificado, uma
sonda de disponibilidade, um medidor de fila. Tudo verde no PR, testes passando.
E aí, no primeiro dia em que ele fica vermelho de verdade, **nenhuma entrega
passa mais** — inclusive a entrega que consertaria justamente o que ele acusou.

**Causa:** `ci/portao_de_deploy.py::vermelhos_nao_previstos` busca os runs por
`actions/runs?head_sha=<SHA>` e barra o deploy se qualquer workflow **fora da
lista `conhecidos`** estiver vermelho naquele commit. É fail-closed de propósito
("check novo não nasce fora do portão sem alguém decidir isso por escrito") — e
está certo, porque a alternativa é um check novo entrar sem ninguém julgar se
ele deve ou não travar produção.

O laço se fecha quando o conserto do alarme é, ele mesmo, um deploy. O caso
concreto: um cadeado vermelho se conserta com qualquer diff em
`infra/traefik/**`, que recria o container e re-tenta o ACME (`armadilhas/018`).
Se o vigia do cadeado barrasse deploys, o único caminho para consertá-lo estaria
fechado pelo próprio defeito que ele acusou.

**A pergunta que separa os dois casos**, e que vale para todo check novo:

> Este check mede ESTE COMMIT, ou mede o MUNDO?

- **Mede o commit** (`muralhas`, `ci-celula`, `alarme-main`): vermelho dele é
  motivo legítimo para não publicar. Vai em `exigidos`.
- **Mede o mundo** (certificado vencendo, servidor fora do ar, fila crescendo):
  vermelho dele não diz **nada** sobre se este código pode ir para produção.
  Acoplar os dois é inventar um bloqueio que ninguém pediu — e, quando o
  conserto passa pelo deploy, é um bloqueio que se auto-alimenta.

**Solução:** declare o workflow em `conhecidos` **sem** pô-lo em `exigidos`:

```python
conhecidos = set(exigidos) | {MURALHAS, VIGIA_DO_CADEADO}
```

Quem grita quando ele fica vermelho é a issue do próprio workflow (o padrão do
`alarme-main`: job com `needs:` + `if: failure()` + `issues: write`), não o
portão. E **não** o promova a `exigidos` "por segurança": um workflow que roda
no relógio quase nunca tem run no `head_sha` de um deploy, então exigi-lo faria
todo deploy esperar por algo que não existe — trocar um bloqueio raro por um
bloqueio diário.

**O teste que a isenção exige — e por que UM só não basta.** Escreva o par:

1. o alarme vermelho **não** barra (a isenção existe);
2. um workflow desconhecido vermelho **continua** barrando (a isenção é estreita).

Sozinho, o primeiro passaria também se alguém tivesse desligado a regra inteira
— que é como uma isenção legítima vira buraco. E acrescente um terceiro,
estrutural, que leia a fonte e afirme que o nome está em `conhecidos` e **fora**
de `exigidos`: medido em 29/08/2026, foi só esse terceiro que ficou vermelho ao
desfazer a declaração, porque os dois primeiros montam `conhecidos` à mão e
testam a FUNÇÃO, não a FIAÇÃO.

**Origem:** vigia do cadeado (29/08/2026), o primeiro workflow do repositório a
acordar pelo relógio em vez de por evento.
