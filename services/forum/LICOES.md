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

---

## 5. Mudar permissão de área semeada EXIGE migração de dados — o `semear_areas` não alcança (30/08/2026)

**Sintoma.** O mandato do mantenedor mudou o desenho das áreas (`duvidas` e
`mostre-seu-trabalho` deixaram de ser públicas). Você edita as constantes de
`apps/forum/management/commands/semear_areas.py`, a suíte fica verde, o PR
mergeia — e **em produção nada muda**. As áreas continuam públicas.

**Causa.** O comando é `get_or_create` pelo `slug` e **de propósito não
atualiza o que já existe** (§ do próprio arquivo: semear é dar o primeiro
empurrão, não ficar de dono). Ele alcança um banco vazio; nunca o banco que já
tem as áreas. E toda a suíte roda em banco vazio, então ela concorda com você.

É a família do *falso-verde por cenário fraco*: o teste mede o mundo em que a
mudança é trivial, e o mundo que importa é o outro.

**Solução — a migração de dados, e ela vem ANTES da restrição.** Quando a
mudança é de permissão, o par correto é:

```python
operations = [
    migrations.RunPython(fechar_o_que_ja_esta_aberto, nao_reabre),  # 1º
    migrations.AddConstraint(...),                                  # 2º
]
```

A ordem não é estilo: com a restrição primeiro, o `AddConstraint` encontra as
linhas antigas em desacordo e o `migrate` **morre no meio, na VPS**, com o banco
a meio caminho e o container em crashloop. O `CMD` do `Dockerfile` desta célula
roda `migrate --noinput` no boot — quem paga esse erro é a produção, não a CI.

E o reverso do `RunPython` **não desfaz**: um `migrate` para trás é coisa que se
faz às pressas, num rollback, sem ninguém lendo o código. Reabrir área ali seria
expor mensagem de menor de idade a estranho como efeito colateral de um comando
de emergência.

**Corolário.** A regra que protege criança não podia depender de alguém lembrar
dela: junto com a migração desceu uma `CheckConstraint`
(`pagina_publica_so_a_escola_fala`) que torna a combinação proibida
**impossível**, inclusive por `QuerySet.update()` — que fura qualquer guarda
escrito em `Model.save()` (`armadilhas/023`).

---

## 6. Testar formulário desta célula tem uma pegadinha própria: o cabeçalho `cookie` apaga o CSRF

O fórum reconhece a pessoa por um cookie que vem de OUTRA célula, então a forma
óbvia de simular login nos testes é `headers={"cookie": "meshcraft_sessao=..."}`.
Isso funciona em todo teste **menos** nos que atravessam um `<form>`: o cabeçalho
substitui o pote de cookies inteiro e leva junto o `forum_csrf`. O detalhe, com
o caminho certo, está em `armadilhas/204`.

O que fica para esta célula: `tests/test_escrever.py` tem **um** teste com
`Client(enforce_csrf_checks=True)` percorrendo a tela inteira. Ele é o único que
prova o formulário — todos os outros provam a permissão e passam por cima da
porta de CSRF.
