# painel/ia — 02. Armadilhas e Padrões Recorrentes

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Este documento é um
> **resumo curado** — a fonte de verdade é `armadilhas/INDICE.md` (gerado,
> nunca editado à mão) e os ~126 arquivos individuais em `armadilhas/`. Este
> texto existe para dar TAXONOMIA e CONTEXTO; para o sintoma exato que você
> está vendo agora, vá direto ao índice e dê Ctrl+F — não leia esta página
> como substituto disso.

## Por que isto importa para quem for sugerir melhorias

Antes de propor uma mudança arquitetural, vale saber que este projeto já
tentou e já sofreu com uma quantidade grande de armadilhas específicas — boa
parte delas não é "falta de cuidado", é a cicatriz de um incidente real, com
teste-guarda escrito depois. Uma sugestão que reintroduz uma dessas
armadilhas (ex.: "simplifique o CI para retornar só PASS/FAIL") provavelmente
já foi tentada e revertida por um motivo documentado.

## Os 8 padrões (o "andar de cima" — leia isto, não o catálogo inteiro)

Vêm de `docs/decisoes/RETROSPECTIVA-FASE-D.md`, escrito depois de uma sessão
repetir duas falhas já catalogadas em 48 horas — a lição meta do documento é
que **conhecer o caso não impede repetir a classe**; só a categoria cura.

1. **Falso-verde é o modo de falha nº1.** "Não consegui medir" nunca pode
   virar "passou" ([INV-CI01]). Casos reais: freeze de contrato "OK" com
   `python3` quebrado; anos de green histórico do deploy que na verdade nunca
   provaram deploy real (o script terminava em `docker compose ps`, que sai 0
   mesmo com o container vazio); veredito lido de `| tail`; `make ci` verde
   com o contrato apagado. Consequência mecânica: todo portão devolve 4
   estados (PASS/FAIL/ERROR/SKIP), nunca 2; veredito sempre de fonte
   estruturada (`gh run view --json`, nunca de um pipe).
2. **Garantia declarada sem mecanismo apodrece.** Uma promessa escrita em
   prosa ("isso roda no CI a cada PR") sem portão que a imponha e teste-guarda
   que reprove a violação, eventualmente para de ser verdade e ninguém
   percebe. Se não dá para mecanizar agora, o documento deve dizer que não
   está imposta — não fingir que está.
3. **A prova vem de fora, não de dentro.** Meça do lado do usuário, pela
   borda pública (ex.: um drill de rollback que mede `200→404→200` visível
   da internet, não "o container reiniciou" visto de dentro).
4. **Nas bordas externas, fail-closed — 2xx não é sucesso.** O corpo da
   resposta precisa descrever o que foi pedido; nada que decide dinheiro
   confia em dado não assinado. Bug mais caro da Fase D: um cliente de
   pagamento traduzia corpo de erro em `201 Created` com QR vazio.
5. **O gargalo era humano — mecanizá-lo foi a maior alavanca.** Medido:
   mediana 22min / média 264min por merge esperando o mantenedor. A pergunta
   que vale fazer sobre qualquer passo manual: "isso pode virar pipeline?"
6. **Contexto é orçamento — decide arquitetura antes do código.** Isto é
   literalmente por que este documento que você está lendo foi fatiado em
   vários arquivos em vez de um monólito, e por que o orçamento de 15
   arquivos por PR existe.
7. **Sessões paralelas: arquivo novo, nunca fim de arquivo compartilhado.**
   Regra prática: antes de editar um artefato compartilhado, `git fetch` e
   confira; se a documentação descreve um estado que o repositório não tem,
   é sinal de trabalho paralelo em voo, não de doc desatualizado.
8. **Não afirme viabilidade sem ler a configuração real.** Uma sessão já
   disse ao mantenedor que algo estava "quase pronto" sem ter lido o
   roteamento do Traefik — a peça central nem era acessível pela internet.
   Viabilidade exige ler config real (roteamento, permissões, secrets,
   workflow), nunca inferir só do código de aplicação.

## Taxonomia do catálogo (~126 entradas em `armadilhas/`, por tema aproximado)

