# Lições da célula `forum`

O que já custou tempo **dentro desta célula**. O que serve a qualquer célula vai
para `armadilhas/` — não para cá (regra do `CLAUDE.md`).

Lei da célula: `docs/decisoes/DECISAO-forum-da-escola.md`.
Constituição: `constituicoes/AGENTS.forum.md`.

---

## 1. A gênese esbarra em dois portões que se contradizem (28/08/2026)

**Sintoma:** o PR de gênese não fica verde de jeito nenhum. Ou `muralhas`
reprova em `test_painel_ia_atualizado.py`, ou `ci-celula-gate` reprova com
*"o diff toca 2 células e este job testa uma só"*.

**Causa:** `ci/tests/test_painel_ia_atualizado.py` exige que toda pasta de
`services/` apareça em `painel/ia/` — *"no mesmo PR que criou a célula"*. Mas
`ci/ci.py::celulas_tocadas` mapeia `painel/**` ⇒ célula `admin`, e o
`ci-celula-gate` reprova `N > 1`. **Os dois são required na `main`**: num PR só,
não ficam verdes ao mesmo tempo.

**Solução — a ORDEM, sem afrouxar portão nenhum:**

1. Um PR tocando **só `painel/ia/`**, citando a célula que ainda vai nascer. O
   guarda do mapa não a cobra, porque `services/<nome>` ainda não existe.
2. Depois o PR da célula (`services/<nome>` + arquivos-lei). O guarda do mapa já
   encontra o nome citado.

**Duas coisas NÃO podem ir no PR do mapa:**

- A **constituição** (`constituicoes/AGENTS.<x>.md`) —
  `ci/tests/test_constituicoes.py` reprova constituição órfã.
- O **registro do livro** (`painel/registros/`) — é `painel/`, ou seja, célula
  `admin`: recria o `N > 1`. Ele vai em PR próprio, **depois** do merge da
  célula.

Resultado prático: a gênese desta célula foram **três** PRs (mapa, célula,
registro) mais o pagamento de uma dívida de livro alheia que a porta do merge
cobrou no caminho.

---

## 2. O deploy fica vermelho de propósito até a infra existir

Entre o PR de gênese e o PR de `infra/`, o `deploy-celula` desta célula **falha
sempre**, com esta mensagem:

```
ERRO: 'forum' não tem serviço algum em /opt/plataforma/docker-compose.yml.
Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira.
```

**Isso é o script se recusando a fazer besteira, não um defeito.** É a
`armadilhas/088`. Não se conserta com rerun, e emendar o compose no mesmo PR do
código é a `armadilhas/134` — trava os dois deploys e nenhum rerun sai.

---

## 3. A busca em português tem dois buracos conhecidos, e eles estão travados em teste

Medido contra PostgreSQL 17 real, não suposto: `modelagem` **não** casa com
`modelagens` (plural em `-ens`), e `chapéu` **não** casa com `chapeu` (acento é
significativo). Detalhe completo, com a tabela do que casa e o que não casa, em
`armadilhas/154`.

O que importa aqui: `tests/test_modelo_de_dados.py` tem um teste que **exige o
comportamento limitado de hoje**. Quando a cura chegar (extensão `unaccent` no
provisionamento + sinônimos), ele fica vermelho — e é assim que se descobre que
a cura chegou, em vez de o limite virar folclore.

**Corolário de método:** essa afirmação errada só foi pega porque a suíte roda
contra um PostgreSQL de verdade. Com SQLite ou dublê, ela teria entrado no
repositório como se fosse verdade.

---

## 4. A marca de leitura é marca-d'água — nunca uma linha por mensagem

O caminho curto (`uma linha por pessoa por mensagem lida`) parece óbvio e é o
erro caro: com 200 alunos e 20 mil mensagens são milhões de linhas para
responder *"tem coisa nova?"*, e o conserto depois é migração na maior tabela do
sistema.

O desenho correto — o mesmo do Discourse — é `MarcaDeLeitura` (uma por pessoa
por área) mais `TopicoLido` (as poucas exceções lidas depois da marca).
Guarda: `test_ler_uma_area_inteira_cria_UMA_linha_e_nao_uma_por_mensagem`,
que cria 30 mensagens e exige **uma** linha de leitura.
