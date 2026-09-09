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
| `areas.json` | **As seis áreas do site nas palavras do dono**, e que nomes de célula e de ramo pertencem a cada uma. Um lugar só: a aba Prioridades, a rota `fila.json` da área administrativa e o portão do pouso leem daqui. A ordem da lista é a ordem da tela; uma célula pertence a UMA área (o gerador reprova se aparecer em duas). | Por PR, com teste-guarda. |
| `logica.js` | As regras que calculam as vistas (caixa de entrada, frescor, capa). Pura, roda em Node e no navegador. | Por PR, com teste-guarda. |
| `abrir-o-painel.cmd` | **Dois cliques** para ver o painel nesta máquina: monta os artefatos a partir do livro e abre a página. Fail-closed — sem Node, ele manda você para o painel do site em vez de abrir algo velho. | Por PR. |
| `gerar_manifesto.js` | Valida TODOS os registros (fail-closed, com a MESMA `logica.js` da página) e monta `painel.html` + os meses. `--conferir` só confere (para CI). O nome ficou do tempo em que ele só escrevia um manifesto. | Por PR. |
| `testes/` | Testes-guarda da lógica e do gerador — incluindo os casos em que devem REPROVAR. | Por PR. |
| `../ci/verificar_painel.py` | **O verificador de FORA.** Confere os gerados contra o índice do Git (`git ls-files`), em Python, sem reusar uma linha do gerador. É ele que pega o que o `--conferir` não tem como pegar: um bug do próprio gerador. Roda na muralha. | Por PR. |
| `ia/` | **Mapa técnico do projeto para IA** (`ia/INDICE.md` é a porta) — infraestrutura, arquitetura de células, CI/CD, decisões de produto, escrito para uma IA sem contexto prévio auditar o sistema e sugerir melhorias. Segue a mesma lei deste diretório: não guarda veredito próprio sobre o estado do projeto, só mapeia mecanismo — quem quiser saber "o que está pendente" continua lendo `registros/`, nunca `ia/`. | Por PR, junto com a mudança que descreve. |

## Como registrar um acontecimento (o gesto de toda sessão)

