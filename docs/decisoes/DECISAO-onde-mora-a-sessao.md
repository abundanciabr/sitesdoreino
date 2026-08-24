# DECISÃO — onde mora a sessão do site (e por que a EVO-01 foi reaberta)

> **Sessão de arquitetura com o mantenedor presente**, 24/08/2026, janela raiz.
> Reabre `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md`, cujo cabeçalho exige
> exatamente isto: *"Agente nenhum re-decide identidade sem uma sessão nova como esta."*
> Insumo: uma banca de quatro especialistas convocada pelo mantenedor (§6 abaixo).
>
> Este documento é a **lei** do assunto. A EVO-01 continua valendo em tudo que ela
> decidiu (§1: adultos, matrícula manda, Google prova quem é); o que muda é **o alcance
> da sessão**, que em 23/08 nem estava em jogo.

---

## 1. A pergunta mudou — e é isso, não um erro, que reabre a decisão

| Quando | A pergunta que estava na mesa | A resposta certa para ela |
|---|---|---|
| 23/08/2026 (EVO-01) | "Como o aluno entra **na Caixa de Sugestões**?" | Sessão dentro da própria `sugestoes` — mais barato, zero célula nova |
| 24/08/2026 (aqui) | "Como a pessoa entra **no site**, de qualquer página, e continua reconhecida em todas?" | Sessão com alcance de site — §3 |

**O mantenedor não errou em 23/08.** A EVO-01 respondeu bem a pergunta de 23/08. Quem
mudou foi o escopo do produto: em 24/08 ele pediu, com estas palavras, *"a liberdade de
poder entrar no site por qualquer lugar"*, e confirmou que o alvo é **o site inteiro
reconhecer a pessoa em toda página** — não só um botão de entrar espalhado.

Registrar isto importa porque a EVO-01 §7 rejeitou "célula de auth nova" e um agente
futuro vai encontrar as duas decisões e achar que uma revogou a outra por capricho.
Não revogou: **elas respondem a perguntas diferentes.**

---

## 2. O mecanismo que transformou isto numa decisão de arquitetura

O que trava não é falta de tela. É que **o crachá da sessão tem um endereço escrito
nele**, e o endereço é o prefixo público da célula que o emitiu:

- `infra/env/sugestoes.env.exemplo:21` → `SCRIPT_NAME=/forms/sugestoes`
- `services/sugestoes/config/settings.py:87` → `SESSION_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"`

Logo, em produção o cookie de sessão vale **só dentro de `/forms/sugestoes`**. O
navegador não o envia para `/pt-br/qualquer-coisa`, e o site não tem como saber que a
pessoa entrou. Espalhar botão de "Entrar" por todas as páginas resolve *onde se clica*
e **não** resolve *quem o site sabe que você é*.

E há uma segunda camada, que é a decisiva: mesmo que o cookie chegasse, o `funil`
**não saberia lê-lo** — ele é assinado com a `DJANGO_SECRET_KEY` da `sugestoes` e
carrega um `Identidade.id` que só existe no banco da `sugestoes`. O `funil` não tem
banco nenhum (`services/funil/config/settings.py:46`, `DATABASES = {}`, por decisão).

**Portanto: reconhecimento no site inteiro exige que alguém RESPONDA "quem é este?"
por HTTP.** Essa é a única forma compatível com a Lei 2 (banco por célula) e a Lei 3
(proibido ler banco alheio). A pergunta de projeto não é *se* haverá essa resposta —
é **quem a dá**.

---

## 3. A decisão: a costura primeiro, a mudança de casa depois

**Decidido: introduzir agora a PERGUNTA ("quem é este?") como contrato, mantendo a
`sugestoes` como quem responde. A célula de identidade dedicada nasce depois, e nascer
depois é trocar QUEM responde — não redesenhar quem pergunta.**

O desenho, em três fatos:

1. **A sessão passa a ter alcance de site.** O cookie é emitido em `Path=/` e com nome
   novo (§5.1). Continua sendo emitido pela `sugestoes`, continua assinado por ela.
