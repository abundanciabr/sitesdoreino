# ARMADILHAS — o que já custou tempo neste repositório

> Documento **vivo**, e desde 23/08/2026 **particionado**: o monólito de 1.490
> linhas (48% da carga de contexto de todo despacho — PLANO-10X, Alavanca 2) virou
> **uma entrada por arquivo** em `armadilhas/`, com um índice gerado. Cada entrada
> é tempo que um agente já perdeu — e que o próximo não precisa perder.

**Existe para uma coisa só: impedir que o mesmo problema seja resolvido do zero em
toda tarefa.** Cada redescoberta custa tokens, custa rodadas de teste e atrasa o
despacho. Se você gastou mais de dois minutos entendendo algo que não era a sua
tarefa, isso pertence aqui.

## Como usar (agente) — a regra nova, em uma frase

**Leia o `armadilhas/INDICE.md` e abra SÓ a entrada que casa com a sua tarefa.**
Ler a pasta inteira desfaz o motivo de ela existir.

1. **Antes de codar:** o §2 abaixo (partida rápida) e o `armadilhas/INDICE.md` —
   uma linha por armadilha, com a **mensagem de erro crua** como chave. Dê um
   Ctrl+F pela tecnologia que vai tocar (`django-ninja`, `importlinter`, `respx`,
   `middleware`, `mypy`…) e abra o que casar. Nada mais.
2. **Quando bater de frente com algo:** procure a mensagem de erro **crua** no
   índice. As entradas começam pelo **sintoma** justamente para serem encontradas
   assim.
3. **Ao terminar o despacho — isto não é opcional:** crie **um arquivo novo**,
   `armadilhas/NNN-slug.md` (NNN = próximo número livre), no formato
   `Sintoma → Causa → Solução → Origem`, e rode
   `python ci/indice_de_armadilhas.py` (ou `make indice`) para regenerar o índice.
   **Nunca acrescente ao fim deste arquivo, e nunca edite a entrada de outro
   agente para encaixar a sua** — arquivo novo por entrada é exatamente o que faz
   duas sessões paralelas pararem de colidir no mesmo hunk. Entrada sem sintoma
   concreto não ajuda ninguém: descreva o erro real, não a lição abstrata.
4. **Se a solução definitiva não estiver nas suas mãos** — depende de instalar algo
   na máquina, de uma conta paga, de uma permissão, de uma decisão de arquitetura —
   **registre na tabela §1 do `ARMADILHAS-OPERACAO.md` E avise o humano no seu
   relatório final, em texto claro.** Você contorna hoje para não travar; ele
   resolve de vez quando puder. Contornar em silêncio é o que faz o mesmo atrito
   voltar no próximo despacho, e no seguinte.

## Onde cada coisa mora (para não duplicar)

| Documento | Público | Guarda |
|---|---|---|
| `CONSTITUICAO.md` + `constituicoes/` | agentes | o que é **proibido** |
| `CAMINHO-DOURADO.md` | agentes | como fazer **certo** (receitas) |
| `INVARIANTES.md` | agentes | o que **não pode quebrar** |
| **`armadilhas/INDICE.md`** | **todo agente, qualquer célula** | o mapa do que a **realidade cobrou** — uma linha por armadilha |
| **`armadilhas/NNN-slug.md`** | o agente que o índice mandar abrir | a armadilha em si (sintoma → causa → solução → origem) |
| **`ARMADILHAS.md`** (este) | todo agente | a regra de uso acima + a partida rápida (§2) |
| `ARMADILHAS-OPERACAO.md` | **maestro de lote, quem mergeia, o humano** | §1 precisa-de-você · como se mergeia · painéis · §9 dívidas abertas |
| `docs/historico/RESOLVIDAS.md` | quem precisar do histórico | armadilhas já resolvidas — fora da dieta do despacho |
| `services/<celula>/LICOES.md` | agente **daquela** célula | decisões e armadilhas **só** daquela célula |
| `arquivos/painel-*.html` | **o humano** | status, fila, roadmap, incidentes |