0. **O caminho é `make pr`, continuando a implementação do PR #1216.**
   Declare em `validacao.json` os comandos de validação aplicáveis como listas
   de argumentos. O comando os executa sem shell, antes do push, numa
   bancada temporária isolada do commit entregue. Arquivos locais sem commit
   e arquivos ignorados da bancada de trabalho não entram nessa validação.
   Os argumentos usam caminhos relativos; apenas o executável pode ter
   caminho absoluto:

   ```json
   {"comandos": [["python", "-m", "pytest", "ci/tests", "-q"]]}
   ```

   Cada comando tem prazo padrão de **900 segundos**, também na prova do SHA
   final. Esse limite finito comporta a suíte ampla medida em 377,78 segundos,
   com margem para variação do ambiente. Para ajustar, acrescente ao mesmo
   JSON `"prazo_segundos": 1800`. O valor explícito vence o padrão; não há
   outra fonte de configuração. Aceita somente inteiro de **1 a 7200 segundos**
   (teto de duas horas por comando). Zero, negativos, decimais, strings,
   booleanos, null e valores não finitos são recusados antes de gravar.
   O prazo vale separadamente para cada comando, não para o fechamento inteiro;
   comandos operacionais de Git e GitHub continuam com limite de 300 segundos.

   O log distingue `PASS` (exit zero), `FAIL` (exit não zero), `TIMEOUT`
   (prazo excedido) e `ERROR` (instrumento ou encerramento indisponível),
   preservando stdout e stderr sanitizados, prazo e horários UTC. Ao exceder
   o prazo, o runner encerra os descendentes no Linux e o Job Object no
   Windows, incluindo filhos e netos. No Linux, adota órfãos antes de iniciar
   o comando e recolhe os descendentes mesmo após nova sessão (`setsid`) ou
   saída antecipada do pai. Restaura o estado de adoção ao fim e recusa um
   processo com filhos preexistentes ou outra validação concorrente. Execute
   `ci/pr.py` em processo separado se essa recusa aparecer. A contenção foi
   exercitada em Windows e Linux; outros sistemas são recusados explicitamente.
   A validação não aprova resultado
   incompleto. A retomada com `CONTINUAR=1` repete as provas da revisão isolada
   e do SHA final; ela não reutiliza uma aprovação anterior para dispensá-las.

   ```bash
   make pr TITULO="ci: o que muda, para leigo" MENSAGEM=mensagem.txt \
           CORPO=corpo.md ARQUIVOS="ci/pr.py ci/tests/test_pr.py" \
           DETALHE=detalhe.txt VALIDACAO=validacao.json
   ```

   A validação ausente, inválida ou com falha impede o fechamento. O recibo
   cita a árvore e o commit validados; mudanças de código posteriores exigem
   nova validação. Após embarcar recibo e eventos, os comandos rodam novamente
   no SHA final isolado. A prova final fica no caderno privado, vinculada a
   esse SHA, sem gerar outro commit. O gerador confere o recibo e o comando
   confirma no GitHub
   o SHA entregue. Os logs de stdout, stderr e falha ficam sanitizados em
   uma pasta privada dentro do `.git`, com revisão e tentativa. O resumo
   informa o caminho para inspeção; os logs não são publicados no recibo.
   **O recibo informa o resultado técnico, sem reproduzir conteúdo privado.**
   No título, no `detalhe` e na evidência pública, registre a mudança, os testes
   executados e o SHA ou link verificável. Não copie nomes pessoais, dados
   privados, conversas ou logs internos para explicar a entrega. Exemplo de
   molde, a preencher com teste e SHA reais: "Cadastro de responsabilidade
   atualizado; testes de atualização e acesso passaram; commit <SHA>." O
   `detalhe` tem mínimo de 80 caracteres; o recibo completo ocupa menos de 1 KB.
   Revise seu conteúdo antes do envio; a sanitização dos logs não certifica texto escrito pelo autor.

   **Confira a autorização existente antes de pedir outra.** Prepare o diff
   e o texto final do recibo, completando os identificadores gerados pelo rito
   assim que existirem. Confira no histórico da tarefa a finalidade, o destino,
   a exposição e os limites explicitamente autorizados. Ao delegar, leve no
   brief o pedido original, seus limites e o destino verificado, para que a
   autorização não se perca entre agentes. Dentro desses limites,
   as etapas técnicas da entrega, inclusive recibo e novo SHA, não exigem nova
   pergunta só pela mudança mecânica. Autorização restrita a uma ação ou commit
   continua restrita: não a transforme em autorização geral. Mudança de
   finalidade, destino ou exposição exige autorização específica. Novo SHA
   continua exigindo as validações e a revisão técnica previstas no rito.

   Uma recusa da revisão automática do aplicativo continua valendo. Prepare
   uma alternativa materialmente mais segura que resolva o motivo da recusa;
   se não houver, devolva à maestro a ação, o motivo e a decisão específica
   necessária. Não repita a mesma ação por outro caminho para contornar a
   recusa. Estas instruções orientam o agente; não alteram permissões nem
   garantem aprovação pelo aplicativo.

   Preparação concluída, validação local e PR aberto são estados distintos.
   Revisão, integração e publicação permanecem não verificadas neste comando.
   Ele devolve o número à maestro, sem armar espera ou pouso.

   `CONTINUAR=1` retoma commits existentes. Toda execução consulta o PR pelo
   ramo, recupera o recibo compatível e reexecuta a validação. A reserva usa
   uma identidade estável e grava número e chave no mesmo push atômico:
   resposta remota perdida não autoriza repetir uma reserva nova. A data da
   reserva original também é preservada. `TAR=TAR-NNN`, quando aplicável,
   conclui a tarefa pela fila existente e embarca todos os seus eventos;
   encerramento por outro fato impede a retomada. Nenhum desses estados
   declara publicação. Interface: `python ci/pr.py --help`.

   **A ordem do rito, desde 31/08/2026: o PR PRIMEIRO, o registro depois — e no
   MESMO ramo.** É por isso que o `make pr` existe: o registro de uma entrega só
   pode citar o número do PR depois que o `gh` o devolve (`armadilhas/185`). O
   portão do pouso confere o embarque e recusa PR de entrega sem o próprio
   recibo a bordo (`ci/mergear.py`); PR que só escritura (`painel/` e/ou
   `fila/`) é isento. Registro de fato pós-merge (veredito de deploy, incidente)
   continua sendo PR próprio, só de livro.
   **A cor descreve o estado que continua aberto.** Um recibo de trabalho
   validado localmente usa `info`; ele não prova publicação. Use `ambar` ou
   `vermelho` quando a entrega ainda exigir uma ação, pois essas cores abrem
   alerta no painel. Confirmado o resultado, a baixa faz parte da conclusão:
   o registro novo aponta `responde_a` para o identificador exato da entrega,
   com `gravidade: "verde"`, `evidencia` citando a URL completa do PR no GitHub
   e a conferência realizada,
   e `verificado_em` a partir da data do alerta. Se houver dois alertas,
   escreva uma baixa específica para cada um no mesmo PR; não apague o passado.

   A muralha do painel executa `python ci/encerramento_alertas.py` e recusa
   uma conclusão verde nova que cite um PR com entrega em alerta sem baixa
   comprovada. Ela também recusa baixa nova sem prova. A recusa só lê o livro,
   não cria pendência e ensina a corrigir o próprio PR. A comparação usa
   `BASE_REF` (padrão `origin/main`); base ou instrumento indisponível é ERROR.
   Alertas antigos sem relação com a conclusão nova não bloqueiam outro trabalho.
   O portão confere vínculos e evidência declarada; não consulta a produção
   nem certifica a verdade do relatório PRONTO na conversa.

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
   **Pelo `make pr` esse pedido acontece sozinho**, no passo 6, com identidade estável para retomar a mesma operação.
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
  area: null,                           // em que parte do SITE isto mexe: o NOME DO RAMO em que você trabalhou
                                        // (o "painel" de agent/painel/aba-prioridades). Tem de ser um dos nomes
                                        // de painel/areas.json; inventado, o gerador recusa. Opcional, e
                                        // recomendado em TODO registro novo: é ele que põe o fato na área certa
                                        // da aba Prioridades. Sem ele, a tela cai na `frente` e diz que caiu.
  vence_em_dias: null,                  // depois de N dias sem registro novo, isto conta como velho — ou null (não vence)

  // DECISÃO: os seis campos são obrigatórios em pedidos NOVOS ao dono.
  // Registros antigos continuam imutáveis e visíveis até resposta explícita.
  porque_so_voce: null,                 // por que esta decisão só pode ser dele
  proximo_passo: null,                  // ação concreta para ele aprovar, recusar ou executar
  se_eu_nao_decidir: null,              // o que acontece se isto ficar parado — ou null
  recomendacao: null,                   // o que você sugere, e por quê — ou null
  reversivel: null,                     // true/false SEM aspas ("false" seria verdadeiro em JS) — ou null
  impacto: null,                        // alto | medio | baixo — ou null

  // O PORTÃO DA FASE DA ESCOLA — opcional, e quase sempre null. Escreva-o só
  // quando este registro PROVA um dos oito portões que a escola atravessa antes
  // de escalar. A fase (achando, provando, escalando) é calculada da contagem
  // dos portões provados, e aparece em /admin/placar/fechamento/.
  // Exige `evidencia` E `verificado_em`: declarar não é provar, e o gerador
  // reprova quem escrever o nome fora dos oito.
  portao: null                          // demanda | conversao | economia | entrega | resultado | retencao | repeticao | escala — ou null
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
- **Pedido novo chega decidível:** `precisa_do_dono: true` cabe quando falta
  uma decisão exclusiva do mantenedor, como autorizar despesa, fornecer segredo,
  destruir dados, definir produto ou ampliar acesso. O título nomeia a decisão;
  `porque_so_voce` explica a exclusividade, `proximo_passo` diz o gesto concreto,
  `se_eu_nao_decidir` registra a consequência de esperar e `recomendacao` traz a
  sugestão com motivo. `reversivel` é booleano e `impacto` é alto, medio ou baixo.
  `ci/encerramento_alertas.py`, já executado na muralha, exige os seis campos
  apenas em IDs novos contra `BASE_REF`. Escrever uma data antiga não dispensa o portão.
  O julgamento de que só ele pode decidir continua sendo da maestro; texto
  preenchido não prova exclusividade. A máquina confere presença e tipos.
