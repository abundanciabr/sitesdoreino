# painel/ — o livro de ocorrências e o painel do dono

> Nascido em 26/08/2026 da reforma dos painéis — decisão do mantenedor após 8
> rodadas de consultoria externa (5 IAs), análise completa em
> `docs/paineis/VEREDITO-DAS-CONSULTORIAS.html`. A lei que este diretório impõe:
> **nenhum fato do projeto mora em dois lugares; acontecimento se acrescenta;
> estado se calcula.**

## O que mora aqui

| Arquivo | O que é | Quem mexe |
|---|---|---|
| `painel.template.html` | **A FONTE da porta.** É este que se edita. Ele não tem dados — o gerador injeta o resumo e as regras nele. | Por PR, como código. |
| `painel.html` | **GERADO** por `gerar_manifesto.js`: o template + as regras + o resumo, num arquivo só. Abrir o painel é **UM pedido**. Não guarda dado próprio: tudo é calculado dos registros. **Não mora no Git** desde 28/08/2026 — quem o constrói é a integração. | Só o gerador — e só a integração commita nada disso (ela não commita: constrói). |
| `registros/*.js` | **O livro de ocorrências.** Um arquivo pequeno por acontecimento. Só se ACRESCENTA — nunca se edita nem se apaga um registro existente. | Toda sessão, ao terminar trabalho relevante. |
| `livro-AAAAMM.js` | **GERADO**, um por mês. O conteúdo dos registros daquele mês, buscado só quando você abre a Memória. Mês fechado nunca mais é reescrito. **Não mora no Git** desde 28/08/2026. | Só o gerador. Nunca à mão. |
| `logica.js` | As regras que calculam as vistas (caixa de entrada, frescor, capa). Pura, roda em Node e no navegador. | Por PR, com teste-guarda. |
| `abrir-o-painel.cmd` | **Dois cliques** para ver o painel nesta máquina: monta os artefatos a partir do livro e abre a página. Fail-closed — sem Node, ele manda você para o painel do site em vez de abrir algo velho. | Por PR. |
| `gerar_manifesto.js` | Valida TODOS os registros (fail-closed, com a MESMA `logica.js` da página) e monta `painel.html` + os meses. `--conferir` só confere (para CI). O nome ficou do tempo em que ele só escrevia um manifesto. | Por PR. |
| `testes/` | Testes-guarda da lógica e do gerador — incluindo os casos em que devem REPROVAR. | Por PR. |
| `../ci/verificar_painel.py` | **O verificador de FORA.** Confere os gerados contra o índice do Git (`git ls-files`), em Python, sem reusar uma linha do gerador. É ele que pega o que o `--conferir` não tem como pegar: um bug do próprio gerador. Roda na muralha. | Por PR. |
| `ia/` | **Mapa técnico do projeto para IA** (`ia/INDICE.md` é a porta) — infraestrutura, arquitetura de células, CI/CD, decisões de produto, escrito para uma IA sem contexto prévio auditar o sistema e sugerir melhorias. Segue a mesma lei deste diretório: não guarda veredito próprio sobre o estado do projeto, só mapeia mecanismo — quem quiser saber "o que está pendente" continua lendo `registros/`, nunca `ia/`. | Por PR, junto com a mudança que descreve. |

## Como registrar um acontecimento (o gesto de toda sessão)

0. **O caminho é `make pr`, e ele faz o rito inteiro (desde 06/09/2026).**
   Commit, push, PR aberto, número pedido ao almoxarife, registro gerado com os
   11 campos que saem do próprio PR, gerador do painel, e o recibo embarcado num
   segundo commit no MESMO ramo. Um comando:

   ```bash
   make pr TITULO="ci: o que muda, para leigo" MENSAGEM=mensagem.txt \
           CORPO=corpo.md ARQUIVOS="ci/pr.py ci/tests/test_pr.py" DETALHE=detalhe.txt
   ```

   Ele **recusa** com `detalhe` de menos de 80 caracteres: os 11 campos
   derivados a máquina preenche, mas a única frase que o mantenedor lê é
   julgamento de quem fez o trabalho. Falhou no meio? `CONTINUAR=1` relê o
   estado (commit feito? PR aberto? recibo a bordo?) e pula o que já está
   pronto. Ele **não arma espera nem pouso**: devolve o número do PR, e quem
   arma é a maestro (`armadilhas/364`). Contrato completo: `python ci/pr.py --help`.

   **A ordem do rito, desde 31/08/2026: o PR PRIMEIRO, o registro depois — e no
   MESMO ramo.** É por isso que o `make pr` existe: o registro de uma entrega só
   pode citar o número do PR depois que o `gh` o devolve (`armadilhas/185`). O
   portão do pouso confere o embarque e recusa PR de entrega sem o próprio
   recibo a bordo (`ci/mergear.py`); PR que só escritura (`painel/` e/ou
   `fila/`) é isento. Registro de fato pós-merge (veredito de deploy, incidente)
   continua sendo PR próprio, só de livro.
