# PARECER — "não seria melhor criar uma API para as células consumirem?"

> Pergunta do mantenedor em **29/08/2026**. Este documento é o desenho no papel
> que ele pediu antes de decidir se alguma coisa deve ser construída.
> **Nada aqui foi construído.** Escrito contra o código real do `origin/main`
> (9dfa8a2), não contra memória — inclusive contra peças que nasceram no MESMO
> dia da pergunta.

---

## A resposta em uma frase

**A pergunta são três perguntas diferentes: duas já estão respondidas e
construídas, e a terceira foi decidida ontem, com três pareceres externos, no
sentido oposto ao da ideia — por motivos que continuam valendo hoje. Sobra UM
pedaço legítimo, pequeno e mensurável, e ele não deve ser construído antes de
existir um número que o justifique.**

---

## Por que "uma API" são três perguntas

A palavra "célula" e a palavra "API" cabem em três lugares muito diferentes
deste projeto. Cada um tem uma resposta própria.

### Camada 1 — API entre as células do produto: **já existe, e é lei**

As 13 células (`services/`) **só** conversam por API HTTP e por eventos
versionados. Não é convenção, é a Lei 2, muralha 4 da `CONSTITUICAO.md`, e tem
portão mecânico: `ci/contract_freeze.py` reprova quem mudar o cardápio sem o
rito.

Medido hoje: 8 contratos OpenAPI congelados em `contracts/` (`alunos`,
`catalogo`, `checkout`, `identidade`, `leads`, `notificacoes`, `pagamentos`,
`sugestoes`), 11 contratos de evento em `contracts/eventos/`, e o
`celulas.yml` declarando quem consome quem (`checkout` → `catalogo`,
`pagamentos`; `funil` → cinco células). Um varredor (`ci/mapa_de_celulas.py`)
impede esse mapa de mentir nos dois sentidos: consumo escondido reprova,
declaração órfã também.

**Nada a fazer aqui.** E uma observação que vale registrar: o que **não**
existe, de propósito, é uma API central única — um "balcão de tudo" que todas
as células chamam. Isso seria a zona quente que a Lei 7 proíbe: o arquivo que
todo mundo toca, e cuja queda derruba tudo junto.

### Camada 2 — API para os robôs consumirem: **nasceu no dia da pergunta**

Em 29/08/2026, o PR #515 criou `fila/` — a fonte que responde "a tarefa X
existe? quem pegou? em que pé está?". Um arquivo por tarefa
(`fila/tarefas/NNN-slug.json`), um arquivo por acontecimento (`fila/eventos/`),
**nenhum campo `status` em lugar nenhum**: o estado é sempre calculado. O balcão
é `ci/fila.py` (`criar`, `listar --ao-vivo`, `pegar`, `soltar`, `concluir`,
`validar`), e a trava contra dois robôs na mesma tarefa é o almoxarife
(`ci/reservar.py`): uma referência atômica criada no servidor do GitHub, com
recusa imediata para o segundo e expiração sozinha em 3 horas.

Um servidor HTTP aqui **não melhoraria nada e pioraria uma coisa**: o robô já
tem o disco e o `gh` na mão; um serviço a mais seria mais uma casa onde o fato
mora — o que a lei anti-duplicação proíbe.

### Camada 3 — API para as TELAS lerem os fatos: **a única pergunta viva**

É aqui que a intuição da pergunta morde algo real. E é exatamente aqui que já
existe uma decisão fechada — de ontem.

---

## O que foi decidido ontem, e que a ideia da API reabriria

`docs/consultorias/central-de-orquestracao/VEREDITO.md`, fechado em 29/08/2026
com três pareceres externos independentes:

- **Gemini propôs um servidor despachante** (os robôs mandam pedido ativo, o
  painel tranca a porta no milissegundo). **Recusado:** os robôs desta casa
  falam com o mundo por git, `gh` e pipeline — pela Lei 5 nem chave SSH têm.
  Um serviço 24/7 novo seria custo mensal, superfície de ataque num repositório
  público, e uma segunda casa para os fatos.
