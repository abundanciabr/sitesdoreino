# Constituição da Célula: admin (Área Administrativa)
> **Jurisdição:** governa apenas `services/admin/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 25/08/2026, PR de gênese) · **Merge:** auto-merge permitido com CI verde

## Missão
A sala de comando da plataforma: onde o mantenedor — e só quem ele autorizar —
vê métricas vivas, painéis de status, usuários, cursos e configuração, num
lugar só, pela internet. A célula **mostra e opera**; ela não é dona de dado de
ninguém. Lei do assunto: `docs/decisoes/DECISAO-celula-admin.md`; o plano
completo, com o mapa das seções por fase: `docs/decisoes/PLANO-AREA-ADMIN.md`.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/admin/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que a
  porta pergunta quem é a pessoa) e, à medida que a fase 2 andar, o contrato de
  cada célula provedora de métrica
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. **E `services/checkout/`, `services/pagamentos/` estão fora de
  mandato inclusive para LEITURA de métrica** — a seção de vendas está
  congelada por diretiva do mantenedor (22/08/2026) até ele dizer que o site
  vai vender

## Comunicação
- **Expõe:** páginas em `/admin/*` (prefixo do gateway via `SCRIPT_NAME`),
  **presas a `Host(meshcraft.top)`** no Traefik — domínio novo com área
  administrativa é decisão nova, não uma linha a menos no router. Nenhuma
  página é pública: a única rota que responde sem crachá é `/healthz`
- **Consome:** `identidade` — `GET /interno/sessao/completa` (`getSessionFull`),
  server-side, com timeout explícito, para saber quem é o dono do cookie. A
  partir da fase 2, a operação de métricas de cada provedora. Desde
  31/08/2026 (`DECISAO-login-por-senha.md`), também `POST
  /interno/pessoas/resetar-senha` (`resetPassword`) — a ÚNICA escrita desta
  célula fora do próprio banco, decidida em sessão de arquitetura com o
  mantenedor presente (o rito que a lei abaixo já exige para este gesto),
  pelo botão de reset manual de senha no prontuário do aluno. Exige o grau
  `TOKENS_SENHA_ADMIN` além do par aceito
- **Auth:** Bearer dedicado por par (`TOKENS_ACEITOS_ADMIN` na provedora). Para
  ver e-mail na resposta da `identidade`, o par precisa estar TAMBÉM em
  `TOKENS_COMPLETOS_ADMIN` — registrado na lei da identidade §6.3. **Nas
  provedoras de métrica o par entra em `TOKENS_SOMENTE_LEITURA_*`**, porque
  `TOKENS_ACEITOS_*` sozinho é conjunto plano e concederia escrita
- **Emite:** nada. Esta célula não publica evento — ela lê
- **Banco:** `admin_db` (role `admin_user` — não enxerga nenhum outro
  database). Guarda auditoria, painéis enviados, configuração chave-valor e
  textos de roadmap. **Nada de dado de outra célula copiado sem necessidade**

## Invariantes desta célula
- **A porta é fail-CLOSED, e é o INVERSO do site público.** `identidade` fora
  do ar ⇒ a área admin **não abre** (o `funil`, no mesmo caso, abre e mostra
  "Entrar"). É a aplicação literal de *reconhecer não é autorizar*
  (`DECISAO-onde-mora-a-sessao.md` §4): reconhecimento falha aberto,
  autorização falha fechada.
- **`ADMIN_EMAILS` autoriza; a resposta da `identidade` nunca.** Nem o campo
  `papel`, nem o e-mail por si. O papel é derivado a cada requisição e **nunca
  gravado** — trocar quem é admin é editar env e reiniciar.
- **Sessão válida fora da lista recebe 404, não 403** — para quem não é da
  casa, `/admin` não existe.
- **Esta célula NUNCA assina o cookie `meshcraft_sessao`** — quem assina é a
  `identidade`, e só ela (`DECISAO-celula-de-identidade.md` §6.4).
  Teste-guarda: `tests/test_inv_admin_nao_assina_sessao.py`.
- **Toda escrita gera linha de auditoria** em tabela append-only, protegida nas
  três metades que `armadilhas/023` e `/079` cobram: `save()`,
  `QuerySet.update()` **e** cascade — esta última por trigger no banco, porque
  guarda em Python é contornado por qualquer código que não importe a classe.
  Formulário novo sem linha de auditoria não mergeia.
- **A célula não escreve fora do próprio banco.** Nem no `catalogo` — a seção
  de cursos é somente-leitura por decisão do mantenedor (25/08/2026).
- **`/healthz` sobrevive ao prefixo:** qualquer isenção de middleware compara
  `request.path_info`, nunca `request.path` (`armadilhas/029`; teste-guarda em
  `tests/test_healthz_script_name.py`), e vale para as DUAS formas de entrada.
- **CSP com `frame-ancestors 'self'`** — nunca `'none'`, que proibiria o
  iframe de mesma origem de que a galeria de painéis depende
  (`armadilhas/109`).

## Definição de Pronto
`make ci` verde · guarda novo provado por mutação (vermelho sem o fix, verde
com) · diff no escopo.

## Ritos
RITOS.md §1, §2. Operação de métrica nova numa célula de contrato congelado é
Rito de Contrato (§3) — dois PRs e sessão com o mantenedor, nunca decisão
local. Escrita fora do próprio banco, login próprio, domínio separado e
qualquer coisa que toque vendas só se re-decidem em sessão de arquitetura com o
mantenedor presente, como foi a de 25/08/2026.
