# DECISÃO — a área do lançamento perpétuo mora em `/admin/perpetuo/`

> **Pedida pelo mantenedor em 02/09/2026**, na frase dele:
> *"no painel do admin crie uma parte assim `https://meshcraft.top/admin/perpetuo`
> onde iremos criar várias coisas sobre o lançamento perpétuo, teremos várias
> páginas, vários painéis, e etc"*.
>
> Este documento é **lei** para tudo que vier depois dentro dessa área. Ele se
> soma a `DECISAO-a-gestao-da-caixa-mora-no-admin.md` (a decisão de que tudo
> que é gestão mora em `/admin`) e a `DECISAO-celula-admin.md` (a porta).

---

## 1. O que foi decidido

Nasce uma área nova na administração: **`/admin/perpetuo/`**, reservada ao
assunto **lançamento perpétuo**. Ela começa com uma página (a planta da
máquina) e foi desenhada para ganhar irmãs: cada painel novo entra como
`perpetuo/<coisa>/`, e **nunca** como uma tela solta noutro canto do site.

O endereço é o que ele pediu, ao pé da letra. Ele responde em
`meshcraft.top/admin/perpetuo` (o `APPEND_SLASH` leva à barra final), e a rota
nasce fora do prefixo `painel/` pelo mesmo motivo do mapa e do menu: a rota
genérica `painel/<qualquer coisa>` engoliria qualquer irmã dela.

## 2. O que é um lançamento perpétuo, para quem for construir aqui

Um lançamento comum abre as matrículas por alguns dias e fecha. O perpétuo não
fecha: cada pessoa que chega começa o próprio caminho, no relógio dela. Quem
entrou hoje encontra o mesmo convite que alguém encontrou semana passada, na
mesma ordem, porque quem conduz é a máquina e não o calendário.

A máquina tem **seis peças**, na ordem em que uma pessoa as atravessa:

| # | Peça | A pergunta que ela responde |
|---|---|---|
| 1 | Atrair | Como alguém que nunca ouviu falar da escola chega até aqui? |
| 2 | Capturar o contato | O que a pessoa ganha em troca de deixar o contato dela? |
| 3 | Aquecer | O que chega até a pessoa depois, sem você precisar mandar? |
| 4 | Decidir a entrada | Quem pediu para entrar, e o que você respondeu? |
| 5 | Entregar | O que a pessoa encontra quando finalmente entra? |
| 6 | Medir | De cada cem que chegam, quantas passam para a etapa seguinte? |

Essa divisão é **conceito**, não estado do projeto, e é por isso que ela pode
morar em código sem envelhecer em silêncio: uma peça continua sendo o que é
mesmo quando a plataforma muda.

## 3. A regra dura desta área: ela não guarda cópia de nada

Cada peça da máquina lista as portas do site que já a servem hoje. **Só o
endereço mora no código.** O nome de cada porta, a explicação e o link clicável
saem de `painel/mapa-do-site.json`, que é a única fonte de endereços do projeto
e é conferida em todo PR por `ci/mapa_do_site.py`, nos dois sentidos.

É a lei anti-duplicação do `CLAUDE.md` aplicada, e ela vale para toda página que
esta área ganhar:

- **Endereço, nome de tela e explicação** vêm do mapa do site.
- **Contagem de gente** vem de quem tem o dado, pelo contrato congelado da
  célula dona (Lei 3), e nunca de uma contagem própria.
- **O que já está pronto e o que falta** se lê no livro de ocorrências,
  calculado, em `/admin/painel/`. Uma lista própria aqui seria superfície
  paralela de acompanhamento, e o `CLAUDE.md` a proíbe.

Endereço citado por uma peça que o mapa não conhece **não some**: vira um aviso
à vista na tela, e `services/admin/tests/test_perpetuo.py::test_toda_porta_existe_no_mapa_do_site`
reprova o PR antes disso chegar à tela do mantenedor. Link que devolve 404 é
pior que link nenhum: ele faz o dono concluir que o site quebrou.

## 4. O que esta primeira página NÃO faz, e por quê

Ela não mostra número nenhum. **O mapa da jornada do aluno
(`/admin/escola/jornada/`) já é a tela dos números de quem está na escola**, e
uma segunda contagem, montada aqui, divergiria dela no primeiro estado novo. A
peça "Medir" aponta para lá, e é assim que fica.

### 4.1 O painel de números do funil NÃO nasce aqui (medido em 04/09/2026)

Em 04/09/2026 o mantenedor escolheu "os números do funil" como o primeiro
painel desta área. **A medição do repositório mostrou que ele já existe**, e
por isso ele não foi construído aqui:

`/admin/placar/` (degrau 1 do `PLANO-PAINEL-DE-GESTAO.md`, entregue em
03/09/2026) mostra, ao vivo da célula `alunos`: pedidos de entrada e liberações
nos últimos 28 e 7 dias, quantas pessoas esperam, há quanto tempo, o tempo
típico de liberação, e a taxa da passagem. O cálculo mora em
`services/admin/apps/core/restricao.py`, e o `ETAPAS` de lá **declara, uma por
uma, as passagens que ainda não têm fonte e por quê** (cadastros, primeira
entrada, escrita no fórum).

Uma segunda tela de funil aqui seria a segunda leitura renderizada do mesmo
fato, num painel de gestão que outra frente está construindo por um plano
escrito. A área do perpétuo **aponta** para `/admin/placar/` na peça "Medir", e
é isso que ela faz com todo número: aponta, nunca recalcula.

**O que falta para o funil ficar inteiro não é tela: é fonte.** As três
passagens sem dado esperam a célula `metricas` (degraus 7 a 9 daquele plano), e
essa célula está parada por um passo do mantenedor no servidor, registrado em
`20260904-052`. Enquanto ele não acontece, nenhuma tela nova pode adiantar o
número: ela mostraria "ainda não sei" com desenho mais bonito.

## 5. Como uma página nova entra aqui

1. Rota `perpetuo/<coisa>/` em `services/admin/config/urls.py`, com `name=`.
2. View em `services/admin/apps/core/perpetuo.py` (ou um módulo vizinho, se
   crescer).
3. Entrada em `painel/mapa-do-site.json`, ou a muralha do cartógrafo reprova.
4. Uma faixa de abas nasce **quando houver a segunda página**, no molde de
   `admin/_caixa_abas.html` — que descobre sozinha onde a pessoa está, por
   `request.resolver_match.url_name`.
5. Guardas em `services/admin/tests/test_perpetuo.py`.

## 6. O que continua fora desta área

**Cobrança.** Por diretiva do mantenedor de 22/08/2026, nada de pagamento entra
em pauta enquanto ele não disser que o site vai vender. A área desenha a máquina
até a entrada do aluno e a entrega; o que acontece no caixa fica de fora, e não
por esquecimento.
