# Roteador do Traefik sem `tls`: o endereço cai no catch-all, com o deploy VERDE

**Sintoma.** Você acrescenta um roteador em `infra/traefik/dynamic/plataforma.yml`,
o `deploy-infra` fica verde, e o endereço novo responde **404** — ou pior, serve
a página de outra célula. Nada fica vermelho em lugar nenhum.

O caso real (29/08/2026): `meshcraft.top/docs/` devolvia 404 servido pelo funil,
enquanto `/forum/` — acrescentado no MESMO arquivo, no commit seguinte —
funcionava.

**Causa.** O roteador declarou `entryPoints: [websecure]` e **não declarou
`tls`**:

```yaml
    docs:
      rule: "Host(`meshcraft.top`) && PathPrefix(`/docs`)"
      priority: 10
      entryPoints: [websecure]
      middlewares: [seguranca-admin]
      service: admin
      # ← faltou `tls: {}`
```

O `websecure` é o entrypoint de HTTPS. Um roteador ali que não diz como servir
TLS **não é criado** — e a requisição segue para o próximo que casar, que aqui é
o catch-all `PathPrefix('/')` do funil (priority 1). O YAML continua válido, o
compose valida, o deploy passa.

**Por que é caro de achar.** Tudo o que você conferiria parece certo:

- a regra está na tabela, e o `git show origin/main:…` mostra o roteador lá;
- o `PathPrefix` está correto, o `service` existe, a prioridade é maior que a do
  catch-all;
- o `deploy-infra` está verde — inclusive reaplicado duas vezes;
- e um roteador IRMÃO, no mesmo arquivo, funciona.

**Como reconhecer de fora, em um comando.** Compare os **cabeçalhos de
segurança** do endereço quebrado com os de um endereço que você sabe que vai
para a mesma célula. Cada cadeia de middleware do Traefik deixa uma assinatura
diferente:

```bash
curl -sD- -o /dev/null https://SEU-DOMINIO/o-endereco-novo | grep -i "x-frame\|content-security"
curl -sD- -o /dev/null https://SEU-DOMINIO/um-endereco-que-funciona | grep -i "x-frame\|content-security"
```

No caso real, `/mapa-ia/` voltava `X-Frame-Options: SAMEORIGIN` **e** o CSP da
célula `admin`; `/docs/` voltava `DENY` e **nenhum CSP** — exatamente os
cabeçalhos da raiz do site. Quem respondia era o funil, e isso fecha o caso sem
entrar na VPS.

**Solução.** Acrescente `tls: {}` — é o que todos os outros roteadores do
`websecure` fazem. Depois **reaplique a infra** e meça de fora; o deploy verde
não é prova.

**Quem faz valer, desde 29/08/2026.**
`ci/tests/test_rotas_sem_forma_de_locale.py::test_todo_roteador_https_declara_o_cadeado`
— todo roteador em `websecure` precisa declarar `tls`, com prova adversarial nos
dois sentidos. Roteador **sem** `entryPoints` atende todos os entrypoints,
inclusive o `web` (porta 80), onde `tls` não faz sentido: fica fora do guarda, de
propósito.

**A classe, e ela é maior que o caso.** É falso-verde de infraestrutura: o portão
mede a **sintaxe** (YAML válido, compose de pé, containers saudáveis) e o que
quebra é a **semântica** (um roteador que existe no arquivo e não existe no
Traefik). Todo portão que valida configuração sem exercitar o comportamento tem
esse ponto cego — e a defesa é sempre a mesma: **prova de fora**, medindo o que o
mundo recebe.
