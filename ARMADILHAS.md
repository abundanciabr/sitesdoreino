# ARMADILHAS — o que já custou tempo neste repositório

> Documento **vivo**. Cada entrada aqui é tempo que um agente já perdeu — e que o
> próximo não precisa perder. Leia antes de começar; acrescente ao terminar.

**Como usar (agente):**

1. **Antes de codar:** leia o §0 (partida rápida) e dê um Ctrl+F pela tecnologia que
   vai tocar (`django-ninja`, `importlinter`, `respx`, `middleware`…).
2. **Quando bater de frente com algo:** procure a mensagem de erro crua aqui. As
   entradas começam pelo **sintoma** justamente para serem encontradas assim.
3. **Ao terminar o despacho:** acrescente o que você aprendeu, no formato
   `Sintoma → Causa → Solução → Origem`. Não crie seção nova se já existir uma que
   sirva. Entrada sem sintoma concreto não ajuda ninguém — descreva o erro real.

**Relação com os outros documentos:** `CONSTITUICAO.md` e as constituições de célula
dizem o que é **proibido**; `CAMINHO-DOURADO.md` diz **como fazer certo**;
`INVARIANTES.md` diz **o que não pode quebrar**. Este arquivo é diferente dos três:
ele não é lei nem receita, é **memória de campo** — o que a realidade cobrou.

---

## §0 — Partida rápida (os 6 primeiros minutos de qualquer sessão)

```bash
# 1. Worktree próprio (RITOS.md §1) — nunca trabalhe no clone principal
git -C <raiz> fetch origin
git -C <raiz> worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa> origin/main

# 2. Docker JÁ (se a célula tem banco) — sobe em background enquanto você lê a constituição
docker run -d --name <celula>-pg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=<celula>_db -p 55432:5432 postgres:17

# 3. Ambiente da sessão (as 3 variáveis que todo make ci local precisa)
export PYTHONUTF8=1
export DJANGO_SECRET_KEY="ci-apenas-nunca-em-producao"
export DATABASE_URL="postgres://dev:dev@localhost:55432/<celula>_db"

# 4. Baseline VERDE antes de tocar qualquer arquivo (RITOS.md §1)
cd ../wt-<celula>-<tarefa>/services/<celula>
bash -lc 'make ci'      # note o bash -lc — ver §1.1
```

Se o baseline não estiver verde: **pare e reporte**. Consertar main quebrada não é
escopo de sessão de feature.

**Planeje a divisão ANTES de escrever código.** O orçamento de 15 arquivos é portão
mecânico (§3.1). Uma célula nova com modelo + migrations + clientes + middleware +
guardas de invariante **não cabe** em 15 arquivos junto com páginas. Conte os arquivos
no papel antes da primeira linha; se estourar, divida o despacho em dois PRs e diga
isso na primeira resposta, não no fim.

---

## §1 — Ambiente (Windows, esta máquina)

### 1.1 `make: command not found` — mas `make` está instalado

**Sintoma:** a ferramenta de Bash do agente não acha `make`, mesmo com o PATH
corrigido em `~/.bashrc`.
**Causa:** a chamada padrão do Bash do agente **não é login shell** — não lê
`~/.bashrc`. O `make` do WinGet só está no PATH por lá.
**Solução:** `bash -lc '<comando>'`. Confirmado: `bash -lc 'make --version'` funciona,
`make --version` direto não. Prefira isso a `export PATH="...:$PATH" &&` manual —
sobrevive a qualquer PATH novo que o usuário configurar depois.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 1.2 `make contrato-check` dá "OK" mesmo com o contrato divergente