Regra de bolso: **se serve para qualquer célula, é uma entrada em `armadilhas/`. Se
só faz sentido dentro de uma célula, é no `LICOES.md` dela. Se só o humano resolve,
é o `ARMADILHAS-OPERACAO.md`.**

> **Por que estes documentos são versionados e os painéis não:** um agente trabalha
> dentro de um `git worktree`, e worktree só contém arquivo rastreado. A pasta
> `arquivos/` está no `.gitignore` — ela **não existe** dentro do worktree, o agente
> não consegue abrir os painéis nem se quiser. Conhecimento destinado a agente
> precisa estar no git; painel é para o humano, e por isso fica de fora.

---

## §2 — Partida rápida (os 6 primeiros minutos de qualquer sessão)

```bash
# 1. Worktree próprio (RITOS.md §1) — nunca trabalhe no clone principal
git -C <raiz> fetch origin
git -C <raiz> worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa> origin/main

# 2. Docker JÁ — os DOIS instrumentos, em background, enquanto você lê a constituição.
#    O `ci-celula.yml` declara postgres E redis; célula que fala com o fio (Huey,
#    Streams) reprova o baseline com "Redis real inacessível" se só o banco subir.
docker run -d --name <celula>-pg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=<celula>_db -p 55432:5432 postgres:17
docker run -d --name plataforma-redis -p 6379:6379 redis:7   # um só atende todas

# 3. Ambiente da sessão — o CI exporta SETE variáveis (`.github/workflows/ci-celula.yml`,
#    bloco `env:`); estas são as mesmas, com os endereços locais. Faltar uma é
#    `ImproperlyConfigured` no import, e isso é ERROR de instrumento, não teste vermelho.
export PYTHONUTF8=1
export DJANGO_SECRET_KEY="ci-apenas-nunca-em-producao"
export DATABASE_URL="postgres://dev:dev@localhost:55432/<celula>_db"
export REDIS_STREAMS_URL="redis://localhost:6379/0"
export HUEY_REDIS_URL="redis://localhost:6379/1"
# Só `pagamentos` LÊ as duas de baixo — mas `mypy` importa config.settings, e o
# fail-hard do INV-P10 mora lá: ausente, a célula nem chega a rodar teste.
export MP_ACCESS_TOKEN="TEST-ci-0000000000000000-000000-fake000000000000000000000000000-000000000"
export MP_WEBHOOK_SECRET="ci-apenas-nunca-em-producao-webhook-secret"

# 4. Baseline VERDE antes de tocar qualquer arquivo (RITOS.md §1)
cd ../wt-<celula>-<tarefa>/services/<celula>
make ci
```

Se o baseline não estiver verde: **pare e reporte**. Consertar main quebrada não é
escopo de sessão de feature.

**Mas separe FAIL de ERROR antes de parar** ([INV-CI01]): baseline que reprova com
*"Redis real inacessível"*, `ImproperlyConfigured` ou `connection refused` é
**instrumento ausente na sua máquina** — suba o que falta no passo 2 e meça de novo.
"Pare e reporte" existe para `main` quebrada, não para container que você ainda não
subiu. Em 25/08/2026 a leitura literal desta seção quase abortou oito despachos por
um Redis que esta partida rápida nunca tinha mandado subir — a lista acima nasceu
dessa medição (`armadilhas/119`).

**Planeje a divisão ANTES de escrever código.** O orçamento de 15 arquivos é portão
mecânico (§5.1). Uma célula nova com modelo + migrations + clientes + middleware +
guardas de invariante **não cabe** em 15 arquivos junto com páginas. Conte os arquivos
no papel antes da primeira linha; se estourar, divida o despacho em dois PRs e diga
isso na primeira resposta, não no fim.

---