2. **`sugestoes` ganha superfície de plataforma:** uma operação de leitura que responde
   *"quem é o dono desta sessão?"* — id opaco, nome de exibição e papel. Isso a torna
   consumida por outra célula pela primeira vez, o que **dispara o Rito de Contrato**
   (`RITOS.md` §3) — o `ci/manifesto-de-contratos.json` já previa exatamente este dia,
   por escrito: *"Se um dia outra célula precisar consumir a Caixa, o contrato entra
   pelo RITOS.md §3."*
3. **`funil` pergunta, por requisição, com cache curto** — e mostra "Entrar" ou o nome
   da pessoa em toda página, nos três idiomas.

### Por que a costura primeiro, e não a célula nova primeiro

Porque **o caro e o arriscado não é quem responde — é quem pergunta.** Depois que o
`funil` (e amanhã a escola, e a área do aluno) perguntam por um contrato, mudar o
respondedor é reapontar um endereço. Antes disso, cada consumidor novo é um redesenho.

E porque o preço é honestamente diferente:

| | Costura primeiro (**decidido**) | Célula de identidade agora |
|---|---|---|
| PRs | ~3 | 6–7 (precedente medido: Lote 6 = 9 merges; Lote 7 = 7 merges) |
| Passos do mantenedor | **0** | 1 (banco + role novos na VPS) |
| Migração de dado | nenhuma | 6 FKs viram coluna opaca, com dado já em produção |
| Rollback | intacto | **inexistente** para a célula nova até `.github/` mudar (H17) |
| Contrato / Rito §3 | **paga** | paga também |

O Rito de Contrato é pago nos dois caminhos. Tudo o mais, não.

### O que se aceita ao escolher isto (dito alto, não escondido)

**O reconhecimento do site passa a depender da `sugestoes` estar de pé.** Deploy ou
rollback da Caixa ⇒ por alguns segundos o site não sabe quem você é. Isso é aceitável
**apenas** porque vale a regra do §4, e é exatamente a dívida que a célula dedicada
paga quando nascer. Ela nasce quando a escola nascer, ou antes, se este atrito
incomodar.

---

## 4. INVARIANTE — reconhecer não é autorizar

> **Falha ao perguntar "quem é este?" ⇒ a pessoa é tratada como VISITANTE, nunca como
> autorizada. E nenhuma decisão de permissão pode ser tomada com base nesta resposta.**

As duas metades:

- **Fail-OPEN para reconhecimento.** `sugestoes` fora do ar ⇒ o `funil` mostra "Entrar"
  e a página abre normal. Não conseguir reconhecer alguém não pode derrubar a vitrine
  do site — seria trocar o raio de explosão de 1 célula pelo site inteiro.
- **Fail-CLOSED para autorização, e ela não mora aqui.** Quem decide se pode votar,
  moderar ou ver a turma continua sendo a célula dona do recurso, conferindo a sessão
  dela própria. O `funil` saber um nome **nunca** vira permissão para nada.

Sem esta separação escrita, o próximo agente usa a resposta de `/sessao` como crachá de
acesso, e aí um fail-open de reconhecimento vira um fail-open de autorização — que é a
família do bug mais caro da Fase D (RETROSPECTIVA §4).

**Teste-guarda no mesmo PR do consumidor** (Lei 8): com a `sugestoes` dublada fora do
ar, a página do `funil` responde 200 mostrando "Entrar" — e nenhuma rota que exija
sessão passa a permitir nada.

---

## 5. Armadilhas conhecidas deste caminho — todas com correção decidida

### 5.1 Trocar `SESSION_COOKIE_PATH` sem trocar o NOME do cookie = sessão fantasma
O navegador guarda cookies por (nome, domínio, **caminho**). Publicar `sugestoes_sessao`
em `Path=/` sem renomear deixa **dois** cookies de mesmo nome convivendo — o velho em
`/forms/sugestoes`, o novo em `/` — e qual deles o servidor lê é ambíguo por caminho.
**Decidido: renomear o cookie no mesmo PR** (`meshcraft_sessao`). Efeito colateral
aceito: **todo mundo que estiver logado hoje é deslogado uma vez**, e reentra com um
clique (o fluxo já trata sessão ausente com 302 para a porta, nunca com erro).