- **Opus propôs uma célula `orquestrador` com banco Postgres**, APIs de
  `claim`/`heartbeat`/`submit` e WebSocket. **Recusado:** pressupõe robôs que
  chamam APIs de um backend próprio. Os daqui leem e escrevem arquivos, criam
  referências e abrem PRs — construir o backend seria reconstruir por fora o
  que o molde do livro + almoxarife + GitHub já garantem por dentro.
- **A decisão, textual:** *"nenhum banco novo, nenhum servidor novo, nenhuma
  lista digitada à mão."*

A tarefa `TAR-002` (construir a aba "Os robôs") já está escrita nesse desenho, e
diz com todas as letras **"zero backend novo"**. Ela prevê três blocos:

1. **O quadro da fila** — da materialização de `fila/` embutida na imagem da
   `admin` no build (o mesmo caminho do `painel.html`).
2. **Quem está com o quê AGORA** — lido **ao vivo, do navegador**, na API
   pública do GitHub: PRs abertos e reservas do almoxarife.
3. **As esperas** — a régua viva (`ci/tempos_esperados.json`) mais um resumo
   curado dos estouros.

**O ponto que importa para a sua pergunta:** o bloco 2 — justamente o que
precisa estar fresco — **já é lido ao vivo, sem backend**. O desenho decidido
resolve, por outro caminho, quase tudo o que uma API resolveria.

---

## Como a tela recebe os fatos hoje (a fotografia medida)

| Peça | Como funciona hoje | Onde está |
|---|---|---|
| O livro | 251 registros, um arquivo por acontecimento | `painel/registros/` |
| A página | Gerada: HTML + CSS + JS + dados num arquivo só. **Abrir custa UM pedido** | `painel/gerar_manifesto.js` |
| O painel online | A `admin` serve os **mesmos bytes** do repositório, byte a byte (há teste provando), com `no-store` e CSP com hash calculado a cada resposta | `services/admin/apps/core/painel.py` |
| Como a pasta chega lá | O `deploy-celula` copia `painel/` para dentro da imagem no build — fail-closed: pasta ausente para o job, não publica painel vazio | `.github/workflows/deploy-celula.yml` |
| Uma medição ao vivo que já existe | `/painel/divida.json` chama a API pública do GitHub **do servidor**, sem token, com cache de 5 minutos, e **nunca** colapsa falha em "0 pendências" | `services/admin/apps/core/divida.py` |

Duas consequências dessa arquitetura, que são o preço real dela:

1. **Fato novo ⇒ imagem nova da `admin` ⇒ deploy.** É por isso que
   `painel/**` está na lista de gatilhos do deploy. Funciona, é vigiado por
   teste-guarda, e o painel online nunca congela em silêncio. Mas é maquinário
   pesado para acrescentar um arquivo de texto.
2. **A `admin` está declarada como quem NÃO fornece API.** Em
   `ci/manifesto-de-contratos.json`: *"nenhuma célula chama a admin, e ela não
   expõe API de máquina"*. Abrir uma porta de leitura muda essa declaração e
   exige o Rito de Contrato (RITOS §3) — contrato congelado, sonda de
   autenticação, testes. Não é um JSON rapidinho.

---

## O único pedaço onde a porta de leitura ainda ganha

O veredito de ontem respondeu **onde o fato mora** (arquivo, nunca banco). Ele
não olhou uma pergunta vizinha: **com que frescor a tela vê o fato, e a que
custo de chamadas.**

O risco concreto, e é o único que encontrei: a API pública do GitHub responde
sem credencial, mas com **limite de 60 chamadas por hora, por IP** — o próprio
`divida.py` documenta isso. O bloco 2 da aba nova fará ~2 chamadas por
atualização (PRs abertos + referências de reserva), **do navegador do dono**.
Isso cabe folgado numa consulta ocasional; encosta no teto se a aba ficar
aberta se atualizando sozinha a cada poucos segundos, ou se um dia mais de uma
pessoa olhar da mesma rede.