| Tema | ~Qtd | Faixa de números de exemplo |
|---|---|---|
| Portões de CI / falso-verde / orçamento de PR / muralhas | ~17 | 034–041, 045, 096, 105, 107, 110, 113, 123, 124, 133 |
| Traefik / roteamento sob `SCRIPT_NAME` / deploy em produção | ~14 | 016–018, 029, 073, 081, 083, 086, 089, 091, 102, 103, 111, 127 |
| Django ORM / django-ninja / templates | ~14 | 020–023, 033, 057, 079, 080, 087, 099, 115, 116, 120, 121 |
| Git / worktree / lote paralelo / evidência vermelho→verde | ~13 | 052, 053, 067–069, 084, 085, 092, 094, 101, 108, 135, 136 |
| GitHub Actions / pipeline de deploy / YAML / segredos | ~12 | 047–051, 090, 112, 114, 125, 126, 130, 134 |
| Testes / mocks (`respx`, `patch`) / mypy / qualidade de guarda | ~10 | 054–056, 058–061, 129, 131, 132 |
| Ambiente Windows / terminal / encoding / CRLF | ~10 | 003, 006, 007, 010, 012, 014, 019, 093, 122, 136 |
| Docker / containers locais | ~6 | 004, 008, 009, 011, 013, 015 |
| Gênese de célula nova / cadastro de site | ~5 | 022, 032, 076, 077, 088 |
| Documentação/auditoria obsoleta / referência que mente | ~4 | 072, 100, 104, 109 |
| Middleware (subconjunto do cluster Traefik/`SCRIPT_NAME`) | ~3 | 024, 025, 026 |
| Painel (JS, geração de manifesto) | ~3 | 095, 117, 128 |
| Provedor externo / pagamentos / fail-open na borda | ~3 | 028, 031, 097 |
| Scripting diverso (heredoc, mtime, script injetado) | ~3 | 070, 074, 078 |
| Workers/Huey | ~2 | 030, 071 |
| i18n/locale | ~2 | 089, 098 |
| Performance | ~1 | 082 |

Há sobreposição deliberada entre temas (uma entrada de `SCRIPT_NAME` é ao
mesmo tempo "Django" e "Traefik"). Os três maiores clusters — CI/falso-verde,
Traefik/roteamento/deploy, e Django/ninja — somam quase um terço do catálogo:
este projeto sofreu mais com "o portão mentiu" e "a rota sob prefixo se
comportou diferente em produção" do que com bugs de lógica de negócio pura.
Isso é, em si, um dado útil para quem for procurar onde uma revisão de
arquitetura rende mais.

## 20 armadilhas mais úteis para uma IA nova conhecer (arquiteturais, não ultra-específicas)

1. **003** `UnicodeEncodeError`/acento virando lixo no terminal Windows (cp1252) — raiz do cuidado com saída em todo script de CI.
2. **024** Middleware intercepta `/healthz` e derruba a sonda de saúde.
3. **025** Middleware roda antes da autenticação do django-ninja — teste espera 401, recebe 404.
4. **028** Cliente de provedor externo que só levanta exceção em 5xx falha **aberto**: 2xx com campos vazios passa como sucesso.
5. **029** `/healthz` 200 em dev e 404/500 em produção por `SCRIPT_NAME` + Django 5.0 — o "funciona na minha máquina" mais citado do projeto.
6. **031** Marcar evento como processado antes de aplicar o efeito descarta reentrega em silêncio.
7. **035/036** Os dois portões que decidem a divisão do trabalho antes da primeira linha de código: orçamento de 15 arquivos por PR e "uma célula por PR".
8. **040** Portão de CI verde porque não conseguiu medir (o padrão 1, em forma de caso).
9. **041** Freeze de contrato passa verde com mudança de API pública real.
10. **045 / 123 / 124** Família "o exit é do último comando do pipe": `gh run watch | tail` reporta verde com o run falho; `&&` obedece ao `tail`, não ao portão; `codigo=$?` depois de `if ! cmd` é sempre 0.
11. **053 / 068 / 135** Família de colisão em lote paralelo (stash de outro agente, outra sessão escrevendo no seu worktree, ramo trocado no clone principal) — motivo direto da regra "clone principal é espelho" deste projeto.
12. **082** Construir um `SSLContext` novo por chamada HTTP em vez de reusar cliente — 0,4s por chamada, sem nenhum teste "lento" para acusar.
13. **083 / 102 / 103** Trio de `SCRIPT_NAME`: `/static/**` 404 em produção, template manda para a célula errada, e uma API "interna" responde pela internet pública (achado de segurança, não só bug).
14. **097** Cliente que lê variável de ambiente no `__init__` — `KeyError` vira HTTP 500 em toda página, com deploy verde.
15. **104** Teste-guarda que checa NOMES em vez de COMPORTAMENTO — fica vermelho quando um nome some e verde quando a coisa em si quebra.
16. **107** GNU Make devolve exit 2 (não 1) quando a receita reprova — quem assume "1=FAIL" lê reprovação real como "não consegui medir".
17. **113** Portão de merge reprova um check que a tela do GitHub mostra verde — dois runs do mesmo workflow no mesmo commit.
18. **126** Ligar proteção nativa de branch trava todo merge para sempre num repo de um colaborador só ("Review required" sem ninguém que possa revisar).
19. **136** (a mais recente) Crase dentro de `git commit -m "…"` executa comando, corrompe a mensagem e cria arquivo-lixo.
20. **090** Segredo em argumento de linha de comando vaza por 4 caminhos (histórico do shell, `ps`, logs...) — relevante para qualquer bloco de colar que gere comando.