### 5.2 O `redirect_uri` do Google
O aplicativo OAuth atual já tem **dois** endereços de retorno cadastrados pelo
mantenedor em 24/08/2026: o de hoje (`/forms/sugestoes/entrar/google/retorno`) e o
neutro (`/entrar/google/retorno`), cadastrado justamente para o dia da célula dedicada.
**Nada a fazer agora** — o fluxo continua usando o primeiro, montado por `reverse()`
(`services/sugestoes/apps/core/views.py:69`), jamais à mão.

### 5.3 O papel continua derivado, nunca gravado
A EVO-01 §4 promete que trocar quem é staff é editar uma variável e reiniciar. A
resposta de "quem é este?" **calcula** o papel na hora, como hoje
(`services/sugestoes/apps/core/sessao.py:124`). Papel dentro do cookie, ou gravado na
linha da `Identidade`, quebraria essa promessa em silêncio.

### 5.4 Nenhuma FK atravessa fronteira, hoje nem depois
`services/sugestoes/tests/test_inv_sem_fk_para_fora.py` já guarda isto e **não muda
neste caminho** — `Identidade` continua dentro de `apps.sugestoes`. No dia da célula
dedicada, esse guarda fica vermelho sozinho e aponta o substituto que ele próprio
nomeia: *snapshot em coluna opaca, nunca FK*.

### 5.5 O papel `professor` NÃO nasce agora
`grep -rn "professor"` no repositório: **zero ocorrências**. É requisito novo, sem dono
e sem tela. Ele nasce com a escola, que é quem sabe o que é uma turma. Enquanto isso,
**não reaproveite a lista de staff para professor** — quem entra nela ganha moderação
da Caixa (`services/sugestoes/apps/core/moderacao.py`), que ninguém decidiu dar a
professor. Papel novo = lista própria.

---

## 6. A banca (24/08/2026) — o que ela mudou

O mantenedor pediu segunda opinião sobre a proposta original (célula de identidade
agora). Quatro pareceres independentes, com acesso ao repositório. **Voto: 3 a 1 contra
a proposta.** O que sobreviveu e virou este documento:

- **Achado mecânico decisivo:** `/{idioma}/login` **não pode** ser servido por célula
  nova — `ci/tests/test_rotas_sem_forma_de_locale.py` reprova router cujo primeiro
  segmento tenha forma de idioma. Quem serve `/{idioma}/*` é o `funil`, pelo catch-all.
  A tela fica no `funil` em **qualquer** cenário.
- **Premissa derrubada:** "admin não tem matrícula" já estava resolvido desde 23/08 —
  staff entra sem matrícula, e há guarda provando que entra até com a `alunos` fora do
  ar (`test_inv_entrada_staff_sem_matricula.py`).
- **Garantia sem mecanismo:** a promessa de "confiro se a tabela está vazia antes de
  mexer" **não tinha como ser cumprida** (sem SSH, Lei 5; nenhum endpoint conta).
  Retirada. Se um dia for preciso, o molde existe: `deploy-infra.yml:232`.
- **Custo real de célula nova**, medido no próprio histórico: Lote 6 = 9 merges; Lote 7
  = 7 merges, com o passo manual falhando **3 vezes**.
- **Célula nova nasce sem rollback** (`.github/workflows/rollback.yml` tem lista fixa) —
  H17 item (2) segue aberto e é **pré-requisito** do dia da célula dedicada.

O voto dissidente (cadeira de IAM) foi quem apontou o §2 deste documento — que o cookie
não alcança o site — e é por isso que o caminho barato entrega a **costura**, e não
apenas uma tela bonita.

---

## 7. O que fica decidido para o próximo agente

1. **Não** crie célula de identidade sem uma sessão como esta, com o mantenedor
   presente — e, quando criar, comece resolvendo H17 (rollback) **antes** do deploy.
2. **Não** mova identidade para `alunos`: matrícula é dado de pedido; admin e professor
   não têm `order_id`. Já descartado em 24/08.
3. **Não** use a resposta de "quem é este?" para autorizar coisa alguma (§4).
4. A tela de entrada mora no `funil`, nos três idiomas, hoje e depois.

## 8. Estado

**Decidido em 24/08/2026.** Nenhuma pendência do mantenedor — os dois passos que
existiam (banco novo, endereço no Google) foram, respectivamente, **eliminados** por
esta escolha e **já executados** por ele.