**A saída, se isso apertar, é pequena e é exatamente uma porta de leitura:** a
`admin` faz a chamada uma vez, guarda uma cópia por poucos minutos e serve para
a tela — o mesmo padrão que o `divida.json` já usa e já provou. Cópia com prazo
não é segunda verdade: é a **Virtude da Lei 3** ("copiar dados — snapshots são
sagrados"), desde que a porta **só responda e nunca guarde nada próprio**.

Mas isso é um remédio para um problema que **ainda não foi medido**. Construir
antes de medir é justamente o erro que este projeto documentou como Classe 8
(mapa velho) e como "garantia sem mecanismo".

---

## A recomendação

**1. Não abrir a porta agora.** Construir a aba "Os robôs" (`TAR-002`) no
desenho já decidido. O motivo não é economizar esforço — é que a decisão de
ontem foi tomada com três análises externas e com conhecimento do código real,
e nada mudou desde então que a contradiga.

**2. Construir a aba com a tomada isolada** — e isto é trabalho a mais, de
propósito. Todo acesso a fato na aba passa por **um** lugar no código que diz
de onde aquele bloco vem (foto embutida na imagem × GitHub ao vivo). Com essa
costura, trocar depois por uma porta de leitura vira um PR pequeno e contido,
em vez de uma reforma na tela inteira. Sem ela, a decisão de hoje vira uma
parede amanhã.

**3. Medir três números durante as primeiras semanas de aba no ar:**

| O que medir | Como | O que o número decide |
|---|---|---|
| Quantos deploys por dia a fila provoca | contar eventos em `fila/eventos/` por dia × gatilhos do `deploy-celula` | se a materialização na imagem é sustentável |
| Quantas chamadas por hora a aba faz ao GitHub | contar no código da aba × padrão de atualização | se o teto de 60/hora encosta |
| Quantas vezes o dono viu a aba desatualizada | registro no livro quando acontecer | o único número que mede o incômodo REAL |

Só com esses três a decisão sobre a porta deixa de ser opinião — inclusive a
minha, escrita aqui.

**4. Se e quando a porta nascer, as regras que ela não pode quebrar:**

- **Só responde, nunca guarda.** Nenhuma lista própria, nenhum banco, nenhum
  campo de estado. Já custou caro aqui: duas listas de pendências coexistindo
  chegaram a discordar (7 itens numa, 6 na outra, com um invisível para o dono).
- **Cópia com prazo é permitida; verdade própria não.**
- **Falha nunca vira zero.** "Não consegui medir" é resposta; "0 pendências"
  quando não se sabe seria a mentira mais cara possível.
- **Rito de Contrato completo** (RITOS §3), porque muda a declaração da `admin`
  em `ci/manifesto-de-contratos.json`.
- **Atrás da porta da `admin`** — sessão do dono, como todo o resto de lá.

---

## O que eu não recomendo, e por quê

| Ideia | Veredito | Por quê |
|---|---|---|
| Célula `orquestrador` com banco próprio | Não | Já recusada ontem, com motivo: os robôs não falam esse idioma, e seria uma segunda casa para os fatos |
| API que **escreve** no livro ou na fila | Não | O arquivo por fato é o que torna duas sessões paralelas imunes a conflito; escrita por servidor devolve a corrida que o almoxarife acabou de matar |
| As células do produto consumirem o livro/fila | Não | Livro e fila são dados de **gestão**, não de produto. `catalogo` e `checkout` não têm nada a ganhar, e ganhariam uma dependência nova |
| Uma API central única para todas as células | Não | Zona quente proibida pela Lei 7 |

---

## Como falsificar este parecer (Lei 6)

Nenhuma afirmação acima é para ser aceita por confiança. Os comandos que a
derrubam, se ela estiver errada:

```bash
python ci/fila.py listar --ao-vivo
```

```bash
grep -n "60 chamadas por hora" services/admin/apps/core/divida.py
```

```bash
grep -n -A3 '"admin": {' ci/manifesto-de-contratos.json
```

```bash
grep -n "painel/\*\*" .github/workflows/deploy-celula.yml
```

Se algum deles contradisser o texto, **o código vence** e este documento está
errado — corrija-o no mesmo PR que descobrir a divergência.

---

## A decisão que fica com o mantenedor

1. **Seguir o desenho decidido** e construir a aba "Os robôs" com a tomada
   isolada (recomendado) — sem porta de leitura, com os três números sendo
   medidos.
2. **Construir a porta de leitura junto**, aceitando o Rito de Contrato e o
   custo, por preferir frescor garantido desde o primeiro dia.
3. **Nem uma coisa nem outra agora** — a fila já está no ar para os robôs, e a
   aba espera.