## `ARMADILHAS-OPERACAO.md` — o que é hoje (mudou em 26/08/2026)

Não é mais lista de pendências — isso é papel do painel calculado
(ver [03 — sistema do painel](03-sistema-do-painel-e-livro.md)). O que sobrou:

- **§1** — histórico narrado dos atritos H1–H22 (maioria já resolvida, com a
  história de como) + instruções técnicas reutilizáveis de passos manuais
  (scripts idempotentes fail-closed para colar na VPS). Um teste-guarda
  (`ci/tests/test_uma_casa_para_o_precisa_de_voce.py`) reprova se alguém
  acrescentar linha nova aqui ou devolver marcador 🔴/🟡 — a mudança nasceu
  de um incidente real: até 26/08 esta tabela era uma segunda lista mantida
  à mão, e já **discordava** do painel calculado (7 itens "abertos" aqui
  contra 6 no painel).
- **§5** — só as 2 entradas operacionais sobre portões mecânicos que restaram
  (distinção LOCAL VERIFIED / CANONICAL CI / MERGE PROTECTED; como mergear
  via `ci/mergear.py`, nunca pelo botão do site).
- **§7** — 4 entradas sobre coordenação entre sessões: múltiplas IAs no mesmo
  repo, o gesto de 3 passos para registrar no painel, despacho colado no chat
  podendo divergir do card do painel, e "registrar é parte de terminar a
  tarefa".
- **§9** — pendências conhecidas que não são armadilhas (dívida, não bug):
  referências obsoletas a `ARMADILHAS.md §1/§9` espalhadas em `services/`,
  3 buracos de cobertura de teste na célula de pagamentos, guardas sem
  invariante declarado (rastreados em `ci/guardas-nao-declarados.txt`).

## `docs/historico/RESOLVIDAS.md`

Guarda armadilhas já resolvidas **de vez**, fora da dieta de leitura de
despacho normal desde 23/08/2026. Filosofia: "resolvido não é apagado" — o
"era assim" evita que a mesma correção seja refeita do zero, e cada título
preserva o número antigo do monólito para que citações velhas (`ARMADILHAS
§5.9.1`) continuem resolvendo. Só consultar quando precisar do histórico de
um item específico.

## Como o índice é gerado (`ci/indice_de_armadilhas.py`)

O índice é **gerado, nunca editado à mão**. Comandos: sem flag regenera,
`--conferir` só confere (é o que roda em CI). Contrato mínimo de uma entrada:
título em `# `, opcionalmente um parágrafo `**Sintoma:** ...` (é o que faz o
Ctrl+F funcionar). A tabela final é sempre plana e em ordem alfabética de
nome de arquivo — agrupar por categoria exigiria uma declaração manual que
uma sessão futura esqueceria de manter.

**A numeração `NNN` é portão mecânico, não combinado.** Já aconteceu de duas
sessões em paralelo escolherem o mesmo número para arquivos diferentes, e o
`git rebase` uniu os dois sem conflito de texto (nomes e hunks diferentes) —
só um `ls` manual detectou. Por isso hoje número repetido é **ERROR**, nunca
um índice silenciosamente "bonito". Regra complementar: nunca reaproveitar um
número vago do meio de uma sequência — os buracos que você vê no índice real
(alguns números "aposentados") são intencionais, porque referências antigas
ainda citam esses números.

## Nota de segurança

Uma pesquisa completa destes documentos não encontrou nenhuma credencial real
exposta — o único token de Mercado Pago citado em `ARMADILHAS.md` é um
placeholder de teste explicitamente documentado como "nunca em produção".
**Um endereço IP real da VPS aparece em `ARMADILHAS-OPERACAO.md` (entrada
H15)** — deliberadamente **omitido** deste documento e de todo o mapa em
`painel/ia/`, porque este conjunto foi escrito para poder ser lido por IAs
sem acesso privilegiado ao projeto. Se você é uma sessão com acesso normal ao
repositório e precisa do IP real por um motivo operacional legítimo, ele está
no arquivo original — não neste mapa.
