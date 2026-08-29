# LICOES — services/sugestoes

> Decisões e armadilhas específicas desta célula. Regra geral em `ARMADILHAS.md`
> (leia `armadilhas/INDICE.md` e abra só a entrada que casa com a sua tarefa).

## A tela de avisos passa a ler da caixa central (Fase 3/4 do sininho): a double fiel, o `id` que deixou de ser inteiro, e um cache que confundiu um guarda antigo

Fecha `docs/decisoes/DECISAO-fase-2-do-sininho.md` §3 (*"a tela de avisos da
Caixa passa a ler da caixa nova"*) e o item 1 do Lote C de
`docs/notificacoes/PLANO-MESTRE.md`. `sino()` e `ver_avisos()`
(`apps/core/avisos.py`) trocaram de fonte — `NotificacoesClient`
(`apps/core/clients.py`), não mais `Aviso.objects`. `avisar_os_interessados()`
continua escrevendo o `Aviso` local exatamente como antes: é rede de segurança
da transição, e aposentá-lo é Fase 6, despacho próprio.

**1. As duas telas do MESMO dado têm regra de falha OPOSTA, e a diferença é o
ponto do despacho, não um detalhe.** `docs/decisoes/DECISAO-fase-4-do-sininho.md`
Escolha 2: o sino (em toda página) fail ABERTA, cópia peça por peça do padrão
do `funil` (`NotificacoesClient.obter_resumo`); a tela `/avisos` fail VISÍVEL —
mensagem clara, nunca lista vazia disfarçada. A saída de desenho que faz as
duas convivEREM no MESMO cliente sem duas classes de exceção: **todo método do
`NotificacoesClient` devolve `None` em qualquer tropeço** (config ausente,
rede, HTTP≠200, JSON fora do contrato) — nunca levanta. `None` é "não sei"; `0`
ou `{"itens": []}` são respostas REAIS. Quem chama decide o que `None`
significa para a TELA dele: `sino()` traduz como "sem número" (`or 0`);
`ver_avisos()` traduz como "mostra a frase de falha". A única exceção a "sempre
`None`" é `marcar_uma_como_lida`, que precisa de um TERCEIRO estado (`False` =
a notificacoes respondeu 404 de verdade, não "não sei") para preservar
404-nunca-403 no aviso de outra pessoa — ver o item 3.

**2. O `id` de um aviso deixou de ser o pk local, e isso muda o conversor da
URL, não só o código.** `GET /avisos` devolve um `id` OPACO (`type: string` no
contrato — nunca prometido numérico). `path("avisos/<int:aviso_id>/lido", …)`
viraria uma mentira estrutural: `<str:aviso_id>` é o conversor certo. A troca
é retrocompatível por acidente feliz — `reverse(..., args=[7])` com o
conversor `str` ainda produz `/avisos/7/lido` (o converter faz `str(valor)`),
então nenhum teste que já chamava `reverse` com um inteiro precisou mudar.

**3. `marcar_uma_como_lida` devolve `bool | None`, e o terceiro estado
(`False`) existe só por causa de UM invariante antigo que quase se perdeu na
migração.** A tela sempre respondeu 404 (nunca 403) ao chute de um aviso
alheio — confirmar "existe, mas não é seu" vazaria a existência a quem só
adivinhou um número. Se o cliente colapsasse 404 no mesmo `None` genérico de
"rede caiu", a view não teria como diferenciar os dois casos, e o invariante
de privacidade silenciosamente viraria "falha visível também no botão de
marcar como lido" — o que É aceitável para "não sei", mas não é a mesma coisa
que confirmar-ou-não a existência. `False` = definitivo (notificacoes
respondeu 404); `None` = não sei (config, rede, 5xx, JSON fora do contrato).
Só o primeiro vira `Http404` na view.

**4. `vinculo` entra na carta pelo CALL SITE (`moderacao.py`), não por
`avisos.py` reimportar `eventos.py`.** A tentação óbvia era fazer
`avisar_os_interessados()` chamar `emitir_cartas_de_notificacao()` direto —
mas quem já chama as duas, em sequência, com o resultado da primeira
alimentando a segunda, é `registrar_mudanca_de_status()`
(`apps/core/moderacao.py`). Cada `Aviso` que `avisar_os_interessados()`
acabou de gravar já carrega `.vinculo`; `moderacao.py` só precisou cruzá-lo
com o mapa `id local → id da plataforma` que já calculava (`ids_de_plataforma`)
para montar `{id da plataforma: vinculo}` e passar como novo parâmetro
OPCIONAL de `emitir_cartas_de_notificacao`. Aditivo de propósito — `vinculos`
tem default `None`, e `parametros` só ganha a chave quando o destinatário
está no mapa — então `tests/test_volume_das_cartas.py`, que chama a função
direto sem `vinculos`, não precisou de UMA linha alterada. Regra que
generaliza: quando um campo novo de contrato nasce OPCIONAL, o jeito certo de
adicioná-lo a uma função já testada é um parâmetro com default que preserva o
comportamento de quem não sabe que ele existe — nunca uma mudança de
assinatura obrigatória que exige atualizar cada chamador.

**5. A double de teste ESPELHA o `Aviso` local em vez de reconstruir um mundo
próprio — e essa decisão sozinha evitou reescrever ~10 arquivos de teste
existentes.** A primeira ideia (errada) foi: já que `/avisos` agora lê de um
serviço de fora, todo teste que hoje monta um `Aviso` pelo ORM e confere o
HTML precisaria ganhar uma segunda montagem, desta vez mockando a resposta
HTTP à mão. Medido: são MAIS de trinta guardas espalhados em
`test_inv_aviso_e_so_do_dono.py`, `test_inv_aviso_nasce_com_o_status.py`,
`test_o_rosto.py`, `test_avisos_script_name.py`. A saída que funcionou: os
quatro handlers novos de `tests/conftest.py::Rede` (`_notificacoes_resumo`,
`_notificacoes_avisos`, `_notificacoes_marcar_lida(s)`) leem e ESCREVEM direto
na tabela `Aviso` local — é o comportamento OBSERVÁVEL que a caixa central
teria depois de a carta chegar e ser lida de volta, sem reimplementar o relay
inteiro dentro do dublê (a carta em si já tem guarda próprio,
`tests/test_volume_das_cartas.py` e
`tests/test_inv_carta_endereca_pelo_id_da_plataforma.py`). Resultado medido: dos 366 testes que já existiam antes deste despacho,
**364 passaram sem tocar UMA linha** — só dois precisaram de um ajuste
pequeno, e nenhum dos dois por estarem ERRADOS (um ganhou uma rota nova na
lista que já percorria, o outro é o item 6 logo abaixo).
O `id` opaco da double é `str(aviso.pk)`: uma implementação válida do
contrato (que só promete "opaco", nunca "não numérico"), e a que deixa
`aviso.id` de fixtures antigas funcionar sem tradução.

**6. O cache do sino (`_CACHE_DE_RESUMO`, TTL 30s) é uma feature real — e
confundiu de verdade um guarda de custo que não tinha nada a ver com ele.**
`tests/test_volume_dos_avisos.py::test_ler_a_pagina_de_avisos_nao_paga_consulta_pelo_vinculo`
abre `/avisos` duas vezes na MESMA sessão de teste para comparar consultas com
1 e com 11 avisos — e toda página desta célula também renderiza o sino
(context processor em toda página). Sem limpar o cache entre as duas
medições, a SEGUNDA visita reaproveitava o `/resumo` da primeira e pagava DUAS
consultas a menos só por isso — o teste comparou 13 com 11 e acusou "cresceu",
quando na verdade tinha DIMINUÍDO por um motivo alheio ao que ele mede. A
cura: `limpar_cache_de_resumo()` (nova função pública de `avisos.py`, a MESMA
receita de `apps/core/sessao.py::limpar_caches` para a `armadilhas/026`) antes
de cada medição naquele teste — nunca desligar o cache, que é comportamento de
produção correto. **A lição que generaliza: qualquer cache novo que atravessa
uma página já coberta por um guarda de CONTAGEM DE CONSULTAS precisa de um
jeito de ser zerado por fora — e o teste que mede "duas visitas seguidas"
precisa saber que ele existe**, mesmo sendo de um assunto (o sino) que não é
o que aquele teste está medindo (o vínculo).

**7. `test_a_jornada_cobre_TODAS_as_rotas_de_participacao`
(`test_inv_avaliacao_interna_fora_do_alcance.py`) é o guarda que pegou a rota
nova (`marcar_todos_avisos_lidos`, Escolha 3 de
`DECISAO-fase-4-do-sininho.md`) na hora — e é exatamente o comportamento que
ele existe para ter.** A lista de rotas é derivada do urlconf
(`exige_sessao` e não `exige_staff`), então a rota nova entrou sozinha na
exigência; a jornada simulada é que precisou ganhar uma chamada a mais. Sem
este guarda, uma rota de participação nova nasceria fora de TODOS os testes
que percorrem "tudo que o aluno alcança" (inclusive o guarda de privacidade da
`AvaliacaoInterna`) sem ninguém notar.

**O que ficou de fora, e é decisão e não esquecimento:** paginação de verdade
na tela (`ver_avisos()` segue `proximo_cursor` em loop, até 50 páginas, mas
não há "carregar mais" na UI — a Caixa nunca teve isso, e ninguém pediu
agora); "silenciar assunto" (Escolha 3, fora até existir um segundo assunto
de aviso); e qualquer coisa em `services/notificacoes/` ou
`services/funil/` — 1 PR = 1 célula, Lei 2 e Lei 3.

## Reemitir os avisos existentes (Fase 3, segunda metade): a migration e as três decisões que ela carrega