1. **À mão, quando o `make pr` não serve** (registro pós-merge, resposta a um
   pedido, correção de rumo): crie **um arquivo novo** em `registros/`, nome
   `AAAAMMDD-NNN-slug.js`. O `NNN` **se pede ao almoxarife — não se escolhe:**

   ```bash
   git fetch origin
   N=$(python ci/reservar.py numero registro)
   DIA=$(python -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'))")
   # arquivo: painel/registros/$DIA-$N-slug.js  (e o campo `arquivo:` idêntico)
   ```

   `ci/reservar.py` cria uma referência no servidor do GitHub — comparar-e-trocar,
   a mesma trava que impede dois `push` simultâneos de se atropelarem. Duas
   sessões no mesmo segundo: uma ganha, a outra é recusada **pelo servidor** e
   recebe o próximo número. Escolher à mão não tem trava nenhuma — as duas leem
   a pasta, as duas veem o mesmo livre, e o Git junta os dois arquivos sem ter o
   que reclamar (nomes diferentes, hunks diferentes). Medido em 29/08/2026: 82
   números gastos no livro, só 39 pedidos ao almoxarife, três colisões no dia.
   **Pelo `make pr` esse pedido acontece sozinho**, no passo 6, e nunca duas
   vezes: era chamado duas vezes na mesma sessão antes de ele existir.
   O `DIA` sai em **UTC de propósito** (`armadilhas/158`); o fallback para
   quando não houver rede está em `armadilhas/179`.

   **Nunca edite um registro existente** — atualização é um registro NOVO
   (se ele fecha um pedido, aponte `responde_a`).
2. Conteúdo — exatamente este molde (copie de um registro existente):

```js
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-001-exemplo",      // = nome do arquivo sem .js (o gerador confere)
  tipo: "entrega",                      // decisao | pendencia | resposta | entrega | incidente | medicao | frente | rumo | nota
  quando: "2026-08-26",                 // quando o FATO aconteceu (não quando você escreveu)
  titulo: "Uma linha, para leigo, sem sigla",
  detalhe: "Texto simples, sem HTML. Parágrafos separados por \\n\\n.",
  autoridade: "github",                 // quem tem o DIREITO de declarar isto: mantenedor | github | sonda | rito | sessao
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/999",  // ou null
  verificado_em: "2026-08-26",          // quando a EVIDÊNCIA foi conferida — ou null (vira "não comprovado")
  precisa_do_dono: false,               // true = entra na caixa de entrada até existir resposta
  responde_a: null,                     // arquivo de outro registro que este fecha — ou null
  gravidade: "info",                    // vermelho | ambar | info | verde
  frente: null,                         // etiqueta do capítulo do "Meu mapa": site | comunidade | curso | vender | fabrica
                                        // (obrigatória em "frente" e em "rumo"; opcional e recomendada no resto)
  vence_em_dias: null,                  // depois de N dias sem registro novo, isto conta como velho — ou null (não vence)

  // OS QUATRO DA DECISÃO — só fazem sentido com `precisa_do_dono: true`, e são
  // OPCIONAIS. Sem eles a ficha na tela diz "não sei", que é honesto e cobra
  // quem escreveu o pedido. Com eles, o dono decide sem reconstruir o contexto.
  se_eu_nao_decidir: null,              // o que acontece se isto ficar parado — ou null
  recomendacao: null,                   // o que você sugere, e por quê — ou null
  reversivel: null,                     // true/false SEM aspas ("false" seria verdadeiro em JS) — ou null
  impacto: null                         // alto | medio | baixo — ou null
});})();
```

3. Rode `node painel/gerar_manifesto.js` (da raiz). Ele valida tudo e monta
   `painel.html` e o arquivo do mês **na sua máquina**. **Se ele reprovar, o
   registro está errado — conserte; não contorne.**
4. Confira abrindo `painel/painel.html` (ou dois cliques em
   `painel/abrir-o-painel.cmd`; ou o teste: `node painel/testes/teste_logica.js`).
5. **Commite só o registro.** Os dois arquivos gerados estão no `.gitignore`
   desde 28/08/2026 e **não viajam no PR** — quem os constrói é a integração.
   Se você tentar forçá-los para dentro do commit, `.githooks/pre-commit` barra;
   se passar, `ci/verificar_painel.py` reprova na muralha.

## As regras que a lógica impõe (não são convenção — são código com teste)