**Sintoma:** `../../ci/freeze-de-contrato.sh: line 19: python3: command not found`
seguido de `✅ Freeze de contrato: OK`.
**Causa:** `python3` nesta máquina resolve para o **stub quebrado da Microsoft Store**.
As duas pontas do diff falham igual e "batem" — falso-positivo.
**Solução:** **resolvido na raiz** — o portão foi reescrito em Python
(`ci/contract_freeze.py`) e é fail-closed por construção ([INV-CI01]). Ferramenta
ausente, stdout vazio, congelado ausente ou malformado ⇒ `ERROR` (exit 2), nunca
`PASS`. O `.sh` virou wrapper fino e procura `python` antes de `python3`.
Não é mais preciso validar na mão: `python ci/contract_freeze.py <celula>` mede de
verdade nesta máquina.
**Ressalva histórica importante:** a nota original dizia "no CI real (Linux) o script
funciona de verdade — o falso-positivo é só local". Isso estava **errado por sorte**:
o mecanismo não dependia do sistema operacional, só de a ferramenta de normalização
falhar nas duas pontas. Qualquer coisa que quebrasse `python3` no runner (imagem sem
PyYAML, por exemplo) produziria o mesmo verde mentiroso no CI.
**Origem:** Prompt 2 (catalogo, PR #15); consertado no despacho `agent/ci/fail-closed`.

### 1.2b Portão de CI que fica verde porque *não conseguiu* medir

**Sintoma:** um portão imprime `✅ ... OK` (exit 0) e, logo acima, o `git`/`python`
gritou `fatal:` ou `command not found`.
**Causa:** o padrão `X=$(comando || true)` seguido de `if [[ -z "$X" ]]; then
echo "nada a fazer"; exit 0; fi`. Falha da ferramenta e "não há nada a verificar"
chegam ao `if` com o mesmo valor — vazio.
**Solução:** separar os três casos. Modelo usado em `ci/cerca-de-celula.sh`,
`ci/cross-smoke.sh` e `ci/orcamento-de-mudanca.sh`:

```bash
if ! DIFF="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR <portao>: não foi possível calcular o diff."   # não consegui medir
  exit 2
fi
if [[ -z "$DIFF" ]]; then echo "SKIP <portao>: git leu o diff e não há nada"; exit 0; fi
```

O mesmo vale para `git grep`, cujo exit code tem TRÊS significados: `0` achou,
`1` não achou, `>1` **erro** (ver `ci/guarda-de-segredos.sh`). Tratar `>1` como
"não achou" faz a guarda de segredos passar sem ter varrido nada.
**Origem:** auditoria §12 do despacho `agent/ci/fail-closed`.

### 1.2c `shutil.which("bash")` no Windows acha o WSL, não o Git Bash

**Sintoma:** `<3>WSL (…) ERROR: CreateProcessCommon:800: execvpe(/bin/bash) failed:
No such file or directory` ao rodar um `.sh` do repositório a partir de Python.
**Causa:** `C:\Windows\System32\bash.exe` (o lançador do WSL) vem antes do Git Bash
no PATH. Ele existe, é executável, e não roda script do Git Bash.
**Solução:** não basta *encontrar* a ferramenta — é preciso **sondá-la**. Ver
`_bash()` em `ci/ci.py` e `bash_utilizavel()` em `ci/tests/conftest.py`: cada
candidato roda `bash -c "printf sondagem-ok"` antes de ser aceito.
**Origem:** despacho `agent/ci/fail-closed`.

### 1.2d `/tmp/arquivo` significa dois lugares diferentes na mesma linha

**Sintoma:** um script Python escreve em `/tmp/x.json` e outro comando não acha o
arquivo, mesmo com o caminho idêntico na tela.
**Causa:** o Git Bash **traduz** argumentos POSIX ao chamar um `.exe` nativo:
`/tmp/x.json` na linha de comando vira `C:\Users\<voce>\AppData\Local\Temp\x.json`.
Mas `Path("/tmp/x.json")` **dentro** do Python vira `C:\tmp\x.json`. São dois
arquivos.
**Solução:** em script que atravessa a fronteira Bash↔Python, use caminho absoluto
explícito (ou `tempfile.mkdtemp()`), nunca `/tmp` literal.
**Origem:** despacho `agent/ci/fail-closed`.

### 1.3 `UnicodeEncodeError` / acento virando lixo na saída de comando Django

**Sintoma:** saída com emoji ou acento quebra no terminal (cp1252).
**Solução:** `export PYTHONUTF8=1` antes de rodar qualquer coisa localmente.
**Origem:** Prompt 2 (catalogo, PR #15).

### 1.4 Docker Desktop frio no meio do trabalho

**Sintoma:** 1–2 minutos parado esperando o Docker subir, bem quando você ia rodar
os testes.
**Solução:** suba o container de banco **no início da sessão**, em background, em
paralelo com a leitura da constituição. Nunca no meio.
**Origem:** Prompt 2 (catalogo, PR #15).

### 1.5 `black` local reformata o que o CI aprovaria (e vice-versa)

**Sintoma:** `black --check` verde local, vermelho no CI (ou o contrário).
**Causa:** a versão instalada globalmente nesta máquina é mais nova que a pinada no
`requirements.txt` da célula (o CI instala a pinada).
**Solução:** rode `black .` antes do commit e prefira construções cuja formatação não
muda entre versões. Se o CI reclamar de formatação que passou local, é isto.
**Origem:** Prompt 4 (checkout).

---

## §2 — Django e django-ninja

### 2.1 `AttributeError: DoesNotExist` / `AttributeError: objects`

**Sintoma:** `Session.objects` estoura `AttributeError: objects`, ou
`except Model.DoesNotExist` estoura `AttributeError: DoesNotExist` — vindo de dentro
do pydantic (`_model_construction.py`).
**Causa:** existe um `ninja.Schema` com o **mesmo nome** do model Django no mesmo
arquivo (ex.: `class Session(Schema)` e `from ...models import Session`). A classe
definida embaixo **sombreia silenciosamente** o import de cima.
**Solução:** importe o model com alias:

```python
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel
```

**Só aparece rodando os testes de verdade** — o import não falha, o lint não vê.
**Origem:** Prompt 2 (catalogo, PR #15) — e repetido em Prompt 4 (checkout), o que
mostra que a armadilha é estrutural, não distração.

### 2.2 `ConfigError: Schema for status 201 is not set in response`

**Sintoma:** handler devolve `(201, {...})` e a rota estoura.
**Causa:** rota **sem** `response=` no decorator só aceita 200.
**Solução:** devolva `django.http.JsonResponse(dict, status=N)` direto — passa batido
pelos `response_models` por completo.
**NÃO resolva com `response={200: ..., 201: ...}`:** qualquer valor não-`None` ali vira
um `ninja.Schema` dinâmico que pode vazar para `components.schemas` do documento
exportado e **quebrar o freeze de contrato**.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 2.3 `migrate` não encontra as migrations do app novo

**Sintoma:** app novo com modelo, migration criada, e o `migrate` ignora.
**Causa:** falta `apps/<novo>/migrations/__init__.py` — é **obrigatório**.
**Nota que economiza um arquivo no orçamento:** `apps/<novo>/management/commands/`
funciona **sem** `__init__.py` (namespace package — já usado em `apps/core`). O
próprio pacote do app também: `apps/core` não tem `__init__.py` e está em
`INSTALLED_APPS`.
**Conte esse arquivo no orçamento** de qualquer app novo com modelo próprio.
**Origem:** Prompt 2 (catalogo, PR #15).

### 2.4 `QuerySet.update()` fura o guarda escrito em `Model.save()`

**Sintoma:** o teste de imutabilidade passa por `save()` mas o campo muda via
`Model.objects.filter(...).update(campo=...)`.
**Causa:** `QuerySet.update()` **não passa** por `Model.save()`.
**Solução:** guarda de imutabilidade precisa existir nos **dois** caminhos — override
de `save()` **e** de `update()` num `QuerySet` customizado. (O `save()` interno do
Django usa `_update()`, com underscore, então não entra em laço com o seu override.)
**Origem:** Prompt 4 (checkout, INV-P1).

### 2.5 Middleware intercepta `/healthz` e derruba a sonda

**Sintoma:** `/healthz` passa a devolver 404 depois de instalar o middleware
CONV-SITE; o teste de fumaça quebra e, em produção, o container ficaria "unhealthy".
**Causa:** o middleware roda em **toda** requisição. `/healthz` chega sem Host de site
(é sonda do container e do gateway) e não pode depender do catálogo estar de pé.
**Solução:** isente os caminhos que não pertencem a nenhum site:

```python
CAMINHOS_SEM_SITE = ("/healthz", "/static/")
if request.path.startswith(CAMINHOS_SEM_SITE):
    return self.get_response(request)
```

**Origem:** Prompt 4 (checkout).

### 2.6 Middleware roda ANTES da autenticação do django-ninja

**Sintoma:** teste que espera 401 (sem token) recebe 404, ou tenta uma conexão HTTP
real e estoura.
**Causa:** ordem real da pilha: middleware → view/auth. O CONV-SITE resolve o site
(e chama o catálogo) **antes** de o Bearer ser conferido.
**Solução:** todo teste que bate na API precisa de Host válido **e** do mock de rede
ativo — inclusive os testes de "sem token".
**Origem:** Prompt 4 (checkout).

### 2.7 Cache de módulo vaza entre testes

**Sintoma:** teste passa sozinho e falha na suíte (ou o contrário), envolvendo
resolução de site/host.
**Causa:** o cache do CONV-SITE é um `dict` de nível de módulo — sobrevive entre
testes, inclusive cacheando o 404.
**Solução:** exponha uma função de limpeza (`limpar_cache_de_sites()`) e chame numa
fixture `autouse` antes e depois de cada teste.
**Origem:** Prompt 4 (checkout).

---

## §3 — Portões mecânicos do CI (eles reprovam de verdade)

### 3.0 Como rodar os portões sem adivinhar (comece por aqui)

Dois comandos, com perguntas **diferentes**:

```bash
python ci/doctor.py     # "este ambiente consegue executar o trabalho?"
python ci/ci.py         # "esta mudanca respeita as invariantes?"
```

`make doctor` / `make ci` na raiz fazem exatamente isso — o Makefile é fachada, a
implementação é o Python. Se `make` faltar numa máquina, os comandos acima
continuam sendo o caminho oficial.

**Leia o estado, não a cor.** Os portões falam quatro palavras ([INV-CI01]):

| Estado | Significa | Exit |
|---|---|---|
| `PASS` | mediu e está correto | 0 |
| `FAIL` | mediu e achou violação — **conserte o código** | 1 |
| `ERROR` | **não conseguiu medir** — conserte o ambiente | 2 |
| `SKIP` | declarado não aplicável, com motivo escrito | 0 |

`ERROR` nunca é "quase passou": é a CI dizendo que não sabe. Se aparecer
`ERROR contrato/<celula>` localmente, quase sempre falta variável de ambiente do
§0 — o detalhe do erro traz o comando, o exit code e o stderr crus.

`python ci/ci.py --apenas freeze,muralhas` roda um subconjunto;
`python ci/ci.py --listar` mostra o que existe.

### 3.1 `❌ ORÇAMENTO: N arquivos sem a label 'arquitetural'`

**Sintoma:** o workflow `muralhas` reprova o PR.
**Causa:** `ci/orcamento-de-mudanca.sh` conta
`git diff --name-only origin/main...HEAD | wc -l`. O limite é **15**, e é mecânico —
não é autoavaliação do agente.
**Solução:** rode esse diff **antes** de abrir o PR:

```bash
git diff --name-only origin/main...HEAD | wc -l
bash ci/orcamento-de-mudanca.sh
```

Se estourou, **divida em PRs**, não peça label. Vários despachos proíbem
explicitamente usar label para inchar escopo.
**Origem:** Prompt 2 (catalogo, PR #15 — 16 arquivos, reprovado, corrigido para 15).

### 3.2 `❌ MURALHA: este PR toca N células`

**Causa:** `ci/cerca-de-celula.sh` — 1 PR = 1 célula, sem exceção. `contracts/` nunca
muda junto com `services/` (Rito de Contrato, RITOS.md §3).
**Nota útil:** arquivos de raiz e de `ci/` **não** contam como célula — dá para
corrigir um script de CI no mesmo PR sem violar a cerca (mas eles contam no
orçamento).
**Origem:** Prompt 3a (pagamentos, PR #16 — o fix do `cross-smoke.sh` entrou junto).

### 3.3 CI vermelho por variável de ambiente que existe só na sua máquina

**Sintoma:** `make ci` verde local, `ImproperlyConfigured: variável obrigatória
ausente: X` no CI.
**Causa:** toda variável **nova e fail-hard** (`env()`, convenção CONV v1) declarada
em `config/settings.py` precisa ser espelhada no bloco `env:` do job **`rodar`** em
`.github/workflows/ci-celula.yml` — é o único lugar que fornece env vars para o
`make ci` do CI real. Seu `.env.dev` local (gitignored) sobrevive entre sessões e
**mascara** o esquecimento.
**Solução:** ao adicionar `env("NOVA")`, abra o workflow no mesmo PR. Ou, quando fizer
sentido, **evite o problema**: leia a variável no ponto de uso (`os.environ[...]`
dentro do cliente/middleware, como fazem as receitas R2 e CONV-SITE) em vez de no
`settings.py` — aí nada é fail-hard no import e o CI não precisa conhecê-la.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 3.4 `lint-imports` reprova a rota que a própria constituição manda usar

**Sintoma:** contrato `forbidden` do import-linter acusa
`methods.pix -> core.gateway -> providers...` — exatamente o caminho aprovado.
**Causa:** `type = forbidden` checa a cadeia de imports **transitiva** por padrão.
**Solução:** `allow_indirect_imports = True` no contrato — restringe a checagem ao
import **direto**, que é o que "só fale com X através de Y" realmente significa.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 3.5 `Wrong expression passed to '-m'` no cross-smoke

**Causa:** `IFS=' or '` em bash é um **conjunto** de separadores (espaço, `o`, `r`),
não a string `" or "`.
**Solução:** `printf '%s or ' "${MARKERS[@]}"` + strip do sufixo.
**Origem:** PR #14 — já corrigido em `ci/cross-smoke.sh`; fica registrado porque o
mesmo erro de `IFS` é fácil de repetir em qualquer script novo.

---

## §4 — Testes

### 4.1 Evidência vermelho→verde sem criar branch descartável

O protocolo (INVARIANTES.md, Lei 3) exige a saída **crua** do guarda vermelho sem o
fix e verde com o fix. O jeito rápido:

```bash
git stash push -- <arquivo-do-handler>   # tira só a proteção
python -m pytest tests/test_inv_pX_*.py -q   # VERMELHO
git stash pop                                 # devolve
python -m pytest tests/test_inv_pX_*.py -q   # VERDE
```

Mais rápido e limpo que criar branch/commit só para isso.
**Origem:** Prompt 2 (catalogo, PR #15).

### 4.2 `respx.models.AllMockedAssertionError: ... not mocked!`

**Sintoma:** o teste do caminho "recurso inexistente" estoura em vez de receber 404.
**Causa:** o `respx` só responde o que foi registrado; rota não registrada é erro, não
404. E ele resolve as rotas **na ordem de registro** — a primeira que casar ganha.
**Solução:** registre as rotas específicas primeiro e um catch-all por último:

```python
mock.get(url__regex=r".*/sites/[^/]+/ofertas/.+").mock(return_value=httpx.Response(404))
```

**Origem:** Prompt 4 (checkout).

### 4.3 Comparação de data/hora falha por 3 horas

**Sintoma:** o mesmo instante "não bate" antes vs. depois de um `save()`+`fetch`.
**Causa:** o Postgres normaliza `timestamptz` para UTC ao persistir — `-03:00` vira
`+00:00` na string.
**Solução:** compare via `datetime.fromisoformat(...)`, nunca string ou dict cru.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 4.4 Teste-guarda é intocável

Proibido deletar, desativar, comentar ou afrouxar teste para passar (RITOS.md §2.3).
Se o teste parece errado: **pare e reporte**, não ajuste o assert. Duas tentativas
consecutivas de correção falharam ⇒ `git reset --hard <último-verde>` e reporte —
a terceira tentativa é onde nascem labirintos.

---

## §5 — Coordenação (humano, painéis, outros agentes)

### 5.1 Mais de uma IA no mesmo repositório

**Sintoma:** PRs aparecem mergeados sem que esta sessão tenha pedido; arquivos mudam
sozinhos no meio do trabalho.
**Causa real (investigada em PR #2 e #5):** não foi invasão — o usuário seguia, em
paralelo, instruções de **outra IA**, e rodou comandos dela sem cruzar com o que esta
sessão pediu para segurar.
**Solução:** quando mais de um agente atua no mesmo repo, cheque cada `merge`/`push`
contra o que qualquer sessão pediu para segurar; e antes de editar um arquivo
compartilhado (painéis, docs de raiz), releia-o do disco — ele pode ter mudado.
**Origem:** incidentes dos PRs #2 e #5.

### 5.2 Painel HTML "some" / cards desaparecem

**Sintoma:** os cards do painel somem; a página renderiza só o cabeçalho.
**Causa:** o JS quebrou. O caso concreto: uma crase (`` ` ``) usada para formatar
código **dentro de um template literal** — que também é delimitado por crases — fecha
a string mais cedo e quebra o parse.
**Solução:** ao editar os painéis, valide antes de considerar pronto:

```bash
node -e "const fs=require('fs');const h=fs.readFileSync('arquivos/painel-X.html','utf8');
const s=h.split('<script>')[1].split('</script>')[0];
global.document={getElementById:()=>({innerHTML:'',style:{},textContent:'',addEventListener:()=>{},querySelectorAll:()=>[]})};
new Function(s)();console.log('JS OK');"
```

**Origem:** sessão de 18/08/2026, painel da Fase D.

### 5.3 O despacho colado no chat pode divergir do card do painel

**Sintoma:** o agente entrega exatamente o que foi pedido — e mesmo assim está
desalinhado com o que o painel prometia.
**Causa concreta:** o texto cru de `PROMPTS-INICIAIS.md` foi colado no chat, mas o
card do catalogo em `painel-prompts-fase-d.html` já tinha uma versão **mais segura**
(exigia `--host` obrigatório no `seed_esqueleto`, nunca hardcoded). Ninguém percebeu
até a retrospectiva, depois do merge.
**Solução:** ao receber um despacho, se houver card correspondente no painel, compare
os dois antes de começar. Divergência é decisão do humano, não do agente.
**Origem:** Prompt 2 (catalogo, PR #15) — pendência ainda aberta.

### 5.4 O painel é parte de terminar a tarefa

`arquivos/painel-fundacao.html` é o checklist vivo do dono do projeto (leigo em
código). Atualizá-lo depois de cada mudança de estado é obrigatório e **não se
pergunta antes** (`CLAUDE.md`). Só marque item como concluído com evidência real —
confirmação de merge do usuário é **gatilho para conferir** (`gh pr view <N> --json
state,mergedBy,mergeCommit`), não substituto da conferência.

---

## §6 — Pendências conhecidas (não são armadilhas, são dívidas abertas)

| O quê | Estado |
|---|---|
| `seed_esqueleto` do catalogo usa env `DOMINIO_OPERACOES` com fallback hardcoded, em vez do `--host` obrigatório que o card do painel pedia | sem decisão do mantenedor |
| Proteção de branch nativa do GitHub exige plano Pro; hoje o fallback é `.githooks/pre-push` | issue `mecanizar:` #1 |
| Relay do outbox (Huey → Redis Streams, R3) ainda não instanciado no checkout — o evento é gravado transacionalmente, mas ninguém publica | Fase D, despacho seguinte |