Fecha o "FALTA A SEGUNDA METADE DESTA FASE" que o
`docs/notificacoes/PLANO-MESTRE.md` §6 deixou escrito quando a célula
`notificacoes` nasceu (26/08/2026, PRs #247/#248/#252): os `Aviso` que já
existiam nesta célula ANTES daquele dia nunca tinham passado pelo fio como
`notificacao.devida.v1` — a caixa central não tinha cópia deles. O mandato é
`docs/decisoes/DECISAO-fase-2-do-sininho.md` §3: *"os avisos que já existem
mudam de casa junto"*, pelo fio, sem ninguém ler o banco alheio (Lei 2).

**1. MIGRATION, não management command — e o motivo é o `Dockerfile`, não
preferência.** `services/sugestoes/Dockerfile` roda
`python manage.py migrate --noinput` no boot do container, ANTES do servidor
subir. Uma migration corre automaticamente em TODO deploy, exatamente uma vez
(Django registra em `django_migrations`), sem exigir SSH nem passo manual do
mantenedor na VPS — o agente não tem acesso SSH (Lei 5), e todo passo manual
é atrito e risco a mais. Um management command exigiria alguém rodar
`docker exec` na VPS para uma operação que só precisa acontecer uma vez.
Verificado com o executor de VERDADE (não só chamando a função do teste): um
banco descartável, migrado até `0007`, com dois `Aviso` semeados (um com
`id_da_plataforma` no destinatário, outro sem) — `python manage.py migrate
sugestoes 0008` publicou exatamente 1 carta e imprimiu o 1 que ficou de fora;
`migrate sugestoes 0007` (o `noop` de volta) não apagou a carta; `migrate
sugestoes 0008` de novo publicou **0** cartas novas. É o cenário de rollback
+ reapply que a idempotência abaixo existe para cobrir, provado pelo caminho
real que a VPS usa, não só pela chamada direta da função nos testes.

**2. `event_id` determinístico é o que torna a migration segura de rodar de
novo — e o payload é montado À MÃO, nunca importando `emitir_cartas_de_notificacao()`
de `eventos.py`.** `event_id = uuid.uuid5(NAMESPACE_FIXO,
f"aviso-backfill-{aviso.pk}")`, nunca `uuid4()`: antes de escrever, a
migration confere quais desses ids já existem em `OutboxEvent` e pula
exatamente esses. Importar a função "de verdade" pouparia duplicação de forma
hoje e quebraria uma garantia que migrations existem para dar: continuar
válidas mesmo depois que o código vivo mudar de assinatura. A duplicação
entre a migration e `eventos.py` é consciente — é o preço de a migration ser
uma fotografia congelada. Não ganhou guarda de paridade comparando os dois
formatos (o despacho permitia deixar de fora sob aperto de orçamento, e
apertou): quem mudar a forma do payload de `notificacao.devida` em
`eventos.py` precisa lembrar, por revisão manual, que esta migration não
acompanha sozinha.

**3. `ator_id` nasce `None` SEMPRE, e não é aproximação — é o que o dado
permite.** O `Aviso` desta célula é a "cópia do aluno" (ver a docstring do
model): ele não guarda quem moderou, de propósito, desde o EVO-21. Cruzar com
`HistoricoStatus` por (sugestão, status_anterior, status_novo, janela de
tempo) para ADIVINHAR o ator seria frágil — uma sugestão pode repetir a
mesma transição mais de uma vez — e o contrato permite `ator_id: null`
exatamente para isto: "fatos de máquina" sem gente atrás. Pelo mesmo motivo,
`origem_event_id` (obrigatório no contrato) é sintético e **PRÓPRIO de cada
`Aviso`** — diferente do caminho ao vivo, onde as N cartas de uma mesma
mudança de status compartilham o `origem_event_id` do fato que as originou
(`test_a_carta_aponta_para_o_fato_que_a_gerou`), as cartas retroativas de um
mesmo backfill NÃO compartilham nada entre si: não há como saber, a partir só
do `Aviso`, quais linhas vieram da mesma chamada de
`avisar_os_interessados()`. É um marcador de backfill, documentado como tal —
um consumidor que usa o campo para RASTREAR a origem não é afetado; um que
tentasse AGRUPAR por ele (nenhum existe hoje) leria "cada carta é um evento
isolado", o que é falso para o passado mas inofensivo, porque nada consome
esse agrupamento ainda.

**4. `occurred_at` quase saiu errado, e a pegadinha virou `armadilhas/139`
porque não é só desta célula.** A missão pedia para preservar o `criado_em`
do `Aviso` no `occurred_at` da carta — mas os dois campos são
`auto_now_add=True`, e `bulk_create` NÃO os deixa incólumes só porque pula
`Model.save()` e os sinais (`armadilhas/116`): o compilador SQL do INSERT
chama `field.pre_save()` para cada objeto de qualquer forma — é dali que
`auto_now_add` funciona no caminho comum —, e isso sobrescreve em memória
qualquer valor atribuído no construtor. A saída: `bulk_create()` primeiro
(aceitando que o campo nasce com "agora"), guardar os valores reais numa
lista PARALELA, e depois `bulk_update(objetos, ["occurred_at"])` — que passa
por `QuerySet.update()`, o único caminho comum que nunca chama `pre_save()`.
`tests/test_backfill_cartas_dos_avisos_existentes.py::test_occurred_at_preserva_o_criado_em_do_aviso_e_nao_a_hora_do_backfill`
é o guarda: empurra um `Aviso` 30 dias para trás (pela mesma técnica —
`.update()` depois do `create()`) e prova que a carta herda a data certa, não
"agora".

**5. Volume: `TAMANHO_DO_LOTE = 500`, e não um `bulk_create` sem teto.** A
troca de destinatário e o cálculo de quem já foi publicado rodam para a lista
inteira em consultas fixas (um `IN (...)` só, nunca um por `Aviso`); a
escrita é fatiada para não segurar uma transação gigante se a tabela crescer
para milhares de linhas. `test_o_backfill_custa_o_mesmo_com_poucos_e_com_muitos_avisos`
mede 2 e 202 candidatos (o segundo número é cumulativo — a função não é
parametrizada por sugestão, processa a tabela inteira a cada chamada) e exige
o mesmo total de consultas, no molde de `test_volume_das_cartas.py`.

**O que ficou de fora, e é dívida documentada, não esquecimento:** quando a
Fase 5 (o sininho fora da Caixa) for ao ar, o rollout dela precisa marcar
como LIDAS — dentro do banco da `notificacoes`, sem esta célula tocar
naquele banco — todas as notificações criadas antes do lançamento, senão todo
mundo vê uma enchente de "não lidas" de coisas já lidas há semanas na Caixa.
Está anotado no `PLANO-MESTRE.md` §6, dentro da descrição da Fase 5, para não
virar palpite herdado por quem for construir aquela fase
(`armadilhas/107` documenta o mesmo padrão de "escrever a dívida onde ela vai
ser lida", para outro caso).

## A V1.2 ("Em alta" e "Meu impacto"): o que estas duas peças ensinaram

Fecha as duas linhas que a `ESPECIFICACAO-CELULA.md` §10 deixou escritas como
V1.2. Nenhuma tabela nasceu, nenhuma rota nasceu: as duas são recortes novos de
dados que existem desde o EVO-11, servidos dentro do quadro. Oito coisas:

**1. A fórmula do "em alta" pesa o VOTO, e não a idade da ideia — e a diferença
decide o que a aba significa.** A fórmula clássica de trending (votos ÷ idade)
só sabe destacar ideia NOVA: uma ideia de seis meses que a turma inteira
redescobre nesta semana continuaria no fundo, exatamente quando está em alta de
verdade. O que ficou, numa frase: **o calor é a soma dos votos com peso de
recência — voto dos últimos 7 dias vale 3, do último mês vale 1, mais velho que
um mês não conta.** Degraus inteiros e não `exp()`, porque aritmética de inteiro
sai igual no Postgres e no Python, ordena sem `float` e **cabe na frase**; zero
depois de 30 dias e não um piso pequeno, porque um piso faria o calor virar o
total de votos com outro nome — e a aba do lado já é essa.

**2. Um `Sum` ao lado de dois `Count(distinct=True)` sai multiplicado, e o
`distinct` do vizinho é o que faz ninguém desconfiar.** A grade já juntava
`votos` E `comentarios`: com dois `JOIN`, uma ideia com 2 votos e 3 comentários
vira 6 linhas antes do `GROUP BY`. Os `Count(distinct=True)` sobrevivem — e é
essa sobrevivência que engana, porque `Sum(distinct=True)` soma valores
distintos, que é outra pergunta. Não existe versão do `Sum` que sobreviva à
junção dupla: a saída é a subconsulta correlacionada (`calor_de_recencia`), que
continua custando **uma** consulta. Medido: com o `Sum` de volta na junção,
**1 teste vermelho de 8** no arquivo — os outros sete tinham fixtures sem
comentário nenhum e aprovariam a versão errada inteira. Virou `armadilhas/121`,
porque não é desta casa só.

**3. `Coalesce(..., 0)` não é zelo — sem ele a aba abre ao contrário.** A
subconsulta não produz linha para quem não tem voto, e no Postgres
`ORDER BY … DESC` põe `NULL` **na frente** de qualquer número: "Em alta" abriria
mostrando exatamente as ideias em que ninguém votou. Há guarda
(`test_ideia_sem_voto_nenhum_fica_atras_de_quem_tem_calor`).

**4. `agora` virou PARÂMETRO, e é isso que torna o ranking falsificável.** Um
`timezone.now()` dentro da função obrigaria todo guarda a medir contra o relógio
da máquina — teste que diz uma coisa na segunda e outra no domingo, e que
apodrece sozinho. A view lê `timezone.now()` na borda e desce o instante; o
guarda passa um `datetime` escrito à mão e carimba os votos à mão. **E
`Voto.criado_em` é `auto_now_add`: `criado_em=` no `create()`/`bulk_create()` é
ignorado em silêncio** — a data só se escreve por `update()` DEPOIS do fato,
senão todo voto nasce "de hoje" e o guarda fica verde sem nunca ter medido um
degrau.

**5. "Em alta" é a PRIMEIRA aba e não a PADRÃO — e as duas coisas foram
decididas.** No protótipo ela é a aba acesa. Aqui o padrão continua
`mais-votadas`, porque a §10 crava o MVP em *"ranking por total de votos"*, e
trocar em silêncio o que todo aluno vê ao chegar seria reescrever spec de
plataforma dentro de um despacho de célula — é a mesma linha do item 2 do bloco
do EVO-40 abaixo. O guarda mede as duas juntas
(`test_as_abas_sao_tres_e_a_acesa_continua_sendo_mais_votadas`): a ordem da fila
E qual delas está com `class="ativo"`. Mudar isso é decisão do mantenedor, e de
uma linha.

**6. "Meu impacto" NÃO é a avaliação interna, e a coincidência da palavra é do
protótipo.** `impacto_educacional`/`impacto_comercial`/`esforco_tecnico`/`notas`/
`decisao_produto` são o que a EQUIPE achou, invisíveis ao aluno por desenho em
três degraus (spec §8). O painel novo é o que a PESSOA fez. Provado por mutação:
acrescentar `"avaliacao__decisao_produto"` ao `.values(...)` do painel e imprimi-
lo no template deixa **dois** guardas vermelhos — o degrau 1 do antigo (o SQL da
jornada tocou `sugestoes_avaliacaointerna`) e o novo
`test_nenhuma_nota_interna_da_equipe_chega_ao_painel`. **O degrau 2 do guarda
antigo NÃO pegou**, e o motivo vale guardar: a fixture `avaliacao` dele semeia a
nota numa sugestão de OUTRA identidade (a fixture `sugestao`, autoria de
`aluno`), e o painel só lista as ideias de quem está olhando. Guarda de vazamento
por corpo renderizado só morde se a marca estiver num dado que a página em questão
**tem motivo de mostrar**.

**7. O painel obedece ao filtro de categoria — e quem decidiu foi um guarda de
quatro despachos atrás, de novo.** A pergunta ("os números são do quadro inteiro
ou do recorte?") tinha resposta boa dos dois lados. Tirar o filtro deixa
`test_o_quadro_filtra_por_categoria` (EVO-12b) **vermelho**, exatamente como já
tinha acontecido com a faixa no EVO-31: ele afirma sobre o CORPO da página, e a
lista "as suas ideias" devolvia no rodapé os títulos que a pessoa acabou de tirar
da grade. Como os números passaram a ser do recorte, o painel **diz em qual
recorte eles estão** — sem essa linha, "1 ideia" pareceria desmentir as 2 que a
pessoa escreveu.

**8. `Q(autor=eu) | Q(votos__autor=eu)` precisa de `.distinct()`, e o caso não é
exótico: é quem vota na própria ideia.** Ela casa nos dois lados do `Q` e sairia
contada duas vezes, premiando quem vota em si mesmo. `.order_by()` antes do
`.distinct()` pela `armadilhas/115` — `Sugestao` não tem `Meta.ordering` hoje, e
no dia em que tiver o `DISTINCT` passaria a ser pelo par sem ninguém notar.

**O que ficou de fora, e é decisão e não esquecimento:** "Meu impacto" não tem
rota nem página própria — é seção com `id` dentro do quadro, alcançada por âncora
pelo botão do trilho, como a faixa do EVO-31. Rota própria seria uma segunda
porta a proteger e a acrescentar às **três** varreduras de urlconf desta célula,
para mostrar um recorte do que o quadro já tem em mãos. E, pelo mesmo motivo do
roadmap, **o botão dele não se pinta de `ativo`**: âncora não muda
`request.resolver_match`, e pintá-lo por adivinhação faria o trilho mentir.

## O id que atravessa (Fase 1 das notificações): guardar o que já passava na mão

`docs/notificacoes/PLANO-MESTRE.md` §2 mediu o nó: `identidade` e `sugestoes`
cunham **dois ids opacos diferentes** para a mesma pessoa, e o único elo entre
eles é o e-mail, que não circula. A porta desta célula recebia o elo que falta em
toda entrada (`SessionFull.id`, contrato congelado) e o jogava fora em
`_sessao_central`. Este despacho parou de jogar fora. Sete coisas que custaram
alguma coisa, ou que decidem o comportamento de quem mexer nisto depois:

**1. O e-mail continua sendo a CHAVE; o id da plataforma é dado a mais.** Trocar
`get_or_create(email=…)` por `get_or_create(id_da_plataforma=…)` parece a
evolução natural e é a regressão: a linha antiga (que não tem id nenhum) nunca
seria encontrada, e a pessoa perderia a autoria de tudo que escreveu antes de o
login mudar de casa. Há guarda nominal para isso
(`test_o_casamento_por_email_continua_sendo_a_chave`), porque a tentação é real e
o sintoma só apareceria como "sumiram as minhas sugestões".

**2. `null=True`, e não `default=""` — a escolha decide se a migration SOBE.** No
Postgres o índice único trata cada `NULL` como distinto; `''` colide com `''`.
Com string vazia o próprio `AddField` estouraria na segunda linha antiga da
tabela. Medido por mutação (model **e** migration juntos, estado coerente): a
suíte foi a **20 vermelhos**, quase todos de fixtures que criam duas pessoas.
Virou `armadilhas/120`, porque não é desta casa só.

**3. O `CheckConstraint` contra `''` não é zelo — é fechar o SEGUNDO jeito de não
saber.** Com `null=True` sozinho, a coluna teria duas formas de vazio, e o dia em
que alguém gravasse `""` por descuido o `__isnull=True` do relatório passaria a
contar errado, em silêncio. Uma forma só de "não sei" é o que faz duas consultas
escritas por pessoas diferentes concordarem.

**4. A colisão de unicidade tem DOIS caminhos, e o teste parametrizado achou o
que faltava.** O primeiro `try/except` que escrevi cobria só a **reentrada** (o
`UPDATE` de `_casar_com_a_plataforma`); a **cunhagem** — o `INSERT` do
`get_or_create` com o id nos `defaults` — ficou de fora e o guarda reprovou na
hora, com `duplicate key value violates unique constraint`. Não é caso exótico:
alguém que troque de e-mail na `identidade` vira uma segunda linha aqui com o
mesmo id da plataforma. As duas metades engolem, cada uma com **savepoint
próprio** (`with transaction.atomic()`), senão o `IntegrityError` envenena a
transação da requisição inteira e a página cai em 500 **depois** de a pessoa já
ter sido autorizada.

**5. Ausência de id NÃO pode virar recusa de acesso.** O contrato declara
`SessionFull.id` opcional e nulável; quem autoriza aqui continua sendo e-mail +
(staff | matrícula). Transformar a falta de um dado que a Caixa passou a coletar
hoje em porta fechada seria punir quem não tem como resolver o problema — e o
guarda cobre as **três** formas de "não veio" (ausente, `null`, só espaços), que
a borda normaliza para um `None` só.

**6. Um lugar só cunha `Identidade`, e agora isso tem varredura de AST.** O
invariante "toda identidade cunhada guarda o id" é completo só enquanto existir
**um** caminho de escrita: um segundo, escrito daqui a seis meses por quem nunca
leu isto, nasceria sem o campo e o buraco apareceria meses depois, do outro lado
da plataforma, como notificação que não chega. É a mesma forma do degrau 3 do
guarda da `AvaliacaoInterna` (AST, não `grep`, para que citar o nome num
comentário não conte).

**7. A migration não preenche NADA, e isso é o desenho.** Não há de onde derivar
o id da plataforma de uma linha antiga sem pedir à `identidade` a lista de gente
dela — que é a Lei 3. As linhas nascem `NULL` e casam **na reentrada** de cada
pessoa. Por isso o número não zera no dia do deploy, e por isso existe
`manage.py relatorio_id_da_plataforma`: um número que não desce em semanas é o
sintoma de que a frente 2 parou de funcionar. É o antídoto que a §9 do plano
exige nominalmente, e é somente-leitura (dois `COUNT`).

**O que NÃO entrou, e é do elo seguinte:** o `ator_id` no envelope dos eventos é
a **Fase 2**, e é Rito de Contrato (RITOS §3) com o mantenedor presente — não
cabe em despacho de célula, e nada aqui o improvisou.

## O leque de avisos (EVO-42): o que muda quando o destinatário deixa de ser um

Fecha o "fica para depois" que o EVO-21 deixou escrito no topo do `avisos.py`, e
a previsão de lá estava certa: *"cabe sem mudar forma nenhuma, são mais linhas
com outro `destinatario`"*. Mudou uma coisa que aquele despacho não podia prever
porque não havia plateia: **o custo passou a depender de gente.**

**1. A igualdade não foi afrouxada para caber o leque — ela mudou de forma e o
guarda mudou junto.** *"Uma linha de `HistoricoStatus` ⇒ um `Aviso`"* virou *"⇒
um `Aviso` por interessado DISTINTO"*. Tudo o que era exigido do aviso único
continua exigido do leque inteiro: mesma transação, mesmo rollback, mesma recusa
fora do `atomic`. A tentação de baixar a asserção para `>= 1` existe e é o erro:
um guarda que aceita "pelo menos um" não distingue seis avisos de um.

**2. `bulk_create` não chama `Model.save()` — e o guarda que mirava o `save()`
ficou apontando para o vazio.** `test_se_o_AVISO_nao_puder_nascer_o_status_nao_muda`
monkeypatchava `Aviso.save`, que era o ponto exato onde o `create()` tocava o
banco. Com a escrita em lote, esse ponto deixou de existir — e o teste teria
ficado **verde sem nunca disparar**, que é a forma mais discreta de um portão ser
desligado. Aqui ele reprovou alto (`DID NOT RAISE`), porque esperava a exceção;
num guarda escrito ao contrário, não reprovaria. **Regra: quando o caminho de
escrita muda, o alvo do monkeypatch é parte do que muda.** O alvo novo é
`monkeypatch.setattr(Aviso.objects, "bulk_create", …)`.

**3. `.distinct()` num model com `Meta.ordering` não é distinto pelo que você
pediu.** `Comentario` ordena por `criado_em`, e o Django acrescenta a coluna de
ordenação ao `SELECT DISTINCT`: o SQL vira `SELECT DISTINCT autor_id, criado_em`,
distinto **por par**, ou seja uma linha por comentário. O resultado final saía
certo (o `dict` do fan-out deduplica), então nada reprovava — a única coisa que
denunciou foi olhar o SQL cru que o teste de volume imprime. `.order_by()` vazio
antes do `.distinct()` devolve ao `DISTINCT` o sentido que o nome promete. Vale
para qualquer célula; `Voto` não sofre disso porque não tem `ordering`.

**4. O guarda de volume não crava um número: compara dois medidos.** `== 3`
transformaria qualquer `select_related` novo em vermelho falso, e a pergunta
nunca foi "quantas consultas" — foi *"o número depende da plateia?"*. Mede-se com
2 e com 20 e exige-se igualdade; a mensagem de falha carrega os dois números e o
SQL. O teto absoluto existe só para o fan-out isolado (três idas ao banco), e
`SAVEPOINT`/`RELEASE` saem dessa conta porque são artefato do `django_db` da
suíte, não do desenho.

**5. Dois degraus de volume, falsificados separadamente — é a lição do EVO-40
paga adiantado.** O degrau 1 mede `avisar_os_interessados()`; o degrau 2 mede o
POST inteiro da moderação. Só o degrau 1 mentiria sobre um laço escrito na
**view**, por fora da função: a função continuaria com as três consultas dela.
Medido com um `create()` por pessoa: 9 × 45 no degrau 1, 15 × 51 no degrau 2.

**6. O vínculo é COLUNA, e a alternativa foi medida, não descartada por gosto.**
A tela precisa dizer "sua ideia" × "ideia em que você votou/comentou". Derivar na
leitura parece mais limpo (zero duplicação) e perde por duas coisas: (a) é
espelho de **estado mutável** — quem desvota amanhã vê o recado de ontem mudar de
explicação, e o `Aviso` é snapshot desde o EVO-21, como `status_novo` e `nota`;
(b) custa leitura por página. As duas estão medidas em teste:
`test_o_vinculo_sobrevive_ao_desvoto` e
`test_ler_a_pagina_de_avisos_nao_paga_consulta_pelo_vinculo`. A precedência de
quem acumula papéis (autor > comentário > voto) tem guarda próprio, senão a
etiqueta passaria a depender da ordem em que o fan-out leu as tabelas.

**7. Fixture de volume pelo ORM, fixture de verdade pela jornada — e as duas.**
A `plateia` escreve `Voto`/`Comentario` por `bulk_create`: vinte logins dublados
não acrescentariam nada à medição de consultas e custariam segundos de suíte. Mas
ela sozinha continuaria verde no dia em que o endpoint de votar parasse de gravar
a linha que o fan-out lê — por isso existe
`test_a_jornada_de_verdade_bota_quem_votou_e_quem_comentou_no_leque`, com POST em
`votar` e em `comentarios`. Nenhuma das duas fecha a escada sozinha.

**8. O que ficou de fora, e é rito e não decisão:** o sininho **ao lado do nome**,
visível em qualquer página do site. Ele exige que o `funil` pergunte à
`sugestoes` quantos avisos a pessoa tem — operação nova num contrato
**congelado**, ou seja Rito de Contrato (RITOS §3) com o mantenedor presente, e
nunca dentro de um lote. Está escrito na §2 da `DECISAO-EVO-40`, e este despacho
não o improvisou de propósito.

## A trava do ChangeSpec (EVO-40): o degrau que eu quase deixei sem dente

Fecha a divergência que o EVO-13 registrou logo abaixo ("A spec §8 pede um
ChangeSpec que esta célula não tem"). A pergunta que aquele despacho deixou
aberta — *onde o ChangeSpec mora?* — foi respondida: **tabela nesta célula**
(`ChangeSpecAprovado`), e não um `changespec_id` no `HistoricoStatus`. O motivo
decide sozinho: um ChangeSpec pode referenciar VÁRIAS sugestões (formato §2), e
a coluna no histórico só saberia falar de uma; e a pergunta que a trava faz
("existe corredor para ESTA ideia?") não é sobre a linha do tempo, é sobre a
ideia.

**1. O degrau 1 não tinha dente, e eu só descobri porque falsifiquei os três
separadamente.** Apagar o ponto de estrangulamento inteiro
(`registrar_mudanca_de_status`) deixava a suíte **verde**: o `save()` do model
recusava dentro da transação, a view convertia a exceção na mesma página de
400, e a frase que ensina o caminho continuava aparecendo — porque a página de
moderação também a mostra no aviso preventivo. Três coisas cobrindo umas às
outras, e nenhum guarda capaz de dizer se a primeira existia.

O que o degrau 1 acrescenta, e que só se vê no SQL, é **recusar antes do
`SELECT … FOR UPDATE`**. `test_a_recusa_nem_chega_a_travar_a_linha` mede isso
com `CaptureQueriesContext`, e é ele que fica vermelho quando o degrau some. A
regra que generaliza: **falsifique cada degrau da escada isoladamente**. Uma
escada testada só por fora prova o andar de cima e mente sobre os de baixo — é
a RETROSPECTIVA §1 (garantia sem mecanismo) na sua forma mais discreta, porque
aqui o mecanismo existe: o que não existia era a prova de que ele fazia
diferença.

**2. A trava vale para a transição NOMINAL, e a fronteira está medida.** A §8
diz `planejado → em_desenvolvimento`. `em_analise → em_desenvolvimento`
continua passando — e não por descuido: fechar toda entrada em
`em_desenvolvimento` deixaria VERMELHO o `test_inv_historico_append_only.py`,
que percorre a moderação exatamente por essa transição desde o EVO-13. Guarda
de célula não reescreve spec de plataforma dentro de um despacho. Fica
`test_a_fronteira_da_lei_e_a_transicao_NOMINAL`, para que a brecha seja uma
decisão visível em vez de um esquecimento.

**3. `SUGESTOES_APROVADORES` é um papel NOVO, e não o crachá da equipe.**
Decisão do mantenedor em 25/08/2026, na forma mais travada: só ele autoriza.
Moderar (`SUGESTOES_STAFF_EMAILS`) e autorizar desenvolvimento são dois
portões empilhados, e o segundo é fail-closed — **lista ausente ou vazia ⇒
ninguém aprova ⇒ nada entra em desenvolvimento**. A suíte inteira roda com a
variável APAGADA (`conftest.py::ambiente`), que é o único jeito de o guarda de
fail-closed poder reprovar algum dia.

**4. Portão novo empilhado colide com as três varreduras de urlconf, e a
colisão é o desenho funcionando.** A rota nova carrega `exige_staff`, então
`test_inv_so_staff_modera.py::test_a_equipe_alcanca_as_mesmas_rotas` passou a
exigir que a EQUIPE não leve 403 numa rota que recusa quem não é aprovador. A
saída **não** foi tirar a rota da varredura (seria esconder rota do guarda
escrevendo um nome numa lista, o erro que a própria célula já não comete com
`MONTAGENS_DE_MAQUINA`): foi pôr a pessoa daquele teste também na lista de
aprovadores, com o motivo escrito ali — aquele guarda mede o PRIMEIRO portão, e
o segundo tem guarda dedicado. Quem for acrescentar rota de equipe com portão
extra vai passar por aqui de novo.

**5. Reusar o append-only custou uma linha e evitou uma cópia.** Os degraus 1 e
2 do `HistoricoStatus` (`save()` + `AppendOnlyQuerySet`) viraram
`RegistroAppendOnly`, uma base abstrata — e a mensagem do queryset passou a sair
de `self.model.__name__`, senão a tabela nova acusaria a antiga. O degrau 3
**não** cabe na classe: cada migração cria o trigger da sua tabela, porque só o
banco impõe o que o `CASCADE` do collector atropela (`armadilhas/079`).

**6. `BEFORE UPDATE OF status` — o trigger nem é chamado quando a coluna não
está na lista do `UPDATE`.** É o que faz a trava no banco custar zero para todo
o resto da célula, e o que a mantém compatível com o
`save(update_fields=["status"])` que a moderação já usava desde o EVO-13.

**7. O que ficou de fora, e é do elo seguinte:** o `SUBSTITUI` do formato §4
não virou coluna. Uma v2 é uma LINHA nova, com o `change_id` terminando em
`-v2`; a corrente entre versões mora no documento, que é a autoridade. Guardar
a corrente aqui seria a célula modelando o que ela decidiu não ler.

## O rosto (EVO-30): as seis decisões de desenho

O comportamento inteiro já existia (EVO-12b/13/20/21) e a Caixa estava **no ar sem
tela**. Este despacho não escreveu regra de negócio nova: costurou tela sobre
comportamento provado, seguindo `docs/caixa-de-sugestoes/prototipo-v2.html`.

**1. `{% url 'estatico' %}` e nunca `{% static %}` — vale para toda célula sob
prefixo.** A lição virou `armadilhas/102` porque não é desta casa só: as duas tags
leem prefixos diferentes, e sob `SCRIPT_NAME` o `{% static %}` gera
`/static/sugestoes/caixa.css` — endereço que em `meshcraft.top` pertence ao `funil`,
não à Caixa. Pagar a `armadilhas/083` (a rota `^static/…` no urlconf) é **necessário
e não suficiente**: a rota existe, responde 200, e o navegador nunca chega nela.
Trocar a tag deixa 7 testes vermelhos aqui; tirar a rota, muitos mais.

**2. O protótipo perdeu as fontes remotas e o JavaScript, de propósito.** O
`prototipo-v2.html` carrega três famílias do Google Fonts e monta a página inteira
por `innerHTML`. A moldura desta célula nasceu com "sem CSS externo, sem JS, sem
fonte remota" e continua assim: os três PAPÉIS de fonte viraram variáveis sobre
pilhas do sistema, as abas viraram links (`?ordem=`), o voto continua
`<form method="post">` e a categoria virou `<input type=radio>` desenhado por
`:has()`. O ganho não é ideológico — é que **o estado mora no formulário**: quem
volta de um POST com erro não reescolhe a categoria do zero.

**3. Aba desconhecida é 404, como categoria desconhecida já era.** `ORDENS` é o
dicionário que define o que existe, e `?ordem=` fora dele para a página. Servir a
ordem padrão em silêncio faria a aba **mentir**: a pessoa pediria "novas" e receberia
"mais votadas" com a aba certa pintada. "Em alta" não está desenhada — é V1.2
(PLANO-MESTRE §6), porque depende de um peso de recência que ninguém decidiu.

**4. A linha do tempo chega ao template já RECORTADA por `.values(...)`.** O
`HistoricoStatus` carrega `alterado_por` — uma `Identidade`, com e-mail dentro. Não
citar o campo no template não é proteção nenhuma (o Django resolve
`{{ h.alterado_por }}` na hora de renderizar, sem import). Decidir na CONSULTA o que
existe é: a coluna nem foi buscada, então não há o que um `{{ … }}` distraído
alcance. É o raciocínio dos três degraus do guarda da `AvaliacaoInterna`, aplicado a
uma tabela que o aluno tem direito de ler **em parte**.

**5. A primeira etapa da linha do tempo não tem registro de histórico.** Uma
sugestão nasce `em_analise` sem ninguém a mover para lá, então a data dela é a da
própria criação (`marcos.setdefault(EM_ANALISE, sugestao.criado_em)`). Sem isso, toda
sugestão começaria a vida com um traço no primeiro marco. E `nao_planejado`/
`mesclado` ficam FORA das etapas: não são degraus do caminho, são saídas dele — a
página as mostra pelo selo de status.

**6. O que o botão de voto DIZ mora no `title`/`aria-label`.** O protótipo tem um
botão compacto (`▲ 218`), e uma seta sozinha não é rótulo para quem usa leitor de
tela. As palavras "Votar" e "Tirar meu voto" continuam no HTML — que é também por
onde os guardas do EVO-12b medem de quem é o voto. Mesma história no sino: a
contagem sai desenhada no `.contador` **e** no nome acessível `avisos (N)`, em
minúsculas, porque é assim que `test_o_sino_de_toda_pagina_conta_so_os_meus` a mede.
Guarda que perde a mordida por uma troca de maiúscula é guarda que ninguém sabe se
reprova.

**O que NÃO entrou, e tem despacho próprio:** a faixa de roadmap por status (as 4
zonas do rodapé do protótipo) e "meu impacto" são o **EVO-31** e a V1.2. O trilho da
esquerda já tem o lugar delas — nasce com quadro, nova ideia, avisos e (para quem
tem crachá) moderação.

### Detalhe de instrumento que custa uma rodada

Imprimir HTML renderizado no console do Windows estoura em
`UnicodeEncodeError: 'charmap' codec can't encode character '▲'` — a seta do botão
de voto. Não é bug da página: é o cp1252 do console. `PYTHONIOENCODING=utf-8` antes
do `pytest` resolve, e isso é ERROR de ambiente, não FAIL de código.

## O sininho (EVO-21): o aviso é da Caixa, não do fio

**A decisão do mantenedor, 24/08/2026, e ela não se reabre.** O plano original
mandava a célula `mensageria` avisar o aluno. Foi descartado com motivo medido: a
`mensageria` é feita para e-mail/WhatsApp, exige um destinatário, é organizada em
torno de *pedidos de compra* — e o envio de e-mail dela é um **esqueleto vazio**.
Pior: para ela mandar qualquer coisa, o e-mail do aluno teria de SAIR de dentro da
Caixa, desfazendo a `DECISAO-EVO-01` §3. O aviso é in-app, dentro da própria
Caixa, que é o que a `ESPECIFICACAO-CELULA.md` §10 já pedia. E-mail só se um dia
fizer falta.

**1. O aviso NÃO consome o próprio evento, embora o `sugestao.status-alterado`
exista desde o EVO-20 e carregue o `autor_da_sugestao_id` exatamente para isso.**
O evento existe para o mundo de FORA (gamificação, analytics — que nascem depois).
Consumir o próprio evento para escrever na própria tabela manda o fato dar uma
volta pela rede para voltar ao ponto de partida, e o preço são três coisas de
graça: modo de falha novo (Redis fora do ar ⇒ status mudado e aluno sem aviso, sem
nada indicando a falta), atraso, e — o que decide — **status e aviso passando a
poder divergir**. Por isso `avisar_o_autor()` é chamada dentro do
`transaction.atomic()` de `registrar_mudanca_de_status()`, logo abaixo do
histórico. Rollback leva os três juntos. Há guarda medindo a independência do fio:
`test_o_aviso_nasce_mesmo_sem_redis_nenhum`, com `django_db(transaction=True)`.

**2. `Aviso` tem colunas próprias e NÃO uma FK para a linha do `HistoricoStatus`.**
A FK parece mais limpa (zero duplicação, impossível divergir) e foi considerada. O
que a derruba é o `alterado_por`: com a FK, o template do aluno alcançaria **quem
moderou** — uma `Identidade`, com e-mail dentro. As duas tabelas guardam o mesmo
fato para leitores diferentes, e é essa diferença que decide o desenho: o
`HistoricoStatus` é a auditoria da EQUIPE, o `Aviso` é a cópia do ALUNO. É a mesma
lição que fez a `AvaliacaoInterna` nascer em tabela separada, e é a Virtude da
Lei 3 (*copiar dados — snapshots são sagrados*). `status_novo` e `nota` aqui não
são espelho de estado mutável: são o retrato do que mudou naquele instante.

**3. `avisar_o_autor()` recusa ser chamada fora de transação**, na forma exata do
`eventos.emitir()` do EVO-20. Lei 1: em vez de confiar que todo ponto futuro de
mudança de status lembre do `atomic`, a função levanta `AvisoForaDaTransacao`. O
guarda disso precisa de `django_db(transaction=True)` — no `django_db` padrão todo
teste já roda dentro de um atomic e a recusa nunca dispararia.

**4. O aviso vai para o autor SEMPRE, inclusive quando quem moderou foi ele
mesmo.** Suprimir esse caso seria um ramo a mais e uma exceção que o guarda de
atomicidade teria de conhecer. Do jeito que está, o invariante é uma igualdade sem
ressalva: **uma linha de `HistoricoStatus` ⇒ um `Aviso`**.

**5. `lido_em` (timestamp) e não `lido` (booleano).** O booleano responde "já
viu?"; o instante responde também "quando" — e é isso que torna a idempotência
**verificável**: a segunda marcação não pode mexer no carimbo da primeira.

**6. O aviso de outra pessoa é 404, nunca 403.** 403 diria "existe, mas não é
seu", que é confirmar a existência de um aviso alheio a quem chutou um número. O
recorte por dono mora dentro do próprio `get` (`_meus()`), de modo que não há
nenhum instante em que a linha de outra pessoa esteja carregada na requisição.

**7. A contagem de não-lidos é context processor PREGUIÇOSO.** Um item que cada
view acrescenta ao contexto seria esquecido pela primeira view escrita depois
(Lei 1). O valor no contexto é um callable, que o Django só executa se o template
pedir: página que não mostra o sino não paga consulta, e a `entrar.html` — que nem
estende a moldura — não paga nada. **O sino desenhado é o EVO-31 (Lote 3);** o que
nasceu aqui é o dado.

**8. Fica para depois, e cabe sem mudar forma nenhuma:** avisar quem VOTOU são
mais linhas de `Aviso`, com outro `destinatario`. Foi por isso que o contrato
congelado do `status-alterado` NÃO leva a lista de votantes (lista sem teto dentro
de evento).

> **PAGO no EVO-42** (25/08/2026), e a previsão se confirmou: a forma não mudou,
> ganhou uma coluna (`vinculo`). Ver "O leque de avisos (EVO-42)" no topo deste
> arquivo — inclusive o que a previsão NÃO cobria, que é o custo em consultas.

## O fuso de fábrica do Django é `America/Chicago` — e ninguém tinha notado

A página de avisos é a **primeira desta célula a renderizar uma data**, e por isso
dois defaults passaram sete despachos despercebidos:

| o que saía | por quê |
|---|---|
| `Aug. 24, 2026, 9 a.m.` | o formato padrão sai no LOCALE do processo, que é `en-us` |
| hora cinco horas antes | `TIME_ZONE` nunca foi definido ⇒ `America/Chicago` |

`USE_TZ = True` guarda em UTC e **converte na exibição** — para o fuso do
`settings`, que ninguém tinha escolhido. Correção: `TIME_ZONE = "America/Sao_Paulo"`
e formato cravado no template (`|date:"d/m/Y H:i"`), que não depende de locale. O
guarda compara com `timezone.localtime(...).strftime(...)`, nunca com uma string
escrita à mão — essa envelheceria no dia seguinte.

**Isto é dívida das outras 8 células, não invenção desta:** nenhuma define
`TIME_ZONE`, e a primeira que mostrar data ao usuário vai mostrar Chicago.

## Patch de prova gerado com `git diff` leva junto o trabalho não commitado

Armadilha nova, mordida neste despacho, e ela **refina a `armadilhas/084`** (que
manda gerar o patch com `git diff`, aplicar `-R` para o vermelho e aplicar de novo
para o verde). O que a 084 não diz: `git diff` captura **tudo** que está sem
commit, não só a quebra que você acabou de escrever. Se você quebrou o código
depois de fazer uma correção que ainda não commitou, o `git apply -R` do "volte ao
verde" **também desfaz a correção** — e desfaz em silêncio, com a suíte verde,
porque os testes que a cobriam sumiram no mesmo patch.

Foi exatamente o que aconteceu aqui: a correção de fuso horário e o teste-guarda
dela viajaram dentro do patch da prova e voltaram ao nada. O sintoma é discreto —
a contagem de testes cai de 217 para 216 e ninguém olha.

**A regra que fecha isso é a catraca do RITOS §2.1, e ela não é opcional:**
*commite o verde ANTES de gerar o patch de prova.* Com o verde commitado, o
`git diff` só pode conter a quebra, e `git apply -R` só pode restaurar. Confira
com `git diff --stat` (vazio) e com a **contagem de testes**, que é o número que
denuncia a perda.

> Não coube em `armadilhas/NNN` pelo orçamento de 15 arquivos deste despacho —
> fica registrada aqui e no handoff, para a maestro promover em PR próprio.

## O que existe aqui hoje (EVO-10 a EVO-21) — e o que NÃO existe

Do EVO-10, o esqueleto: `config/` (settings fail-hard, urls, asgi),
`GET /healthz`, `apps/core`. Do EVO-11, **a camada de dados**:
`apps/sugestoes/models.py`, a migration `0001_initial`, o seed e os três
testes-guarda de invariante. Do EVO-12a, **a porta de entrada**:
`apps/core/clients.py` (Google + `alunos`), `apps/core/sessao.py`, as rotas de
entrar/sair em `views.py`, a página `templates/sugestoes/entrar.html` e cinco
guardas de invariante novos. Do EVO-12b, **a participação do aluno**:
`apps/core/participacao.py`, as três páginas (`quadro`, `nova`, `sugestao`)
sobre `base_caixa.html`, e cinco guardas de invariante a mais. Do EVO-13, **a
moderação**: `apps/core/moderacao.py`, as páginas `fila` e `moderar`, e mais
cinco guardas — o Lote 1 fecha aqui, do lado do comportamento. Do **EVO-20**, a
**emissão**: `apps/sugestoes/eventos.py` (os quatro construtores de `data` +
`emitir`), `apps/sugestoes/tasks.py` (o relay), `config/huey.py`, o model
`OutboxEvent` com a migration `0002`, e três arquivos de guarda novos
(162 → 195 testes). Do **EVO-21**, o **sininho**: `apps/core/avisos.py` (a
criação transacional, as duas rotas e o context processor da contagem), o model
`Aviso` com a migration `0003`, a página `avisos.html`, o link na moldura e três
arquivos de guarda novos (195 → 217 testes). Aqui fecha o Lote 2, e a Caixa passa
a ter jornada completa: a pessoa sugere, a equipe responde, e ela **fica sabendo**.

**Continua não existindo**, e cada um tem despacho próprio: **consumir** evento
(nenhuma célula assina os quatro ainda), merge de sugestão (V1.1 na spec §10),
middleware CONV-SITE e `config/api.py`. O sino desenhado saiu no EVO-31 (Lote 3);
**avisar quem VOTOU saiu no EVO-42** (Lote 4), junto com quem comentou. O que
segue fora, e é rito e não despacho: o sininho VISÍVEL FORA da Caixa, que exige
operação nova num contrato congelado.

## A emissão (EVO-20): a Caixa passou a AFIRMAR fatos

Os quatro contratos foram congelados pelo Rito (RITOS §3, PR #128) **antes** de
existir código que os emitisse — e isso mudou o trabalho: aqui não houve nenhuma
decisão de formato a tomar, só a de como não divergir do que já era lei.

**1. Um lugar só monta o `data`, e é ele que o guarda mira.** Os quatro
construtores moram em `apps/sugestoes/eventos.py`; as views chamam e não montam
dicionário. Se cada ponto de emissão montasse o seu, o dia em que o contrato
ganhasse um campo seriam quatro lugares para lembrar, e o guarda estaria
conferindo quatro cópias que envelhecem em ritmos diferentes.

**2. O guarda de contrato LÊ o arquivo de `contracts/eventos/` — nunca uma
cópia.** `jsonschema` com `Draft202012Validator` + `FormatChecker` (sem o
`FormatChecker` o `format: uuid` vira anotação decorativa e um `event_id` igual
a `"abc"` passaria). **E ele morde**: os quatro contratos são
`additionalProperties: false`, então um `email` a mais no `data` reprova o CI
nos quatro. É a decisão de privacidade do EVO-01 §3 virando trava mecânica em
vez de combinado — medido, não suposto: o patch que acrescenta
`"email": sugestao.autor.email` deixa 4 testes vermelhos.

**3. `emitir()` recusa ser chamada fora de `transaction.atomic()`.** Lei 1: em
vez de confiar que todo ponto de emissão futuro se lembre do `atomic`, a própria
função levanta `EventoForaDaTransacao`. O guarda disso precisa de
`django_db(transaction=True)` — no `django_db` padrão TODO teste já roda dentro
de um atomic e a recusa nunca dispararia (é a `armadilhas/057` pelo avesso).

**4. A metade do INV-P6 que quase ninguém escreve.** "Rollback não deixa evento
órfão" é a metade fácil, e ela continua verde mesmo se alguém mover a emissão
para DEPOIS do `with`. A metade que pega esse erro é a inversa: **emissão que
falha desfaz o fato**. `tests/test_inv_outbox_transacional.py` a varre sobre os
quatro pontos, e é ela que fica vermelha (4 testes) quando a emissão sai de
dentro do `atomic`.

**5. Emite-se o FATO, não o clique.** `votar` só emite quando o `get_or_create`
devolveu `criado=True`; `desvotar` só quando o `delete()` devolveu contagem > 0.
Sem isso, o segundo clique faria a plataforma contar dois votos onde há um, e o
`total_votos` do evento passaria a divergir da contagem do banco.

**6. `nota` ausente ≠ `nota` vazia.** O contrato tem `nota` como opcional em
`status-alterado`; mandar `""` obrigaria todo consumidor a distinguir "sem
justificativa" de "justificativa vazia", que são dois nomes para a mesma coisa.
O campo só entra quando existe.

## O guarda de UUID ganhou UMA exceção — e ela é derivada do contrato

`test_os_ids_inter_celula_sao_texto_opaco_e_nao_uuid` proibia **qualquer**
`UUIDField` nos models desta célula. `OutboxEvent.event_id` colide com isso de
frente — e a colisão é aparente, não real: o guarda fala de **ids inter-célula
de domínio** (`site_id`, `produto_id`, `Identidade.id`), e `event_id` é o id do
**envelope**, que os quatro contratos congelados pedem em `format: uuid`, como
pagamentos, checkout e quiz já fazem há meses.

A saída **não** foi transformar o campo em `CharField` para o guarda calar (isso
faria o outbox desta célula divergir do padrão provado em produção, que o
despacho manda copiar). Foi estreitar o guarda com uma exceção nominal — e,
para que ela não envelheça em silêncio, um teste novo
(`test_a_excecao_do_event_id_e_o_que_o_contrato_congelado_pede`) **lê os quatro
`.json`** e cai se algum deixar de pedir `format: uuid`. A exceção só se
sustenta enquanto o contrato a justificar.

Regra que vale para o próximo: **guarda que colide com contrato congelado não
se afrouxa nem se contorna — se ESTREITA, com a exceção derivada da lei que a
justifica.** Exceção escrita à mão é uma linha que alguém pôs um dia para o CI
parar de reclamar, e que continua valendo depois de o motivo sumir.

## Redis de dev: porta 16380, container `sugestoes-redis-dev`

`docker run -d --name sugestoes-redis-dev -p 16380:6379 redis:7`. Porta
exclusiva pelo mesmo motivo do `55440` do Postgres desta célula: `16379` já é do
`mensageria-redis`, e duas sessões de agente em paralelo (o modo normal desta
casa) não podem disputar o mesmo Redis — `XRANGE` de uma leria evento da outra.

**Isso NÃO está no `docker-compose.dev.yml`**: o orçamento de 15 arquivos deste
despacho fechou exatamente em 15, e o compose ficou de fora. Quem tiver um
arquivo sobrando, acrescente o serviço `redis` (com essa porta) e o
`sugestoes-relay` ao compose de dev — está registrado no handoff do EVO-20.

## Como provar o relay CONTRA REDIS DE VERDADE (o roteiro que valeu no EVO-20)

A suíte dubla o transporte (`redis.from_url`), e de propósito: uma suíte que
precisa de container fica vermelha por motivo alheio, e a máquina do mantenedor
é Windows. A prova do fio de verdade é este roteiro, e ele tem um truque que
vale guardar:

1. sobe o Redis de dev (acima) e o worker, **com** as duas variáveis:
   `REDIS_STREAMS_URL=redis://127.0.0.1:16380/0`,
   `HUEY_REDIS_URL=redis://127.0.0.1:16380/1`, `python manage.py run_huey`;
2. provoca os quatro fatos num processo **SEM** `REDIS_STREAMS_URL`. O
   `relay_apos_commit` engole o `KeyError` (§5.3) e os quatro eventos ficam
   PENDENTES na outbox;
3. espera o minuto do periódico e confere com
   `docker exec sugestoes-redis-dev redis-cli -n 0 XRANGE eventos.sugestao.criada - +`.

O passo 2 é o truque: sem ele, quem publica é o `on_commit` do próprio processo
de teste, e o roteiro **não prova nada sobre o worker**. Tirando a variável, a
única coisa capaz de publicar é o `run_huey` — que é exatamente o que o serviço
`sugestoes-relay` roda na VPS. No EVO-20 isso pegou o log que interessa:
`The following commands are available: + apps.sugestoes.tasks.relay_outbox_periodico`
(o oposto do registro vazio da `armadilhas/030`).

Detalhe que custou uma rodada: um script de limpeza de banco de dev **não pode**
usar `HistoricoStatus.objects.all().delete()` — o append-only do EVO-11 recusa,
nos três degraus. Use `TRUNCATE ... RESTART IDENTITY CASCADE` por cursor.

## A moderação (EVO-13): as seis decisões de desenho

**1. `exige_staff` EMPILHA sobre `exige_sessao`, e não fica ao lado dele.** O
anônimo continua sendo mandado para a porta (302), como em toda a célula; só
quem já tem sessão chega a receber **403**. A diferença de código é uma linha
(`return exige_sessao(cracha)`), e ela é o que mantém verdadeiro o guarda que
varre o urlconf exigindo o porteiro de sessão em toda rota não pública. É
também o que faz as **três varreduras do urlconf** cobrirem o urlconf inteiro,
sem sobra nem sobreposição:

| rota | quem a pega |
|---|---|
| sem `exige_sessao`, fora da lista pública | `test_inv_sem_sessao_nada.py` |
| com `exige_staff` | `test_inv_so_staff_modera.py` (aluno ⇒ 403 em todas) |
| com `exige_sessao`, sem `exige_staff` | `test_inv_avaliacao_interna_fora_do_alcance.py` |

Foi por causa disso que o `_rotas_de_participacao()` do terceiro arquivo ganhou
o recorte `and not exige_staff`: sem ele, o guarda do aluno passaria a exigir
que a jornada dele percorresse as páginas da equipe — que devolvem 403
justamente porque ele não pode entrar nelas. **Não é afrouxamento; é o recorte
que faz as três somarem o urlconf inteiro.**

**2. 403 e não 302.** Quem chega à moderação sem crachá não esqueceu de entrar:
já entrou e não tem o papel. Mandá-lo para a tela de login seria dizer "tente de
novo" a quem não tem o que tentar — e esconderia a única resposta verdadeira
atrás de um redirecionamento. É também a letra da DoD do MVP (spec §11).

**3. Mudar o status quando ele já é aquele é PERMITIDO, e grava histórico.** A
tentação é recusar o no-op. Mas metade do valor do formulário é a nota
("seguimos analisando, e o motivo é este"), e recusar levaria a equipe a agir
sem nada ficar escrito — exatamente o que o histórico existe para impedir. Cada
POST aceito ⇒ **uma** linha, sempre.

**4. `mesclado` fica FORA do `<select>`, mesmo existindo no model.** Mesclar é
V1.1 (§10) e é uma operação transacional inteira — mover votos sem duplicar
ator, preservar comentários e histórico, manter a URL antiga resolvendo. Deixar
o rótulo disponível daria à equipe um jeito de marcar "mesclado" sem que nada
tivesse sido mesclado, e a lista de mescladas nasceria mentindo, com
`sugestao_canonica` vazia. Há guarda
(`test_mesclado_nao_entra_pela_porta_do_status`).

**5. A escala 0–5 das notas é decisão desta implementação, não da spec.** A §6
só diz `PositiveSmallIntegerField`. O teto existe para que a recusa venha como
uma frase em português em vez de um `IntegrityError` do check constraint do
Postgres — que é o que um `-1` produziria, com 500 na cara de quem digitou.

**6. O ponto de emissão do evento está marcado, e não é decorativo.** A DoD do
MVP pede o `sugestao.status-alterado` *"publicado antes do commit da transação
de status"*. O comentário `[EVO-20 — Lote 2]` está **dentro** do
`with transaction.atomic()` de `registrar_mudanca_de_status()`, e não uma linha
depois do `with`. Quem for escrever o outbox: é ali, e a diferença de duas
linhas é a diferença entre evento transacional e evento perdido.

## `{# … #}` do Django comenta UMA linha — e a de baixo vai para o HTML

Armadilha nova, mordida neste despacho e ainda sem entrada em `armadilhas/`
(não coube no orçamento de 15 arquivos — fica registrada aqui e no handoff).

```django
{# comentário de quatro linhas
   escrito assim vai INTEIRO
   para dentro da página, e o
   navegador mostra o texto #}
```

`{# … #}` é **de uma linha só**. Multi-linha exige
`{% comment %} … {% endcomment %}`. O que torna isso caro é o modo de falha:
não há erro, não há aviso, a página renderiza — e o comentário aparece na tela
do usuário. Aqui ele vazou um comentário sobre o crachá da equipe para dentro da
página do ALUNO, e quem pegou foi um guarda que procurava outra coisa
(`test_o_aluno_nao_ve_esse_link`), pelo texto "moderação" no corpo. Se a
asserção fosse só pelo `href`, teria passado.

## A spec §8 pede um ChangeSpec que esta célula não tem — PAGA no EVO-40

> **Resolvida em 25/08/2026.** O que este bloco descreve é o estado até o
> EVO-13; a decisão que faltava foi tomada (tabela nesta célula) e a trava
> existe nos três degraus — ver "A trava do ChangeSpec (EVO-40)" no topo deste
> arquivo. O texto abaixo fica porque a PERGUNTA que ele formulou é o que
> definiu a resposta.

A `ESPECIFICACAO-CELULA.md` §8 tem um invariante a mais que os outros:

> `Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir
> um ChangeSpec aprovado referenciando aquele `suggestion_id`.

**Não há model de ChangeSpec nesta célula** — a `0001_initial` (mergeada) não o
tem, e `FORMATO-CHANGESPEC.md` descreve um artefato de processo, não uma tabela.
O EVO-13 seguiu a regra de parada do despacho ("siga o banco e registre a
divergência"): a transição `planejado → em_desenvolvimento` é aceita sem
conferir ChangeSpec nenhum, e **isso está sem guarda de propósito** — um guarda
aqui teria de inventar o modelo de dados que a decisão ainda não tomou.

Quem for fechar isso decide primeiro **onde o ChangeSpec mora**: tabela nesta
célula, ou um `changespec_id` no `HistoricoStatus` (que é append-only e já
carrega quem mudou o quê). As duas mudam migration; nenhuma é decisão de
despacho.

## A participação (EVO-12b): as cinco decisões de desenho

**1. Páginas renderizadas no servidor, não uma API JSON — e o `contrato-check`
já dizia isso.** O `reason` do manifesto para esta célula é explícito: *"nem
hoje (esqueleto), nem quando a API de sugerir/votar/comentar nascer"*. A
superfície é consumida pelo front-end da PRÓPRIA célula; um `NinjaAPI` aqui
seria um contrato sem consumidor, mais uma dependência no `requirements.txt` e
uma ilha de JS para renderizar o que um `<form>` já renderiza. O dia em que
outra célula precisar consumir a Caixa é RITOS.md §3, não uma decisão de
sessão — e aí nasce `config/api.py` ao lado destas páginas, não no lugar delas.

**2. TODA rota exige sessão, inclusive a de só olhar o quadro.** A Caixa é de
quem tem matrícula (`DECISAO-EVO-01` §2). Uma lista pública de sugestões seria a
única superfície da célula que não respeita essa decisão — e a mais fácil de
alguém abrir "só para o pessoal ver", sem perceber que está publicando o que os
alunos escreveram. O porteiro é o decorador `exige_sessao`, e ele deixa um
atributo no objeto da view: é por esse atributo que
`test_inv_sem_sessao_nada.py` **varre o urlconf** e reprova rota nova que tenha
nascido aberta. Detalhe que faz isso funcionar: `functools.wraps` copia o
`__dict__` da função embrulhada, então o atributo sobrevive ao `require_GET`/
`require_POST` **desde que `exige_sessao` seja o decorador de dentro**.

**3. `quadro_atual()` é a costura do CONV-SITE, e ela é fail-closed.** A célula
ainda não resolve Host→Site, então não há de onde tirar o `site_id`. Um quadro
no banco serve; **zero ou dois param com 404 e uma mensagem dizendo o que
falta**. Escolher "o primeiro" seria esta célula inventando um site padrão em
silêncio — o erro exato que a Lei 9 proíbe. Quando o middleware chegar, muda
essa função e nada mais.

**4. A busca de duplicatas informa; não bloqueia.** O formulário tem duas
etapas — "conferir se já existe" devolve as parecidas sem criar nada, e só
então aparece "publicar assim mesmo". Um portão que recusasse por semelhança
calaria a segunda pessoa a descrever a mesma dor com outras palavras, que é
caso comum, não exótico. A busca é `icontains` por palavra de 4+ letras (a §10
admite `icontains` ou trigram): palavra curta casa com tudo, e o que sempre
casa não avisa nada.

**5. O redirecionamento depois de votar tem DOIS destinos fixos, escolhidos
pelo código.** O formulário só diz de onde veio (`de=quadro`); a URL de destino
nunca vem do POST. Um campo `proximo` com o endereço dentro seria
redirecionamento aberto — a Caixa mandando o aluno para onde o atacante
escrever. Há guarda para isso (`test_um_destino_inventado_no_formulario_e_ignorado`).

## O guarda da `AvaliacaoInterna` tem três degraus, e o do meio é o que pega

A spec §8 diz que a avaliação interna nunca é lida por endpoint que o aluno
alcança. Provar isso com "não escrevi o campo no template" não prova nada — o
Django resolve `{{ sugestao.avaliacao.notas }}` na hora de renderizar, sem
import nenhum. Os três degraus de
`tests/test_inv_avaliacao_interna_fora_do_alcance.py`:

1. **o SQL**: a jornada inteira do aluno roda dentro de um
   `CaptureQueriesContext` e o nome da tabela não pode aparecer em consulta
   nenhuma — é o degrau que pega o acesso por template e o `select_related`
   distraído;
2. **o corpo das respostas**: a avaliação é semeada com uma marca
   inconfundível, e nenhuma página do aluno pode devolvê-la;
3. **a AST do módulo**: `participacao.py` não pode nomear `AvaliacaoInterna`
   nem o atributo `avaliacao` — via `ast`, não `grep`, para que citar o nome num
   comentário (como o próprio arquivo de teste faz) não conte.

E a completude é mecânica: a lista de rotas percorridas é conferida contra o
urlconf, então rota de participação nova deixa o guarda VERMELHO até alguém
acrescentá-la à jornada.

## A raiz virou o quadro, e a porta ganhou um link (senão vira beco)

`path("", ver_quadro, name="quadro")` — o `urls.py` do EVO-12a já previa isso.
Mas o `_abrir()` da entrada continua redirecionando para `entrar`, **de
propósito**: o quadro exige um `Quadro` semeado, e uma porta que caísse em 404
logo depois de um login bem-sucedido seria pior que um clique a mais. Daí o
link "Ver o quadro de sugestões" no `entrar.html` — sem ele a pessoa entra,
lê "você está dentro" e não tem para onde ir.

## O que ficou fora do EVO-12b, e não por esquecimento

- **Status e histórico**: mudar status é do staff (EVO-13). Nenhuma rota daqui
  escreve `HistoricoStatus` — e `Sugestao` não é apagada em lugar nenhum, o que
  mantém o `PROTECT` do histórico verdadeiro sem nenhum caso especial.
- **Merge de sugestão**: a §10 põe em V1.1. `sugestao_canonica` continua no
  model, sem ninguém escrevendo nela.
- **Evento de `sugestao.criada` / `voto-adicionado`**: era do Lote 2 e **entrou
  no EVO-20** — os pontos de emissão são exatamente os `create()`/`delete()`
  deste arquivo, como o EVO-12b previu. O que a célula ainda NÃO faz é
  **consumir** evento (EVO-21).

## A porta de entrada (EVO-12a): as cinco decisões de desenho

A lei é a `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md`. O que ela NÃO
decidiu, e este despacho decidiu:

**1. A sessão é um cookie assinado com um `Identidade.id` dentro, e mais nada.**
Nem e-mail (o backend de cookie *assina*, não *cifra* — o conteúdo é legível por
quem tem o cookie, e e-mail ali seria dado pessoal espalhado, justo o que a §3
evitou no banco), nem papel. Não há tabela `django_session` e
`django.contrib.sessions` **não** está em `INSTALLED_APPS`: este backend não tem
model. Trocar por sessão em banco, no dia em que for preciso revogar sessão de
longe, é mudar `SESSION_ENGINE` e nada mais.

**2. O papel `staff` é DERIVADO a cada requisição, nunca persistido.** É o que
faz a promessa da §4 ("editar uma variável e reiniciar, sem migração e sem
deploy") ser verdadeira: gravar o papel na linha da `Identidade` — ou no cookie —
faria tirar alguém da lista não tirar o crachá de quem já estava dentro. Há
guarda para isso (`test_o_papel_sai_com_a_variavel_de_ambiente`).

**3. O perfil vem do `userinfo` do Google, não da verificação local do
`id_token`.** Verificar o JWT exigiria buscar o JWKS (mais uma ida à rede, mais
um cache para envelhecer errado) e uma biblioteca de criptografia a mais. O
`access_token` veio da própria troca servidor-a-servidor sobre TLS.

**4. `email_verified` só passa como booleano `True`.** `if not
perfil.get("email_verified")` é o jeito exato de o portão virar peneira: a string
`"false"` é verdadeira em Python. O guarda cobre `"false"`, o campo ausente e o
booleano.

**5. Cookies com nome próprio (`sugestoes_sessao`, `sugestoes_csrf`) e
`SESSION_COOKIE_PATH` no prefixo.** `meshcraft.top` serve o `funil` na raiz e a
Caixa sob `/forms/sugestoes`: duas células no mesmo domínio com `sessionid` é uma
sobrescrevendo a sessão da outra.

E uma que parece detalhe e não é: **`SESSION_COOKIE_SAMESITE = "Lax"` é
obrigatório**, não preferência. A volta do Google é navegação de topo vinda de
`accounts.google.com`; com `Strict` o navegador não manda o cookie nessa volta, o
`state` guardado some, e **todo login legítimo falha como se fosse
falsificação**.

## Um `httpx.Client` por processo — a suíte caiu de 85 s para 2 s

O padrão R2 do `CAMINHO-DOURADO.md` (e o `clients.py` do `checkout`) usa
`httpx.get(...)` direto. Cada chamada dessas constrói um cliente novo e, com ele,
um `ssl.SSLContext` que carrega os certificados raiz do sistema. **Medido nesta
máquina: 0,4 s por chamada, contra 0,000 s com o cliente reaproveitado.**

São dois saltos por login (Google + `alunos`), ou seja quase um segundo de espera
pura para quem está entrando — e a suíte desta célula levava **85 segundos**
antes da troca, contra **2 segundos** depois. Daí `apps/core/clients.py::http()`,
um `httpx.Client` preguiçoso por processo. `httpx.Client` é seguro entre threads,
que é o que o uvicorn precisa.

**Isto é dívida das outras células, não invenção desta** — o mesmo custo está no
`checkout` e no `funil`, só que escondido em suítes menores.

## A suíte NÃO usa a rede, e isso é verificável em um comando

Google e `alunos` são dublados com `respx` em `tests/conftest.py`. A prova não é
promessa: rode a suíte com todo socket e todo DNS não-local proibidos e ela passa
inteira (só o Postgres local é liberado).

```python
# um plugin de pytest de dez linhas, fora do repositório:
import socket
LOCAIS = {"127.0.0.1", "::1", "localhost"}
_connect, _dns = socket.socket.connect, socket.getaddrinfo
def _c(self, e, *a, **k):
    if str(e[0] if isinstance(e, tuple) else e) not in LOCAIS:
        raise AssertionError(f"REDE PROIBIDA: {e!r}")
    return _connect(self, e, *a, **k)
def _d(h, *a, **k):
    if str(h) not in LOCAIS:
        raise AssertionError(f"REDE PROIBIDA: DNS de {h!r}")
    return _dns(h, *a, **k)
socket.socket.connect, socket.getaddrinfo = _c, _d
```

```
PYTHONPATH=<pasta> python -m pytest -q -p sem_rede
60 passed in 1.84s
```

O `respx` sozinho já dá metade da garantia: rota não registrada vira
`AllMockedAssertionError`, não requisição de verdade (`armadilhas/054`). Um salto
de rede novo neste fluxo estoura a suíte em vez de sair em silêncio para a
internet.

## `reverse()` mente no teste e acerta em produção (armadilhas/081)

A pegadinha que custou a maior parte do tempo deste despacho, e que vale para
`checkout` e `quiz` também: `reverse()` **não lê** `settings.FORCE_SCRIPT_NAME`.
Ele lê um prefixo de thread que o SERVIDOR preenche
(`ASGIHandler.__call__` chama `set_script_prefix`) — e os handlers de teste do
Django **não chamam**. Resultado: `path_info` certo e `reverse()` sem prefixo, na
mesma requisição, com a produção correta o tempo todo.

No OAuth isso é grave: o `redirect_uri` é comparado caractere a caractere pelo
Google. `tests/test_entrada_script_name.py` emula o servidor
(`set_script_prefix` + `clear_script_prefix` na saída — o prefixo é de thread e
vaza entre testes) e confere as três partes do endereço separadamente, porque
elas falham por motivos diferentes: o esquema vem de `SECURE_PROXY_SSL_HEADER`, o
domínio vem do `Host` da requisição, o caminho vem de `reverse()`.

## Matrícula `reembolsada` entra — DECIDIDO pelo mantenedor em 24/08/2026

O contrato de `alunos` devolve matrículas com `status` em
`[ativa, suspensa, reembolsada]`. A `DECISAO-EVO-01` diz "só quem tem matrícula"
e **não fala de status**. Esta implementação segue a decisão ao pé da letra:
qualquer matrícula devolvida deixa entrar.

Não foi descuido — filtrar por `status == "ativa"` seria decidir, dentro de um
despacho, que quem pediu reembolso perde a voz na Caixa.

**A pergunta foi levada ao mantenedor e ele decidiu em 24/08/2026: TODAS as
situações entram, inclusive a `reembolsada`.** Quem já foi aluno mantém a voz.
Está na `DECISAO-EVO-01-identidade.md` **§4.1**, que é a lei do assunto.

**Isto agora tem guarda** (EVO-13): o patch que "conserta" o filtro para
`status == "ativa"` deixa o CI VERMELHO, de propósito. Se você chegou aqui
achando que deixar reembolsado entrar é bug esquecido — não é. Foi escolhido, e
mudar exige nova sessão com o mantenedor, nunca uma decisão de despacho.

## O modelo de dados diverge da spec em três pontos, e os três são deliberados

A `ESPECIFICACAO-CELULA.md` §6 foi escrita antes da `AUDITORIA-AS-IS.md`. Onde
as duas discordam, **vence a realidade medida** — e é isto que a §6 diz de
errado:

| A spec §6 diz | O que está no código | Por quê |
|---|---|---|
| `tenant_id = models.UUIDField()` | `site_id = models.CharField()` | "Tenant" não existe no vocabulário da casa; site existe (Lei 9). E em toda a plataforma o ID que atravessa fronteira é `type: string` **sem** `format: uuid` (auditoria Q3) |
| `autor_id = models.UUIDField()` | `autor = FK(Identidade)` | Ver abaixo |
| `HistoricoStatus.sugestao` com `CASCADE` | `PROTECT` | A §8 da mesma spec diz "nenhuma linha é apagada". As duas não cabiam juntas (`armadilhas/079`) |

Há um teste-guarda mecânico para o primeiro item
(`tests/test_inv_sem_fk_para_fora.py::test_os_ids_inter_celula_sao_texto_opaco_e_nao_uuid`):
qualquer `UUIDField` que apareça em model desta célula reprova o CI. Não é
gosto — é a fronteira que os consumidores já falam.

## `Identidade` é FK de verdade, e isso NÃO fura a Lei 3

A leitura apressada da Lei 3 ("nenhuma FK saindo da célula") vira, na cabeça de
quem está com pressa, "nenhuma FK". São coisas diferentes: o que o Postgres não
sustenta é constraint **entre bancos**, e `Identidade` mora no mesmo
`sugestoes_db` de `Sugestao`, `Voto` e `Comentario`. Dentro do banco, a
integridade referencial é de graça — recusá-la seria pagar o preço da restrição
sem receber nada em troca.

E não custa o nome: FK chamada `autor` faz o Django criar a coluna `autor_id`,
que é exatamente o campo que a spec pede — e continua sendo **texto opaco**,
porque `Identidade.id` é `CharField`. Ganha-se o `ON DELETE` explícito de
brinde: `PROTECT` em toda referência a `Identidade`, para que apagar uma pessoa
nunca vire histórico órfão em silêncio.

**O que continua proibido, e o guarda que impõe:** FK para model de outra
célula. `tests/test_inv_sem_fk_para_fora.py` varre `apps.get_models()` e deriva
sozinho quais apps são desta célula (os que moram em `apps/`), então app novo
entra no guarda sem ninguém lembrar de cadastrá-lo.

## O append-only tem TRÊS degraus, e o terceiro é o banco

`HistoricoStatus` (spec §8) é imposto em `save()`, no `AppendOnlyQuerySet`
(`update`/`delete`/`bulk_update` — `armadilhas/023`) **e** num trigger plpgsql
criado pela `0001_initial`. O terceiro não é zelo excessivo: sem ele, o
`Collector` do Django apagaria o histórico inteiro por um `CASCADE`, sem passar
por nenhum dos dois primeiros e sem erro nenhum (`armadilhas/079`).

Consequência prática para quem for escrever a API (EVO-12/EVO-13): **não existe
"corrigir o histórico"**. Correção é `HistoricoStatus.objects.create(...)` com o
estado novo; qualquer tentativa de editar levanta `RegistroImutavel` antes de
chegar ao banco, e o banco recusa de novo se alguém desviar do ORM.

## O e-mail vive numa linha só, e há guarda para isso

`Identidade.email` é o único campo de e-mail da célula (EVO-01 §3), e
`test_o_email_vive_numa_linha_so` reprova qualquer `EmailField` — ou campo com
"email" no nome — que apareça em outro model. Dado pessoal espalhado por cada
voto de cada pessoa não é problema de estilo: é o que faz uma troca de endereço
virar migração de dados em vez de um `UPDATE` de uma linha.

## O prefixo mora no env, e o `/healthz` foi travado ANTES de o middleware chegar

A Caixa serve em `meshcraft.top/forms/sugestoes/`
(`DECISAO-EVO-01-identidade.md` §2) — ou seja, **sob `SCRIPT_NAME`**, o mesmo
regime que matou a sonda do `checkout` (PR #65) e do `quiz` (PR #71). A
armadilha (`armadilhas/029`) tem duas metades, e as duas estão travadas por
`tests/test_healthz_script_name.py`:

1. `config/urls.py` **não conhece o prefixo**. Quem o aplica é
   `FORCE_SCRIPT_NAME`, lido do env. Rota escrita como
   `path("forms/sugestoes/healthz", …)` faz da mudança de URL uma cirurgia em
   código; o teste `test_urlconf_nao_conhece_o_prefixo` reprova isso.
2. Quando o middleware CONV-SITE entrar (EVO-11/EVO-12), a isenção de
   `/healthz` compara **`request.path_info`**, nunca `request.path`. Pela borda
   pública o Traefik NÃO remove o prefixo: a request line que chega ao uvicorn
   é `GET /forms/sugestoes/healthz`, e aí `request.path` contém o prefixo em
   qualquer versão do Django.

**O guarda usa `AsyncClient`, e isso não é preciosismo.** Em produção a célula
roda sob uvicorn, logo o objeto de requisição é `ASGIRequest` — que faz
`path = scope["path"]` e `path_info = path.removeprefix(script_name)`. O
`client` síncrono do Django constrói um `WSGIRequest`, cuja aritmética é a
inversa (`path_info` vem do environ como está, `path = script_name + path_info`).
Testar a borda pública pelo client síncrono mediria outra coisa. Detalhe que
custa tempo se descoberto na hora errada: no `AsyncClient` a requisição sai por
`resp.asgi_request`, **não** `resp.wsgi_request` (que só existe no síncrono, e
é o que os testes das outras células usam).

## O compose de dev foge do molde em duas linhas, de propósito

`docker-compose.dev.yml` das outras 8 células usa `name: dev-celula` e mapeia o
Postgres em `5432`. Aqui é `name: dev-sugestoes`, `container_name:
sugestoes-pg-dev` e `55440:5432`.

O nome do projeto do compose é o **namespace dos containers**: com
`dev-celula` em todas, duas sessões de agente rodando em paralelo (o modo de
trabalho normal desta casa — `RUNBOOK-LOTES.md`) disputam o mesmo
`dev-celula-db-1`, e a segunda derruba o banco da primeira sem avisar. A porta
55440 é a pré-atribuída a esta célula, para não colidir com o `55432` da
partida rápida do `ARMADILHAS.md` §2.

**Isso é dívida das outras 8, não invenção desta.** Se alguém uniformizar, o
caminho é uniformizar para o nome por célula, não de volta para `dev-celula`.

## Fail-hard: só as duas variáveis que o CI já fornece

`config/settings.py` levanta `ImproperlyConfigured` no import para
`DJANGO_SECRET_KEY` e `DATABASE_URL` — e mais nada. O motivo é mecânico
(`armadilhas/037`): variável nova e fail-hard no `settings.py` precisa ser
espelhada no bloco `env:` de `.github/workflows/ci-celula.yml`, que é o único
lugar que alimenta o `make ci` do CI real — e `.github/` está fora do escopo
desta célula. As variáveis que ainda vão nascer aqui
(`SUGESTOES_STAFF_EMAILS`, `ALUNOS_API_URL`, `TOKEN_ALUNOS`, credenciais do
Google) são lidas **no ponto de uso**, com default inofensivo, como manda a
convenção do lote de Huey. `SCRIPT_NAME` já segue essa forma
(`os.environ.get(...) or None`).

## `contrato-check` veio do template, não do vizinho

O `Makefile` desta célula usa `bash ../../ci/freeze-de-contrato.sh $(CELULA)`
— a forma do `celula-template/`. O `Makefile` de `quiz` e `funil` ainda usa a
forma antiga (`if [ -f ../../contracts/… ]` + escrita em `/tmp`), que tem dois
problemas: infere "não tem contrato" de "não achei o arquivo" (exatamente a
ambiguidade que o `ci/manifesto-de-contratos.json` foi criado para matar,
INV-CI01) e escreve em `/tmp`, que não existe na máquina Windows do
mantenedor. Quem decide é o manifesto, e nele esta célula é
`freeze: not-applicable`.

## Por que `not-applicable` aqui não envelhece como o de `funil`/`quiz`

O `reason` de `funil`, `mensageria` e `quiz` diz "célula ainda em esqueleto: só
`/healthz`" — um motivo que caduca no dia em que a célula ganhar API. O desta
não caduca, porque não é sobre maturidade: `contracts/` é a fronteira **ENTRE**
células (`contracts/README.md`), e a superfície HTTP da Caixa é consumida pelo
front-end **dela mesma**. Mesmo depois de EVO-12, com sugerir/votar/comentar no
ar, continua não havendo contrato a congelar. Só muda se outra célula precisar
consumir a Caixa — e aí é RITOS.md §3, não edição de manifesto.

> **O dia chegou — 24/08/2026.** O `funil` passou a consumir a Caixa
> (`docs/decisoes/DECISAO-onde-mora-a-sessao.md`), exatamente pela porta que o
> parágrafo acima previu. O manifesto vira `freeze: required` no PR seguinte, o
> do contrato — que anda sozinho, porque `ci/cerca-de-celula.sh` proíbe
> `contracts/` e `services/` no mesmo PR. O exportador
> (`apps/core/management/commands/export_openapi.py`) nasceu **neste** PR por
> causa dessa mesma cerca: ele é `services/`, então não poderia viajar junto
> com o contrato.

## O cookie de sessão tinha um endereço escrito nele — e era esse o bug do site

Até 24/08/2026 esta linha era `SESSION_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"`.
Parecia zelo — "o cookie nem sai para o resto do domínio" — e era, para a
pergunta de 23/08 ("como o aluno entra **na Caixa**?").

Quando a pergunta virou "como a pessoa entra **no site**?", essa linha passou a
ser o problema inteiro: em produção o caminho é `/forms/sugestoes`, então o
navegador **não envia** o cookie para `/pt-br/qualquer-coisa`, e o site não tem
como saber que a pessoa entrou. Nenhuma quantidade de botão "Entrar" espalhado
resolveria — não era falta de tela, era o crachá não valer fora da sala.

Três coisas que andam juntas nessa mudança, e **as três são obrigatórias**:

1. **`SESSION_COOKIE_PATH = "/"`** — alcance de site. Não é
   `SESSION_COOKIE_DOMAIN`: alcance de CAMINHO é um host, todas as páginas;
   alcance de DOMÍNIO espalharia por subdomínios que não são desta plataforma.
2. **Nome novo do cookie** (`sugestoes_sessao` → `meshcraft_sessao`). O
   navegador guarda cookie por (nome, domínio, **caminho**): publicar o mesmo
   nome em `/` deixaria dois cookies homônimos convivendo, e qual deles o
   servidor lê passa a depender de precedência por caminho. Nome novo faz o
   velho ser ignorado. Preço: todo mundo logado é deslogado **uma** vez.
3. **O CSRF NÃO acompanhou.** `CSRF_COOKIE_PATH` era `= SESSION_COOKIE_PATH`,
   por acidente de escrita. Agora diverge por decisão: a sessão precisa do
   site inteiro, o token de CSRF protege os `<form>` **desta** célula.

### O guarda óbvio deste item seria falso-verde

O primeiro teste que escrevi para isso abria a porta, lia o cookie e afirmava
`path == "/"`. **Ele passava com e sem a correção** — porque em dev não há
`SCRIPT_NAME`, e a linha antiga (`FORCE_SCRIPT_NAME or "/"`) também devolvia
`/`. Um guarda que nunca reprova é um guarda que ninguém sabe se reprova
(RETROSPECTIVA §1).

O guarda que vale carrega `config/settings.py` como um módulo NOVO, com
`SCRIPT_NAME` no ambiente — o regime da VPS
(`tests/test_sessao_interno.py::test_em_producao_a_sessao_vale_no_site_e_o_csrf_so_na_caixa`).
Falsificado antes de entrar: com a linha antiga de volta, ele reprova com
`assert '/forms/sugestoes' == '/'`.

E use módulo novo via `importlib.util`, **nunca `reload` de `config.settings`**:
o `django.conf.settings` da suíte aponta para aquele objeto, e recarregá-lo
troca a configuração viva no meio dos outros testes — falha que só apareceria
como teste vizinho quebrando por ordem de execução.

## A superfície de MÁQUINA: duas perguntas, dois códigos de resposta

`/interno/sessao` cruza duas perguntas, e confundi-las é o erro caro:

| Pergunta | Prova | Falha vira |
|---|---|---|
| quem CHAMA? | Bearer do par (`TOKENS_ACEITOS_*`) | **401** |
| quem é a PESSOA? | cookie repassado pelo chamador | **200** com `autenticado: false` |

Visitante anônimo respondendo 401 faria o `funil` ler "ninguém entrou ainda"
como "a Caixa recusou a minha credencial" — e a primeira coisa que alguém faria
para "consertar" seria afrouxar o token.

**Rota nova nasce fora da varredura de porteiro, e o guarda pegou.**
`path("interno/", api.urls)` é um `URLResolver`, não um `URLPattern`: não tem
`.name` nem `.callback`, e os guardas que varrem o urlconf estouraram
`AttributeError` — três de uma vez. A correção NÃO foi ignorar todo
`URLResolver` (aí bastaria montar páginas por `include()` para a participação
inteira sair da varredura em silêncio): a montagem é **declarada** por
igualdade exata em `MONTAGENS_DE_MAQUINA`, e o mesmo teste **mede o 401** do
lado de fora. Declaração sem prova seria licença para tirar rota do guarda
escrevendo o nome dela numa lista.

### Dívida aberta: a trava do gateway (Lei 1, um degrau acima)

Como o Traefik roteia o prefixo inteiro da Caixa, `…/forms/sugestoes/interno/sessao`
**também resolve pela borda pública**. Hoje quem fecha essa porta é o Bearer
(401 sem token, e o conjunto de tokens nasce vazio) — o que é proteção, mas é
*documento + código*, não *impossibilidade*. A trava de verdade é uma regra de
negação no gateway, e ela mora em `infra/traefik/dynamic/plataforma.yml`, fora
do alcance de um PR de célula (CODEOWNERS). **Fica registrada aqui e não foi
paga neste PR** — quem for mexer em `infra/` a próximo, pague junto.

## O login foi embora — e o que ficou é o que sempre foi desta célula (25/08/2026)

Lei: `docs/decisoes/DECISAO-celula-de-identidade.md`. O Google, o cookie e o
"quem é?" mudaram para a célula `identidade`; a Caixa virou CONSUMIDORA da
resposta completa (`getSessionFull`, com e-mail — degrau `TOKENS_COMPLETOS_*`
do lado de lá). O que ficou aqui, fail-closed como sempre: staff antes de
matrícula, matrícula na `alunos`, recusa explicando com o e-mail na tela.

As três decisões que valem releitura antes de mexer nesta área:

- **A tabela `Identidade` local virou SNAPSHOT casado por e-mail** — as 6 FKs
  de autoria continuam locais e ninguém migrou dado nenhum. Apagar a linha
  local NÃO revoga sessão (ela renasce na visita seguinte); revogação é lá.
- **`/interno/sessao` está DEPRECADO E INERTE**: responde pela sessão legada,
  que ninguém mais assina — sempre `autenticado: false`. NÃO o "conserte"
  ricocheteando para a identidade (`test_inv_sessao_nao_vaza_email` morde).
  Remover a operação é Rito §3 futuro — dívida em ARMADILHAS-OPERACAO §9.
- **Sair da Caixa é sair do site**: o `flush()` apaga `meshcraft_sessao` em
  `Path=/` porque nome e Path dos settings CASAM com os da identidade — par
  guardado em `test_inv_caixa_nao_assina_sessao.py`. E nenhuma página daqui
  pode voltar a ESCREVER esse cookie (sobrescreveria a sessão do site com
  assinatura que só esta célula lê).

Custo por requisição: 1 salto à identidade (cache 60s por cookie) + 1 à
`alunos` (cache 10 min por e-mail, positivo E negativo) — módulo, então os
testes limpam via `ses.limpar_caches()` no `ambiente` (armadilhas/026).
## O EVO-31: a faixa de roadmap e o sino vestido — o que este elo aprendeu

Fecha o Lote 3. Nenhuma regra de negócio nasceu aqui: a faixa é um recorte novo
de dados que já existiam desde o EVO-11, e o sino é o EVO-21 com roupa. As sete
coisas que custaram alguma coisa:

**1. Quem decidiu o escopo da faixa foi um guarda de dois despachos atrás.** A
pergunta "a faixa mostra o quadro inteiro ou só o que o filtro deixou passar?"
tinha resposta boa dos dois lados, e eu tinha escolhido *o quadro inteiro*. O
`test_o_quadro_filtra_por_categoria` (EVO-12b) ficou **vermelho** — porque ele
afirma sobre o CORPO da página, não sobre a grade: quem filtrou por "Blender"
estava recebendo o resto do quadro de volta na parte de baixo da mesma página.
A faixa obedece ao filtro, e a decisão não foi de gosto: foi medida. É a lição
da `armadilhas/087` pelo outro lado — guarda que afirma sobre o corpo
renderizado pega o vazamento que ninguém previu, inclusive o vazamento de
DESENHO.

**2. Nesta célula, classe de CSS é interface de teste.** `.votos` é lida por
regex pelo guarda do botão de voto (`CONTAGEM` em `test_o_rosto.py`), que afirma
`== ["0"]` na grade inteira. Reaproveitar a classe na faixa faria aquele guarda
contar losangos achando que contava votos — verde ou vermelho pelo motivo
errado, os dois igualmente ruins. Daí `.marco-votos`. **Antes de batizar classe
nova numa página que já tem guarda, dê um `grep` pelo nome nos testes.**

**3. A faixa não é rota — é âncora — e isso decide onde mora a proteção dela.**
`{% url 'quadro' %}#roadmap`, seção com `id` dentro do quadro. Consequência que
vale escrever: ela **não entra** em nenhuma das três varreduras de urlconf
(`test_inv_sem_sessao_nada`, `test_inv_so_staff_modera`,
`test_inv_avaliacao_interna_fora_do_alcance`), porque não há `URLPattern` novo.
O porteiro dela é o do quadro, e o guarda de "exige sessão" da faixa mede o
quadro — não uma rota que não existe. Rota própria teria sido uma segunda porta
a proteger para mostrar um recorte do que a primeira já tem em mãos.

**4. O botão do roadmap no trilho NÃO se pinta de `ativo`.** Âncora não muda
`request.resolver_match`, então não há como saber se a pessoa está olhando a
faixa. Pintá-lo por adivinhação (ou pintar os dois) faria o trilho — que
descobre sozinho onde a pessoa está desde o EVO-30 — passar a mentir. E o ícone
é novo (`#i-trilha`): o protótipo reaproveita o `#i-bars` no roadmap, mas aqui
esse desenho já é o da **moderação**, e dois botões idênticos no mesmo trilho é
economia que faz a pessoa clicar no errado.

**5. O guarda de N+1 que não envelhece é a COMPARAÇÃO, não o número.**
`assertNumQueries(9)` na página inteira envelhece a cada mudança e é
"consertado" para o valor novo sem ninguém olhar o motivo. O que não envelhece é
*a mesma página, com mais dados, custa o mesmo*. Duas armadilhas para montá-lo
nesta célula: as duas medições têm de ser da **mesma pessoa** e depois de uma
**leitura de aquecimento** — sessão e matrícula têm cache de módulo com janela
própria (`apps/core/sessao.py`), então um leitor novo entre as medições traz
consultas de estreia e o guarda acusa N+1 onde não há.

**6. O limite de 3 sugestões por 7 dias mora dentro de toda fixture que povoa
quadro.** Uma zona cheia precisa de mais de três ideias; publicá-las pela mesma
pessoa dá **429** na quarta, e o teste morre num lugar que não tem nada a ver
com o que ele mede. A fixture `povoar` de `test_faixa_de_roadmap.py` cunha um
autor novo por ideia. `mesclado`, por sua vez, só entra pelo ORM: ele fica FORA
do `<select>` da moderação desde o EVO-13 e há guarda impedindo que entre por
lá — mas a tela tem de saber desenhá-lo hoje, senão o dia em que o merge nascer
é o dia em que a página quebra.

**7. `nao_planejado` e `mesclado` ficaram na tela, e a aritmética é o guarda.**
Eles não são degraus do caminho, são saídas dele — não têm zona. Mas somem da
existência se ninguém os desenhar, e aí a soma das quatro zonas deixa de dar o
total de sugestões do quadro **sem nada na tela explicando a diferença**, e a
justificativa que a equipe é obrigada a escrever desde o EVO-13 perde a vitrine.
Ficam em "Fora do trilho", logo abaixo da faixa, com o caminho para o detalhe. O
guarda que impede alguém de "limpar" a faixa um dia é
`test_nenhuma_ideia_do_quadro_fica_de_fora_da_conta`: zonas + saídas == quadro.

### E uma de instrumento, que quase virou prova falsa

`git checkout origin/main -- <arquivos>` **também mexe no ÍNDICE**, não só na
árvore. Depois dele, o `git diff` que a `armadilhas/084` manda gerar sai
**VAZIO** — e o patch de prova de 0 bytes aplica ao contrário sem erro nenhum,
sem efeito nenhum. A evidência vermelho→verde teria sido escrita sobre um patch
que não existia. A cura é `git reset` (misto: desfaz o índice, preserva a árvore)
antes do `git diff`, ou `git diff HEAD` direto — e **conferir o tamanho do
patch** (`wc -l`) antes de confiar nele. Isto foi promovido a `armadilhas/108`,
porque é mecânica de git e não desta casa.

## A auditoria do MVP (EVO-41): o que 15 mutações ensinaram sobre esta célula

Este despacho não escreveu comportamento nenhum — foi **auditor**. O relatório
inteiro, com os cinco vereditos e a saída crua de cada mutação, está em
`docs/caixa-de-sugestoes/AUDITORIA-MVP.md`. O que fica aqui é o que serve para
quem for MEXER neste código depois.

**1. Duas das cinco linhas do Definition of Done estavam ERRADAS — o documento,
não o código.** É a lição mais cara deste despacho, e é uma lição de método: um
plano aprovado vira lei para os agentes seguintes, e eles não o questionam.

* A §11 diz *"403 para **qualquer** ator sem role de staff"*. Medido, a célula
  devolve **403 para um** dos três atores sem crachá e **302 para os outros
  dois** — e está certa: o anônimo vai para a porta porque 403 a quem nem
  entrou é um beco, e porque `exige_staff` **empilha** sobre `exige_sessao`, que
  é o que faz as três varreduras de urlconf somarem o urlconf inteiro. Um agente
  futuro que leia a §11 ao pé da letra e "conserte" o 302 quebra
  `test_inv_sem_sessao_nada.py` junto.
* A §11 diz *"evento **publicado antes do commit**"*. Publicar no barramento
  antes do commit é o dual-write que a outbox existe para impedir. O código
  **registra** na outbox dentro da transação e **publica** no `on_commit` — dois
  momentos, e a frase confunde os dois num só.

**Regra que fica: quando a spec e o código discordam, o achado é a divergência,
não o "bug".** Diga qual dos dois está errado e por quê; não conserte o lado
mais fácil de mexer.

**2. A §8 e a §10 da spec se contradizem, e a §11 fica impossível no meio.** A
§8 lista *"merge de sugestão é transacional"* como invariante sem ressalva; a
§10 põe merge em **V1.1**; a §11 exige "todas as invariantes da §8" para o
**MVP**. Não há como cumprir as três. O invariante do merge é o único da §8
**sem guarda nenhum** — e não pode ter, porque a operação não existe. O que
existe no lugar é `test_mesclado_nao_entra_pela_porta_do_status`, que impede
alguém de FINGIR que mesclou; ele reprova quando `MESCLADO` entra na
`STATUS_QUE_A_EQUIPE_ESCOLHE`. Quem for fechar isto de verdade fecha os dois
lados: a operação **e** as quatro promessas da frase da §8.

**3. Escrita idempotente engana o degrau do meio do guarda da
`AvaliacaoInterna`.** A primeira tentativa de provar a metade "nunca é ESCRITA
por endpoint do aluno" usou `get_or_create` sobre a linha que a fixture já tinha
criado: `test_a_jornada_do_aluno_nao_escreve_na_avaliacao` **ficou verde**,
porque ele compara conteúdo antes/depois e nada mudou. Os outros dois degraus (o
SQL e a AST) pegaram — que é para isso que a escada existe. Mas fica o aviso:
**guarda que mede resultado não vê escrita que não muda nada**; para falsificá-lo
é preciso `update_or_create`, não `get_or_create`. Nenhum dos três degraus é
redundante, e quem "simplificar" o arquivo tirando um vai descobrir isso tarde.

**4. O degrau 1 da trava do ChangeSpec é segurado por UM teste só, e a margem é
essa.** Apagar o `raise CorredorAusente` do ponto de estrangulamento deixa a
suíte com **1 failed, 305 passed** — e o único vermelho é
`test_a_recusa_nem_chega_a_travar_a_linha`, que mede SQL (recusar **antes** do
`SELECT … FOR UPDATE`). Todo o resto continua verde porque os degraus 2 e 3
cobrem o buraco e a frase em português continua aparecendo pelo aviso preventivo
da página. O guarda existe, morde e está no lugar certo — o que este número diz
é: **não o apague achando que "os testes de moderação cobrem"**. Não cobrem.

**5. O mesmo vale para a unicidade do voto: 1 vermelho em 306.** Tirar a
`UniqueConstraint` do model **e** da migration deixa só
`test_segundo_voto_do_mesmo_ator_na_mesma_sugestao_e_recusado` vermelho. Os
guardas de endpoint continuam verdes porque o `get_or_create` da
`participacao.py` resolve o caso comum em Python — a constraint do banco é a
rede de baixo, que só aparece na corrida de dois cliques simultâneos, e corrida
não acontece em suíte de teste. **A camada mais importante é a que menos testes
derrubam quando some.**

**6. Mutação em model sem a migration correspondente dá ERROR, não FAIL — e
ERROR é evidência pior.** Acrescentar `Voto.removido_em` só no `models.py` fez
os cinco testes do arquivo saírem como `ERROR: column sugestoes_voto.removido_em
does not exist` (o `db` do pytest-django limpa as tabelas no setup, e o SELECT
cai antes de qualquer asserção). O guarda que a mutação queria falsificar nem
chegou a rodar. Com uma migration descartável junto, a saída vira o vermelho
limpo que serve de prova:
`AssertionError: Voto ganhou campo de desvoto lógico: {'removido_em'}`.
**Prova por mutação exige que a mutação seja um estado COERENTE do sistema** —
senão o que se mede é o ambiente, não o guarda.

**7. Onde o `AUDITORIA-AS-IS.md` envelheceu, e por que isso morde.** Ele é
citado pela spec (§3 e §11) e pelo plano mestre como o retrato do terreno, e o
"maior achado" dele — *"não existe login de usuário final em nenhuma célula"* —
**hoje é falso**: a célula `identidade` nasceu e está no ar. Também envelheceram
a contagem de bancos (7 → 10), a de células (8 → 11) e a proposta de "link
mágico", que o mantenedor descartou na EVO-01. Auditoria é fotografia com data;
o erro não é envelhecer, é envelhecer sem dizer a data. **Não foi corrigido aqui
de propósito** (auditor não conserta, e o arquivo estava fora dos alvos) — está
registrado no item 5 do `AUDITORIA-MVP.md`, com a tarja proposta.

**8. `docs/changespecs/` é PONTEIRO, não cópia.** O plano mestre pedia o
`FORMATO-CHANGESPEC.md` "como lei local" na pasta nova. Copiá-lo seria a
armadilha §5.11 — duas cópias derivam em silêncio, e neste mesmo lote isso já
custou dois PRs num script cujo texto embutido divergiu do molde. O `README.md`
da pasta aponta para onde a lei mora e acrescenta só o que ela não sabia: como
se nomeia o arquivo e quem assina. E **nenhum ChangeSpec real foi escrito**: a
regra de autoria do §1 (quem escreve nunca é quem implementa, `APROVADO_POR` é
sempre o mantenedor) faz de um exemplo assinado por ninguém exatamente a
formalidade vazia que o documento existe para impedir.

## O formulário da fila de liberação — o beco virou destino (27/08/2026)

**Onde:** `apps/core/views.py` (`_tela_da_fila`, `pedir_entrada`),
`apps/core/clients.py` (`AlunosClient.pedir_entrada_na_fila`),
`apps/core/templates/sugestoes/entrar.html`.
**Lei:** `docs/decisoes/DECISAO-fila-de-liberacao.md`. **Provedor:** PR #304.

**O guarda antigo não precisou de UMA linha alterada — e isso foi escolha, não
sorte.** `tests/test_inv_entrada_sem_matricula.py` afirma que a recusa é 403,
que NOMEIA o e-mail, que oferece "Entrar com outra conta Google" e que tem as
três saídas. A primeira versão da tela reescrevia o texto inteiro e derrubava
dois desses guardas; a leitura certa é que **o beco nunca foi o diagnóstico, foi
a falta de destino**. Mantendo "Não encontramos matrícula para esse e-mail" como
título e pondo o formulário logo abaixo, a lei é cumprida e os invariantes
seguem com os dentes que tinham. Afrouxar um teste-guarda para caber uma feature
quase sempre significa que a feature está desenhada errado.

**`request.session` está PROIBIDO nesta célula.** `SESSION_COOKIE_NAME` aqui é
`meshcraft_sessao` — o mesmo cookie que a `identidade` assina para o site
inteiro — e o engine é `signed_cookies`. Uma única escrita reserializa aquele
cookie com uma sessão DESTA célula e **desloga a pessoa da plataforma toda**. A
primeira versão guardava a lembrança do pedido ali; quem pegou foi o teste de
recarregar a página, com a porta respondendo "visitante". Lembrança de tela mora
em cookie próprio (`caixa_pedido_na_fila`), com marca opaca em vez do e-mail.
Classe catalogada em `armadilhas/143`; guarda:
`test_pedir_entrada_nao_reescreve_o_cookie_do_site`.

**O `site_id` é DESCOBERTO, não configurado:** `quadro_atual().site_id`. Uma
variável de ambiente a mais seria um segundo lugar guardando o mesmo fato, e o
dia em que os dois discordassem a pessoa entraria na fila de outro site.

**`pedir_entrada` é rota pública, e isso custou uma declaração.** Ela existe
exatamente para quem NÃO tem sessão de aluno — pôr `@exige_sessao` seria exigir
o crachá para pedir o crachá. Entrou em `PUBLICAS` de
`test_inv_sem_sessao_nada.py` acompanhada da medição de fora que aquele arquivo
exige de toda exceção (`test_a_rota_publica_de_pedido_de_entrada_...`): um
anônimo é devolvido à porta **antes** de qualquer salto para a `alunos`, e quem
prova isso é o `respx` estourando em requisição não registrada.

**A regra das respostas da `alunos`:** 201 e 200 são a mesma notícia para quem
está deste lado (*seu pedido está registrado*) — o reenvio idempotente é
desenho, não erro. 409 vira redirecionamento para a porta: a pessoa TEM
matrícula e o que a barrou foi o cache curto de `_tem_matricula`, que expira
sozinho. Todo o resto — inclusive **422** — fecha com "não foi registrado".
O 422 merece o destaque: como a tela valida antes de mandar, ele significa
desacordo NOSSO com o contrato, e a única coisa inaceitável seria a pessoa sair
achando que está na fila.

**A conferência do WhatsApp é frouxa de propósito** (10 a 15 dígitos): existe
para pegar "não tenho" e dedo escorregado, nunca para recusar um número real
escrito de um jeito inesperado. Um formulário que recusa telefone válido é um
aluno perdido, e o mantenedor confere tudo à mão de qualquer jeito.

## Cache com TTL igual para "sim" e "não" barra quem acabou de ser liberado (28/08/2026)

`_tem_matricula` guardava as duas respostas por **10 minutos**. O mantenedor
liberou a própria conta pelo painel, a pessoa saiu da fila na hora, e a Caixa
continuou recusando — com a tela dela prometendo, com todas as letras, que
*"quando estiver liberado, esta página abre a Caixa"*.

**O número não estava errado quando foi escrito.** Ele nasceu quando a única
forma de virar aluno era COMPRAR: um caminho assíncrono, sem ninguém olhando a
tela. A fila de liberação (27/08) mudou o cenário — passou a existir alguém
esperando na frente do navegador enquanto outra pessoa aperta o botão — e o TTL
não acompanhou. **Toda constante de cache carrega uma suposição sobre quem está
esperando do outro lado; quando o fluxo muda, ela vira dívida silenciosa.**

**A regra que fica: TTL de cache que decide ACESSO é assimétrico.** Os dois
erros têm custos muito diferentes, e tratá-los como iguais é o defeito:

| Resposta velha | Custo | TTL |
|---|---|---|
| "é aluno" (e não é mais) | acesso a mais por alguns minutos — raro, sem urgência | longo (600s) |
| "não é aluno" (e já é) | **pessoa barrada depois de liberada, olhando a tela** | curto (5s) |

**Por que 5s e não 0:** o valor não é para o humano — ninguém percebe cinco
segundos. É para não perder a proteção contra rajada: várias requisições da
mesma pessoa no mesmo instante continuam custando uma consulta só.

**E a tela é metade do conserto.** Ela prometia algo que o cache impedia.
Trocar o texto sem trocar o comportamento seria maquiagem; trocar o
comportamento sem trocar o texto deixaria a tela mentindo para o outro lado. O
guarda `test_a_tela_nao_promete_mais_o_que_nao_acontece` cobra os dois.
## A Mesa (28/08/2026): a primeira tela desta célula que é só uma CONTA

O painel de gestão nasceu aqui — `apps/core/gestao.py`, rota `/gestao`. O
desenho foi escolhido pelo mantenedor entre quatro modelos
(`docs/paineis/painel-da-caixa-de-sugestoes/`, registro `20260828-002` do
livro), e a escolha veio de um número que o próprio desenho produziu: **o degrau
mais lento da travessia é a assinatura** — o robô constrói em dois dias o que
espera semanas por um nome num documento. Daí a forma: uma decisão por vez,
grande, e o resto pequeno e à direita.

Quatro coisas que este elo aprendeu, e que valem para a próxima aba:

**1. A tela nova não precisou de coluna nova — e isso não foi sorte.** Tudo que a
Mesa mostra já existia no banco desde o EVO-11/EVO-13/EVO-40: o estado da
sugestão, a existência (ou não) de `AvaliacaoInterna`, a existência (ou não) de
`ChangeSpecAprovado`, e as datas do `HistoricoStatus`. "Esperando você" não é um
sinalizador que alguém liga: é `planejado` sem ChangeSpec. Quando o corredor é
assinado, o item some da mesa **sozinho** — ninguém o marca como resolvido, e há
guarda para isso (`test_ideia_planejada_com_changespec_sai_da_mesa`). Uma coluna
`pendente=True` teria parecido mais simples no primeiro dia e seria a primeira
coisa a divergir da realidade no segundo.

**2. Duas rotas novas custaram DUAS listas de sanidade — e é assim que se quer.**
`test_inv_so_staff_modera.py` e `test_inv_historico_append_only.py` varrem o
urlconf e cravam a lista esperada à mão. A rota `mesa` entrou nos dois guardas
como VERMELHO antes de entrar como linha — o guarda avisou que existia rota de
equipe nova antes de qualquer pessoa lembrar de contá-la. Quem acrescentar a aba
seguinte vai ver os mesmos dois vermelhos: eles não são atrito, são a lista se
recusando a envelhecer em silêncio.

**3. A mesma definição em dois lugares precisa de um guarda que os case.**
"Quantas pessoas estão atrás desta ideia" existe duas vezes de propósito:
`avisos.interessados_em()` (duas consultas POR sugestão, e devolve o vínculo de
cada um) e `gestao.plateia_de()` (duas consultas para a LISTA inteira, e devolve
só o número). A segunda não podia chamar a primeira num laço — seria N+1 numa
tela de lista —, e duas implementações da mesma definição divergem no primeiro
ajuste que só uma recebe. O que as segura juntas é
`test_a_plateia_da_mesa_e_a_mesma_do_sininho`, que monta a plateia com
sobreposição (quem vota E comenta, e o autor votando na própria ideia) e compara
os dois números. Sem sobreposição o guarda passaria com as duas contas erradas.

**4. Tela de leitura merece um guarda de que ela não escreve.** `test_abrir_a_mesa
_nao_muda_nada_no_banco` tira um retrato de oito contagens, abre a página duas
vezes e compara. Parece exagero para uma view com `@require_GET` — e não é: a
tentação de "aproveitar que a tela já carregou" para criar a avaliação vazia, ou
marcar como vista, é exatamente como um relatório vira, tarde, algo que altera o
que relata.

**Uma ausência deliberada, para ninguém a "consertar":** a planta tem quatro
abas e esta entrega tem uma. As outras aparecem apagadas, escritas como *em
construção*, e não são links. A aba "Os robôs" em particular depende de uma fonte
de dados que **não existe em lugar nenhum** — qual agente está com qual tarefa,
desde quando, em que etapa. Inventá-la por suposição seria o falso-verde do §1 da
`RETROSPECTIVA-FASE-D`; ela espera uma fonte de verdade, não uma tela.

> **Fechado em 29/08/2026:** a espera acabou do jeito certo — a fonte nasceu
> primeiro (a fila de trabalho, `fila/LEIA-ME.md`, fase 2 do plano da lista de
> tarefas), e só então a aba virou link, já na casa nova da gestão
> (`/admin/caixa/robos/`, `services/admin/apps/core/robos.py`). A lição acima
> fica como estava: recusar a tela sem fonte foi o que garantiu que ela
> nascesse cheia, um dia depois — e não vazia, um dia antes.


## A travessia (aba 2): o que a mutação ensinou sobre cenário fraco

A segunda aba do painel (`/gestao/travessia`) põe as ideias em seis colunas. As
colunas **não são os seis status**: dois deles partem em dois, e é a partição que
responde "de quem é a vez" — `em_analise` parte por ter avaliação interna,
`planejado` parte por ter ChangeSpec. A mesma partição que a Mesa usa para
decidir o que sobe, escrita uma vez (`_sem_avaliacao`, `_sem_changespec`) e não
copiada por tela.

**A lição cara deste elo não está no código — está nos testes, e foi a mutação
que a mostrou.** Duas das cinco sabotagens passaram verdes na primeira rodada, e
nas duas o código estava certo e o CENÁRIO estava fraco:

1. **Esvaziar a coluna "No ar" não derrubou o guarda aritmético.** Porque o
   cenário não tinha nenhuma ideia entregue: apagar uma coluna vazia mantém a
   soma batendo. Um guarda de soma só morde se o cenário encher **todas** as
   parcelas — hoje `cenario_das_seis_colunas` põe uma ideia em cada uma, e existe
   um segundo guarda que nomeia qual ideia caiu em qual coluna (a soma sozinha
   bateria com as ideias trocadas de lugar).
2. **Trocar `max` por `min` na escolha do gargalo não derrubou nada.** Porque só
   uma coluna tinha gente: com um elemento, o maior e o menor são o mesmo. O
   cenário passou a ter duas, com esperas diferentes.

A generalização vale para qualquer guarda futuro desta casa: **um teste verde
prova que o código passa no cenário — a mutação prova que o cenário mede alguma
coisa.** Os dois casos acima teriam sobrevivido a uma revisão humana sem
levantar suspeita.

**Um esbarrão que também virou lição: não dá para envelhecer o `HistoricoStatus`
nem num teste, e isso está certo.** A primeira versão do guarda do gargalo tentou
`HistoricoStatus.objects.filter(...).update(criado_em=...)` e levou
`RegistroImutavel` — o append-only morde nos três degraus, inclusive contra o
teste. A saída não é abrir exceção: `colunas_da_travessia` recebe `agora` de fora,
como `sugestoes_ordenadas` já fazia para a aba "Em alta", e o teste move o
relógio em vez de reescrever a história. Para a medição pela PÁGINA — que lê o
relógio de verdade — envelhece-se o `criado_em` de uma ideia que nunca mudou de
fase, que é o único caminho honesto.

**E uma armadilha de fixture que custou duas rodadas:** cenário com mais de três
ideias precisa de mais de um aluno. O freio de 3 sugestões a cada 7 dias é por
PESSOA, e a quarta publicação do mesmo aluno responde **429** — o que é o
comportamento certo. `publicar_por_gente_diferente` existe para isso; escrever
pelo ORM para fugir do freio tiraria da suíte a prova de que a jornada de verdade
alimenta estas colunas.

**A faixa de abas virou `_abas.html`.** Com duas telas desenhando a mesma faixa,
duas cópias envelheceriam separadas; ela descobre sozinha onde a pessoa está por
`request.resolver_match.url_name`, como o trilho da `base_caixa.html`. E o número
na primeira aba sai de `gestao.esperando()` — a MESMA função que a Mesa usa para
montar a lista, nunca uma contagem escrita à parte.


## A aba 3: contar GENTE não é contar tarefas — e o bug que provou isso

`/gestao/esperando` mede o que nenhuma outra tela mede: **o silêncio**. Não o
tempo que a tarefa levou, mas quantos dias uma pessoa que escreveu, votou ou
comentou passou sem ouvir nada. A unidade da tela é a pessoa.

**O bug que este elo produziu, e que o guarda pegou antes do merge:** a primeira
versão de `filas_do_silencio` calculava o silêncio de cada balde isoladamente.
Quem estava atrás de duas ideias em baldes diferentes — uma esperando assinatura
e outra em obra, por exemplo — era contado **duas vezes**, e a soma dos motivos
dava mais gente do que existe. A tela teria mostrado, com toda a confiança, um
número maior que a realidade; e o texto ao lado dela já prometia o contrário
("nunca duas vezes"), o que é a marca do bug que sobrevive à revisão: **o
comentário estava certo e o código não**.

O conserto não foi somar melhor. Foi **fazer a pessoa ter um balde só**, o que
exige partir da mesma travessia que decide o silêncio dela — daí
`noticia_mais_recente()`, que devolve por pessoa o par *(dias, de qual ideia)*, e
da qual `silencio_por_pessoa()` passou a ser derivada. Uma travessia, duas
respostas; duas travessias seriam duas verdades sobre a mesma pergunta.

Três decisões de produto que ficaram escritas no código porque cada uma já foi
tomada errado em algum lugar:

* **Recusada conta como RESPONDIDA.** Um "não vamos fazer" explicado é resposta.
  Tratá-lo como silêncio faria a tela cobrar para sempre uma dívida já paga — e
  ensinaria a equipe a evitar recusar, que é o oposto do que a spec §10 quer.
* **"Nunca ouviram nada" ≠ "ouviram há muito tempo".** São frases diferentes na
  tela. Juntar os dois esconderia o caso pior: a ideia escrita há dois meses que
  nunca mudou de fase, cuja plateia nunca recebeu sequer um "estamos olhando".
* **O silêncio de uma pessoa é o da notícia MAIS RECENTE dela**, nunca o da ideia
  mais parada. Quem votou numa ideia de 40 dias e noutra que andou ontem não está
  há 40 dias sem notícia — e o `min` (com desempate por id, para a ordem do banco
  não decidir nada) é o que diz isso.

**E a armadilha do cenário fraco apareceu pela terceira vez no mesmo dia.** O
guarda da soma dos baldes passou verde com um dos quatro baldes vazio: apagar um
balde vazio do código não muda soma nenhuma. Hoje o teste **cobra que nenhum
balde esteja vazio antes de somar** — e essa asserção é o que faz a mutação
morder. A regra geral, agora escrita em três lugares desta célula: *um guarda de
soma só mede alguma coisa se o cenário encher todas as parcelas.*

O número de avisados na coluna da direita **não é contado à parte**: é a plateia,
que por `[INV-SUG13]` é exatamente quem recebeu o aviso. Uma segunda contagem
seria uma segunda verdade sobre quantas pessoas foram avisadas.


## A gestão saiu de casa: o que o Rito de Contrato de 28/08 ensinou

A gestão das ideias deixou as telas desta célula e foi para `/admin/caixa/`
(lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`). O que ficou
aqui é a superfície de máquina — `apps/core/api_gestao.py` — pela qual o Admin
pergunta e escreve, porque pela Lei 3 ele não pode ler este banco.

**A forma do contrato foi a decisão de projeto mais cara, e ela é de DOMÍNIO.**
`listManagementIdeas` devolve os fatos de cada ideia e **não** as colunas, os
baldes nem a ordem. A tentação de devolver a tela pronta é grande — o consumidor
ficaria com um template burro — e é uma armadilha de manutenção com nome: cada
ajuste de layout viraria mudança de contrato, e mudança de contrato aqui custa
**um Rito, ou seja, uma conversa com o mantenedor**. Com forma de domínio, a tela
do Admin evolui de graça.

A única conta que viaja PRONTA é a plateia, e a exceção tem motivo: ela é
definição desta célula (`[INV-SUG13]`) e é a mesma gente que o sininho avisa.
Recalculá-la do outro lado da fronteira criaria uma segunda verdade sobre quantas
pessoas esperam — exatamente o que o guarda entre `plateia_de` e
`interessados_em` existe para impedir, agora atravessando uma célula.

**As três escritas NÃO reimplementam nada.** Elas chamam
`registrar_mudanca_de_status` e `changespecs.registrar`, os mesmos caminhos que
as telas usavam. É o que mantém de pé, de graça, o histórico na mesma transação,
o leque de avisos, a justificativa obrigatória e o corredor do ChangeSpec nos
três degraus. Uma segunda implementação "só para a API" seria uma segunda porta
para o mesmo cofre — e a que ninguém testa é a que fica aberta.

**O invariante que a mudança de casa revelou, e que ninguém tinha previsto:**
`[INV-SUG12]` exige que quem moderou tenha `id_da_plataforma`, porque a mudança
de status vira carta endereçada. Vindo pela tela, isso era de graça — a porta
gravava o id na entrada. Vindo pelo contrato, o Admin precisa ENVIAR o id
(`por_id_da_plataforma`); ele o tem, é o mesmo `SessionFull.id` com que abriu a
própria porta. A primeira rodada de testes estourou com `AtorSemIdDaPlataforma`
em duas escritas, e o conserto certo não foi afrouxar o invariante: foi
acrescentar o campo ao contrato e **traduzir a falta numa recusa que ensina o
caminho** (422 em português), em vez de deixar chegar ao Admin como erro 500.

**Um guarda que vale copiar:** `test_nenhuma_operacao_responde_sem_o_token_do_par`
deriva a lista de operações da própria `NinjaAPI` e exige 401 em todas. Rota nova
nasce medida, sem depender de alguém lembrar de escrever o guarda dela. E
`test_o_email_do_aluno_nao_atravessa` varre o CORPO INTEIRO em texto, não os
campos que o autor lembrou de conferir — um campo novo que carregue e-mail por
descuido cai ali sem ter sido previsto.

## Porta que responde sim/não não consegue explicar por que não abriu (28/08/2026)

A porta desta célula perguntava **"tem matrícula?"** e recebia um booleano. Com
um `não`, ela mostrava sempre a mesma tela: o formulário de pedir entrada.

Isso esteve **certo por meses** — enquanto só existiam dois mundos (é aluno /
nunca foi). Na manhã de 28/08 nasceram estados novos (pausado, encerrado) e o
booleano continuou dando conta de responder, mas parou de dar conta de
EXPLICAR. O mantenedor apagou um aluno e a pessoa viu *"seu pedido já está com
a gente"* — o recibo de quem está numa fila que ela nunca entrou.

**A lição não é "use enum em vez de bool".** É que **um tipo de retorno é uma
aposta sobre quantas respostas existem**, e a aposta envelhece em silêncio: o
código continua compilando, os testes continuam verdes, e o que quebra é a
frase que a pessoa lê. Quando um domínio ganha estados, todo `bool` que
atravessa aquele domínio vira dívida — e ele não avisa.

**O sinal de alerta, para a próxima vez:** um `if not x:` seguido de UMA tela,
num lugar onde o domínio acabou de ganhar um terceiro caso.

**E a cura tem duas metades, não uma.** Trocar o bool pela categoria conserta o
caso de hoje; o mapa `ESTADO_POR_CATEGORIA` conserta o de amanhã. Sem ele, uma
categoria nova inventada do outro lado cairia no `else` — e o `else` é o
formulário, que é exatamente o defeito de volta com outro nome. O que não está
no mapa FECHA, e há teste para isso.