- **Caixa de entrada calculada:** pendência = registro `precisa_do_dono: true`
  sem nenhum outro registro com `responde_a` apontando para ele. Uma lista
  calculada não consegue esquecer um pedido.
- **Verde é conquistado:** `gravidade: "verde"` exige `evidencia` E
  `verificado_em`. Sem prova conferida, o gerador reprova. Relato sem evidência
  aparece como "não comprovado", nunca como verde.
- **Número do dia é único — a trava é mecânica, não combinado:** duas sessões
  podem ler a pasta no mesmo minuto e escolher o mesmo `NNN` — aconteceu de
  verdade em 26/08/2026, quatro vezes num único dia (registro
  `20260826-041-o-livro-passou-a-recusar-numero-repetido`). `validarRegistros`
  (`painel/logica.js`) reprova (FAIL) qualquer `AAAAMMDD-NNN` usado por mais de
  um registro — a mesma família de trava que `ci/indice_de_armadilhas.py` já
  tem para `armadilhas/` (`armadilhas/085`), rodando em todo PR pela
  `muralhas`. Colidiu? A mensagem de erro já traz o próximo número livre:
  renomeie o arquivo E o campo `arquivo` (os dois têm de bater) e rode
  `node painel/gerar_manifesto.js` de novo. As duas colisões de 26/08 ficam
  congeladas de propósito (registro mergeado não se edita); um terceiro
  registro *nesses* números, porém, ainda reprova — a tolerância guarda o
  tamanho do par herdado, não uma licença permanente.
- **Pedido chega decidível, ou diz que não sabe:** a caixa "Precisa de você"
  mostra, para cada pedido, o que acontece se ele ficar parado, a recomendação,
  se dá para voltar atrás e o peso. Campo ausente aparece como "não sei" —
  nunca some da tela, porque sumir faria um pedido incompleto parecer completo.
  A ordem continua sendo por IDADE (pedido velho grita mais); o peso é para você
  ver, não para reordenar a fila pelas suas costas.
- **O tanque à vista:** a aba Operação mostra quanto o painel já ocupa dos tetos
  (página e resumo), em barra e em porcentagem. O teto sozinho só se manifesta no
  dia em que o gerador se recusa a construir — e aí o dono descobre pelo tranco.
  A página carimba o próprio tamanho com um marcador de largura FIXA, trocado
  depois de medir: largura variável faria a página declarar um tamanho que não
  tem, e a barra mentiria sobre o teto que a protege.
- **A quinta pergunta — "posso confiar nisto?":** a aba Operação conta quantas
  afirmações do painel têm prova conferida, e NOMEIA as que não têm. Mais o
  placar de promessa × entrega (rumos cumpridos, e em quantos dias). Ele mede a
  FONTE, não o projeto — e continua funcionando mesmo se todo o resto estiver
  mentindo. Pontua calibração, nunca ambição: premiar rumo cumprido rápido
  ensinaria a prometer menos.
- **Quem está mexendo em quê agora:** sai dos PRs abertos que a página já busca
  — zero pedido a mais. Os ramos são `agent/<área>/<tarefa>`, e é a área que
  responde "em quê". Ramo fora do padrão é dito como tal, nunca adivinhado.
- **Dois relógios:** `quando` (o fato) ≠ `verificado_em` (a prova). A página
  mostra os dois; o segundo é o que importa.
- **Frescor computado:** a página compara as datas com o relógio dela ao abrir.
  Seção velha se desbota sozinha e diz há quantos dias. Ninguém escreve "atualizado".
- **Teto da capa:** a capa recusa construir com mais blocos que o teto — em vez
  de crescer, ela quebra visivelmente e diz o que precisa sair. O mesmo vale para
  o TAMANHO: se o resumo passar do orçamento, o gerador se recusa a construir.
- **Quem confere não é quem constrói:** o `--conferir` do gerador compara a saída
  dele com a recomputação dele — cego para um bug do próprio gerador. Por isso
  existe `ci/verificar_painel.py`, em Python, partindo de `git ls-files` e
  comparando CONJUNTOS de ids em vez de contagens. Cardinalidade não é
  integridade: `A B C C` passa por `A B C D` numa contagem, e não passa por ele.
- **A página depõe sobre si mesma:** quando algo falha, a tela nomeia a CLASSE
  (A não montou · B resumo vazio · C capa não calculou · D mês não chegou ·
  E mês incompleto · F gerações diferentes), descobre sozinha se foi aberta por
  `file://` ou pelo site, e entrega um bloco copiável para colar numa sessão.
  Ninguém entra no servidor e ninguém vê o navegador do dono — então o sistema
  produz a própria evidência.
