# DECISÃO: a página real antes do experimento

> **Sessão com o mantenedor presente, 19/09/2026.** Ele recebeu de fora uma
> proposta de "Experimentation & Conversion Architecture" (control plane, data
> plane, analytics plane, camadas de exclusão mútua, SRM, teste sequencial,
> CUPED, bandits contextuais, knowledge graph de aprendizados e IA geradora de
> hipóteses) e perguntou o que seria preciso para implantá-la aqui.
>
> A resposta foi que a arquitetura está certa e o momento está errado. Ele
> decidiu inverter a ordem. Este documento é a lei desse assunto, e é a única
> fonte para quem chegar depois: seis a sete PRs em quatro células saem daqui,
> e a casa não admite mudança desse tamanho sem decisão escrita.

---

## 1. A decisão

**Página real e telemetria do funil antes de qualquer infraestrutura de
experimentação.**

Nada de plataforma de teste, de camada, de alocador ou de análise entra nesta
plataforma enquanto a página de oferta não estiver escrita de verdade e
enquanto cada passo do visitante não estiver virando fato no livro.

## 2. O estado medido de hoje

Tudo abaixo foi lido de `origin/main` no dia da decisão, nunca da árvore de
trabalho. O comando vem junto para que quem duvidar confira em vez de
acreditar.

**1. A página de oferta tem 62 linhas:** título, preço, botão e um formulário
de novidades. Não há promessa, mecanismo, prova, objeção, garantia nem
perguntas frequentes.

```
git show origin/main:services/funil/templates/funil/landing.html | wc -l
62
```

**2. Nenhum dos 43 contratos de evento descreve a visita.** Nenhum fala de
visita, de página vista ou de clique.

```
git grep -il -E "visit|visita|pageview|page_view|impressao" origin/main -- 'contracts/eventos/*'
(sem saída)
```

**3. O primeiro fato do funil é `pedido.criado`**, publicado pela `checkout`.
Antes dele o livro não sabe que alguém esteve na casa. O que a página captura
hoje no formulário de novidades vira uma linha interna da `leads`
(`TimelineEvent`, `lead.upsert`), que não é contrato e não chega ao livro.

```
git grep -rln "pedido.criado" origin/main -- services/
```

**4. Não existe identidade de visitante.** Nenhuma célula e nenhum contrato
conhecem a ideia de alguém que está na casa e ainda não se identificou.

```
git grep -rln -E "visitor_id|visitante_id|anonymous_id|device_id" origin/main -- services/ contracts/
(sem saída)
```

**5. `services/metricas` já é um livro de fatos imutável, append-only e
idempotente**, e serve de base sem mudança nenhuma: `Evento.save()` recusa
alteração, `EventoQuerySet.update()` e `.delete()` fecham também o caminho de
conjunto, e `event_id` é único.

```
git show origin/main:services/metricas/apps/fatos/models.py
```

**6. Versionamento imutável já é hábito da casa.** `Offer.version` existe
desde a primeira receita, com a regra escrita no próprio modelo: publicada não
é editada destrutivamente, mudar preço nasce como versão nova.

```
git show origin/main:services/catalogo/apps/ofertas/models.py
```

A soma disso é curta de dizer: a casa mede dinheiro com rigor e não mede nada
do que acontece antes do dinheiro.

## 3. A conta que decidiu

Amostra por braço para duas proporções, alfa 0,05 bilateral, poder 80%,
fórmula com variância agrupada sob a hipótese nula.

```python
import math
from statistics import NormalDist

Z_ALFA = NormalDist().inv_cdf(1 - 0.05 / 2)
Z_PODER = NormalDist().inv_cdf(0.80)

def por_braco(base: float, lift: float) -> int:
    tratado = base * (1 + lift)
    media = (base + tratado) / 2
    termo_nulo = Z_ALFA * math.sqrt(2 * media * (1 - media))
    termo_alt = Z_PODER * math.sqrt(base * (1 - base) + tratado * (1 - tratado))
    return math.ceil(((termo_nulo + termo_alt) / (tratado - base)) ** 2)
```