- **Falha técnica é trabalho dos robôs:** erro de teste, ferramenta ou publicação
  reparável dentro do pedido usa `precisa_do_dono: false`, `gravidade: "ambar"`
  ou `"vermelho"`, diagnóstico e próximo passo do robô em `detalhe`. Continua
  visível nos alertas e em Prioridades. A recusa do portão se corrige no próprio
  PR, sem criar automaticamente outro pedido ao mantenedor.
- **Histórico não some por adivinhação:** pedido antigo incompleto continua na
  caixa, com ausência explícita. Nem idade nem palavras do texto o encerram.
  Correção exige registro novo com `responde_a` e evidência conferida; a baixa
  não apaga o original. A ordem dos pedidos continua por idade.
- **Prioridades por área do site (07/09/2026):** a aba 🎯 mostra tudo que está
  aberto agrupado pelas seis áreas de `painel/areas.json` (Alunos, Cursos,
  Comunidade, Vendas, Seu painel, Infra e fábrica) e, dentro de cada uma, em
  quatro grupos: o que só ele decide, o que está quebrado, a fila dos robôs e os
  rumos com prazo. As áreas moram num arquivo só, lido por três leitores (esta
  página, a rota `fila.json` da área administrativa e o portão do pouso), porque
  o mesmo nome escrito em três lugares divergiria sozinho. **Um fato, um lugar:**
  o pedido que também é âmbar aparece em "Decidir" e some de "Quebrado" na mesma
  área, e as contagens do topo saem da mesma estrutura que desenha os blocos,
  nunca de uma segunda contagem. O que a página não reconhece vai para "sem área
  reconhecida", nunca some. A fila dos robôs é buscada uma vez, ao abrir a aba;
  aberto por duplo clique, a tela diz que ela só chega pelo site.
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