- **Falha de um mês NÃO apaga a capa:** a faixa vermelha fica sobre a seção
  afetada, barulhenta e local. A capa veio embutida nesta mesma página e não
  depende do histórico. Apagar tudo seria o painel mentindo na outra direção.
- **O carimbo da geração** viaja na página e em cada mês. Se diferirem, os
  arquivos são de gerações diferentes — quase sempre OneDrive sincronizando
  pela metade — e a tela diz isso, em vez de acusar registro faltando.
- **ESCRITOR ÚNICO (desde 28/08/2026 — Onda 3):** a fonte é multiescritor
  (`registros/`: arquivo novo por ocorrência, imune a conflito por construção);
  a MATERIALIZAÇÃO tem um escritor só (a integração: a muralha em todo PR, o
  deploy antes de montar a imagem da `admin`); e quem confere é um terceiro
  independente (`ci/verificar_painel.py`, em Python, partindo de `git ls-files`).
  Nenhum robô commita arquivo gerado — `.gitignore` os mantém fora,
  `.githooks/pre-commit` barra o `git add -f`, e o verificador reprova o PR se
  um deles voltar ao índice. **O motivo é medido, não estético:** enquanto eles
  viajavam no Git, todo PR que registrasse qualquer coisa reescrevia os dois
  arquivos inteiros — dois robôs no mesmo dia colidiam sem ter escrito uma linha
  em comum, e um PR de 4 arquivos levou OITO tentativas para entrar
  (`armadilhas/156`). A lei vale para o que vier: índice, catálogo, resumo —
  fonte que muitos escrevem, materialização que um só escreve, prova por fora.
- **Duas provas diferentes, porque medem coisas diferentes:** a muralha constrói
  e reconstrói (byte a byte: o build é reprodutível) E roda o verificador
  semântico (o conjunto de ids do Git chegou inteiro à tela). Uma não cobre a
  outra: um gerador que pule registros produz os dois lados errados do mesmo
  jeito, e um build não determinístico passaria na comparação de conjuntos.
- **Conflito em arquivo gerado não se resolve à mão:** `painel.html` e
  `livro-*.js` estão marcados com `-merge` no `.gitattributes`, então o Git para
  em vez de produzir uma junção plausível e errada. Apague, rode o gerador,
  `git add`.
- **Autoridade:** cada tipo de fato tem quem pode declará-lo. Painel nenhum é
  origem de fato — todo painel é espelho.
- **O mapa não inventa futuro:** a vista "Meu mapa" mostra os cinco capítulos
  sempre, cada um com o rumo registrado daquela frente. Frente sem `rumo` diz
  *"não sei para onde esta frente vai"* — nunca uma tela vazia, que se leria
  como "nada planejado". E **`rumo` nunca é verde**: verde é prova conferida, e
  o futuro não se prova. Quando um rumo vira realidade, quem o fecha é um
  registro novo com `responde_a` apontando para ele — a mesma mecânica da caixa.

## O que NÃO fazer

- ❌ Editar um registro existente (nem "só para corrigir um typo" — registro
  novo com `responde_a`).
- ❌ Editar `painel.html` ou `livro-AAAAMM.js` à mão (os dois são gerados —
  mexa em `painel.template.html` e em `painel/registros/`).
- ❌ Commitar `painel.html` ou `livro-AAAAMM.js` (nem com `git add -f`). Eles são
  materializados pela integração desde 28/08/2026; commitá-los devolve a colisão
  diária entre robôs, que é o problema que a Onda 3 fechou.
- ❌ Resolver conflito de Git num arquivo gerado editando o arquivo. Apague,
  rode o gerador, `git add`. A pasta de registros é a verdade; o gerado é sombra.
- ❌ Fazer o custo de ABRIR o painel crescer com o tamanho do livro. Até 27/08/2026 a página pedia um arquivo por registro, e a rajada de dezenas de pedidos batia na porta da área administrativa até parte deles voltar como erro — o painel se recusava a abrir, com número diferente a cada vez, quatro vezes num dia. Hoje abrir é **um pedido**, sempre (guardas: `teste_gerador.js` mede com 1, 100 e 1.000 registros; `test_painel_vivo.py::test_o_livro_chega_em_UM_pedido_e_nao_um_por_registro` mede pelo servidor real).
- ❌ Pôr no resumo qualquer conta que dependa do relógio. Idade de pedido, vencimento e "o que mudou em 7 dias" são contados NO NAVEGADOR, ao abrir. Congelá-los no build fossilizaria o frescor — a doença que este painel existe para não ter.
- ❌ Escrever HTML dentro de `titulo`/`detalhe` (a página insere como texto).
- ❌ Criar lista/estado em qualquer outro lugar e "sincronizar depois" — é
  exatamente a doença que este diretório existe para curar.