```
z(alfa/2)=1.959964  z(poder)=0.841621
metrica             base   lift   visitantes/braco    total
compra               2%   +20%             21,109   42,218
compra               2%   +50%              3,826    7,652
checkout_started    10%   +20%              3,841    7,682
checkout_started    10%   +50%                686    1,372
clique no CTA       30%   +20%                963    1,926
clique no CTA       30%   +50%                163      326
```

A leitura, em uma frase: um teste A/B honesto em compra custa dezenas de
milhares de visitantes, e a casa ainda não viu a primeira compra real de
cartão (o `PLANO-MESTRE-APPMAX-NO-CARTAO.md` é da mesma data desta decisão).

Duas consequências que a tabela impõe ao desenho:

1. **A métrica que dá para testar primeiro é a de cima do funil.** Clique no
   CTA move com 163 visitantes por braço; compra pede 21.109. Quem só mede
   compra fica sem leitura por meses.
2. **Medir cada degrau não é luxo, é o que torna o teste possível.** Sem
   seção vista e CTA clicado no livro, a única métrica disponível é a mais
   cara de todas.

## 4. O que se constrói agora

Sete PRs, em quatro células. A dependência é a ordem: nada começa antes da
raiz, e cada linha diz de quem depende.

| # | Célula | O que entrega | Depende de |
|---|---|---|---|
| 1 | `contratos` | Aditivo de páginas no `catalogo` (OpenAPI) e quatro eventos novos do `funil`: `funil.pagina-vista`, `funil.secao-vista`, `funil.cta-clicado`, `funil.lead-capturado`. | raiz de tudo |
| 2 | `catalogo` | `Page`, `PageVersion` imutável, `PageDraft` e o vocabulário de slots semânticos. | 1 |
| 3 | `funil` | `visitor_id` de primeira parte, gerado e guardado pelo próprio domínio. | 1 |
| 4 | `funil` | A página de oferta renderizada a partir da estrutura, no lugar do template fixo de 62 linhas. | 2 |
| 5 | `admin` | A tela onde o mantenedor escreve a copy nos slots e publica uma versão. | 2 |
| 6 | `funil` | A telemetria: seção vista, CTA clicado e lead capturado, publicados como eventos. | 1, 3, 4 |
| 7 | `admin` | O funil na tela, calculado do livro de fatos. | 6 |

O PR 1 é a raiz porque contrato nesta casa cresce por adição e é conferido por
máquina (Lei 2, muralha 4). Escrever o modelo antes do contrato inverteria a
ordem que o `ci/contrato_aditivo.py` cobra.

O PR 7 não precisa de nada novo na `metricas`: os eventos chegam pelo relay e
caem no `Evento` como qualquer outro fato, e a tela é uma leitura.

## 5. O que se guarda da proposta externa

Estas seis coisas são baratas agora e caras depois. Elas entram nos PRs da
escada acima, não numa fase futura.

1. **Nomes semânticos, nunca `div_47_text`.** A seção diz o assunto
   (`promessa`, `mecanismo`, `prova`, `objecao`, `garantia`, `faq`) e o slot
   diz o papel do texto dentro dela (`headline`, `depoimento`, `preco_texto`).
   Nome estrutural sobrevive à troca de layout; nome posicional morre no
   primeiro redesenho e leva junto todo histórico que apontava para ele. A
   lista canônica das duas coisas é fixada pelo PR 1 da escada, e este
   documento não a congela.
2. **Quatro coisas separadas, com nomes separados:** o template (a forma), a
   especificação (quais slots aquela forma tem), a versão (o conteúdo
   congelado) e a página renderizada (o que o visitante recebe). Fundir duas
   delas custa uma migração depois.
3. **Versão imutável.** `PageVersion` publicada não se edita: editar cria a
   próxima. É a regra que `Offer.version` já pratica, e é a única forma de um
   evento de ontem continuar apontando para o que a pessoa realmente viu.
4. **Identidade persistente de visitante.** `visitor_id` de primeira parte,
   gerado pelo `funil`, sem o qual nenhuma contagem de funil é contagem de
   gente: é soma de requisições.
5. **O evento carrega ID e versão, nunca o texto da copy.** `page_id`,
   `version`, `slot`, `site_id` (Lei 9). O texto mora na versão; duplicá-lo no
   evento faria o livro engordar sem ganhar informação e criaria duas verdades
   sobre a mesma frase.
6. **Falha de medição jamais derruba a página.** Telemetria é fail-open: o
   endpoint de evento fora do ar deixa o visitante comprar. A casa já pratica
   a distinção (fail-open para reconhecimento, fail-closed para autorização e
   para dinheiro), e medição fica do lado do reconhecimento.

## 6. O que fica adiado, e o gatilho que destrava cada coisa

Nada aqui está recusado. Cada item tem uma condição objetiva, e no dia em que
a condição acontecer o item entra sem precisar de decisão nova.

| Adiado | Gatilho que destrava |
|---|---|
| **SRM** (conferência da razão de amostra) | O primeiro experimento que dividir tráfego, qualquer que seja o volume. |
| **Teste sequencial** | O primeiro experimento que precisar durar mais de duas semanas, ou a primeira vez que alguém quiser ler o resultado antes do fim. |
| **Camadas de exclusão mútua** | Dois experimentos precisarem rodar ao mesmo tempo sobre a mesma página. |
| **Holdout global** | Dez vitórias embarcadas sem nenhuma medição do efeito somado. |
| **Hierarquia formal de métricas** (guarda, secundária, principal) | O primeiro experimento que subir uma métrica e derrubar outra. |

## 7. O que fica descartado até segunda ordem

| Descartado | Por quê, em uma frase |
|---|---|
| **CUPED** | Reduz variância usando o comportamento anterior de cada pessoa como covariável, e não existe histórico por visitante para usar. |
| **Bandits contextuais** | Alocar tráfego bem exige mais tráfego do que um teste de horizonte fixo, e é tráfego que a casa não tem. |
| **Personalização automática** | Personalizar exige distinguir pessoas, e hoje a casa não distingue dois visitantes. |
| **Knowledge graph de aprendizados** | Um grafo de aprendizados sem nenhum aprendizado medido é um índice vazio. |
| **IA geradora de hipóteses** | Hipótese é o insumo mais barato que existe aqui, e o que falta é tráfego para testá-las, não ideias. |

O argumento é da própria proposta externa: não se constrói Fórmula 1 sobre
estrada de barro. Hoje falta a estrada.

## 8. Uma correção explícita à proposta externa

A proposta pede uma célula `experimentos` transversal desde o início.

**O destino transversal está aceito. O começo não.**

A casa tem 18 células. Célula nova custa Dockerfile, banco e role Postgres
próprios, consumidor de eventos, entrada no deploy, suíte própria no
`ci-celula` e manutenção para sempre (Lei 2). Esse preço se paga quando existe
mais de um dono para o assunto, e hoje existe um: a página.

Por isso a primeira encarnação da experimentação nasce dentro do domínio da
página, e nasce com contrato de evento público desde o primeiro dia. É o
contrato que torna a mudança de casa barata depois: quando a fronteira
aparecer (Lei 7, um mesmo caminho em três briefs distintos é cheiro de
arquitetura), a célula `experimentos` nasce consumindo eventos que já existem,
e nada do que foi escrito precisa ser reescrito.

Quem propuser criar a célula antes disso está reabrindo uma decisão fechada, e
o ônus é dele: a proposta precisa mostrar o segundo dono do assunto.

## 9. O que esta decisão NÃO muda

- **A ambição continua inteira.** Esta não é a versão reduzida de nada
  (`DECISAO-filosofia-de-escopo.md`). A arquitetura de experimentação está
  aceita como destino; o que este documento fixa é a ORDEM, exatamente como a
  diretiva "o site vem antes da venda" fixou outra ordem sem cortar escopo.
- **A `metricas` não muda.** O livro de fatos recebe os quatro eventos novos
  como recebe qualquer outro, e nenhum PR da escada toca nela.
- **Contrato congelado continua congelado.** O PR 1 é aditivo, e caminho
  `contracts/` exige mandato escrito do mantenedor como sempre.

## 10. Estado

**Decidido em 19/09/2026.** Vale a partir de agora. A escada do §4 é a ordem
de execução; os gatilhos do §6 são a única porta de entrada dos itens
adiados; o §7 só reabre por decisão nova e escrita.
