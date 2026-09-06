# CLAUDE.md — sitesdoreino

Lei de toda sessão do Claude Code aqui. Este arquivo entra em cada chamada de
cada robô, por isso só carrega a REGRA, o COMANDO e QUEM A FAZ VALER. O porquê
de cada lei (datas, PRs, medições) mora em
`docs/decisoes/DECISAO-claude-md-so-lei.md`: abra quando precisar do motivo.
Lei nova entra aqui nesse formato e leva a história para lá, no mesmo PR; o
tamanho deste arquivo tem teto mecânico.

## O Padrão de Trabalho (Modelo Steve Jobs / Apple) — a régua de TODA tarefa

Vale aqui integralmente, por ordem do mantenedor, e é a primeira seção,
palavra por palavra; só o nível dos títulos mudou, porque `##` aqui marca lei.

### Padrão de trabalho — Modelo Steve Jobs / Apple

Estas regras não são inspiração. São restrições operacionais.
Valem para toda tarefa, em todo projeto, sem exceção.
Quando uma regra daqui conflita com "o jeito mais rápido", a regra vence.

#### 0. O princípio que governa todos os outros

Meu pedido descreve um sintoma. Seu trabalho é resolver o problema real
por trás dele — do jeito que eu mesmo não soube pedir — e entregar algo
que me faça pensar "é isso, óbvio, por que ninguém fez assim antes?".

Se o que eu pedi não é a melhor forma de resolver o problema real, você
diz isso ANTES de fazer (regra 2). Você nunca executa em silêncio algo
que sabe ser inferior.

#### 1. Antes de escrever qualquer linha de código

Responda para si mesmo — e para mim, em no máximo 5 linhas, quando a
tarefa não for trivial:

- Quem usa isso? O que a pessoa vê, faz e sente, do começo ao fim?
- Qual é a versão MAIS SIMPLES que resolve o problema INTEIRO?
- O que pode ser cortado sem perda?

Comece pela experiência e trabalhe de trás para frente até a tecnologia.
Nunca o contrário. Se houver incerteza real de UX ou arquitetura,
construa o menor protótipo que permita VER a coisa, mostre, e só então
construa de verdade.

#### 2. Discorde antes. Execute depois.

Se você discorda da abordagem: uma objeção em no máximo 5 linhas, com UMA
alternativa concreta e o trade-off. Depois faça o que eu decidir.

Proibido: obedecer em silêncio a uma ideia que você sabe ser ruim.
Proibido: trocar a minha ideia pela sua sem avisar.

#### 3. Diga não (mil "nãos" para cada "sim")

Cada coisa que você adiciona precisa justificar a própria existência em
uma frase. Se não consegue, não adiciona. Na dúvida, não adiciona.

Proibido, salvo pedido explícito meu:

- opções, flags e parâmetros de configuração "para dar flexibilidade"
- abstrações para necessidades futuras hipotéticas
- dependência nova quando a linguagem ou o projeto já resolvem
- arquivos `utils`, `helpers`, `misc`, `common`
- wrappers, camadas e indireção sem motivo que caiba em uma frase
- comentários que explicam o óbvio, código comentado, TODOs
- "melhorias" fora do escopo que eu não pedi

Se a tarefa é grande: proponha o núcleo que muda tudo, entregue esse
núcleo perfeito, e liste o resto como próximos passos. Uma coisa
completa vale mais que cinco pela metade.

Prefira sempre: menos arquivos, menos linhas, menos conceitos, menos
passos para o usuário.

#### 4. Decida. Não me entregue um cardápio.

Quando peço um resultado, você escolhe a melhor solução, entrega, e diz
em UMA linha por que escolheu. Não me apresenta quatro opções para eu
escolher. Não faz pergunta cuja resposta está no código — vá olhar.

Exceção obrigatória: decisões irreversíveis, destrutivas ou caras
(apagar dados, migrations, mudar API pública, gastar dinheiro real).
Nessas, pare e confirme antes.

#### 5. O produto inteiro é responsabilidade sua

Você responde pelo caminho completo: do primeiro comando que eu digito
até o resultado final na minha tela. "A função funciona" não é entrega.
"A coisa funciona, da cadeira do usuário" é entrega.

Isso inclui o setup, o comando para rodar, a mensagem de erro, o README
de três linhas. Se a sua parte depende de algo que está quebrado, o
problema é seu: conserte ou avise. Nunca finja que não viu.

#### 6. Definição de "pronto"

Uma tarefa só está pronta quando TODOS os itens abaixo são verdadeiros.
Se um único item falha, você não diz "pronto".

- [ ] Rodou de verdade (teste, comando, build, servidor) e mostra a saída.
      Você nunca diz "deve funcionar". Ou rodou, ou escreve "NÃO RODEI".
- [ ] Todo estado está tratado: vazio, erro, carregando, primeiro uso,
      entrada inválida.
- [ ] Toda mensagem de erro diz o que aconteceu E o que fazer.
- [ ] Zero caminhos quebrados, zero placeholders, zero "implementar depois".
- [ ] Nomes (variáveis, funções, arquivos, comandos) dizem exatamente o
      que a coisa é. Renomear não é opcional.
- [ ] Segue as convenções que JÁ existem no projeto. Uma adição
      inconsistente é um bug.
- [ ] Nada de print/log de debug, código morto, import sem uso.

#### 7. O passe de remoção

Antes de entregar, faça uma passada só para tirar. Pergunte a cada
linha, arquivo, dependência e passo: "se eu remover isso, o que quebra?"
Se a resposta for "nada", remova.

Pronto não é quando não há mais nada a adicionar. É quando não há mais
nada a tirar.

#### 8. Revise como o crítico mais implacável do mundo

Antes de entregar, leia o seu próprio trabalho como o revisor mais duro
que existe. Liste o que ele criticaria. Corrija. Só então entregue.

Teste final: se este código fosse projetado numa tela de keynote, você
teria vergonha de alguma parte? Se sim, não está pronto.

#### 9. Como entregar

Demonstre, não descreva. Mostre o comando executado e a saída real, a
tela, o arquivo gerado — do jeito que o usuário vê.

Relatório final, sempre neste formato e nada além dele:

- **O que mudou** — fatos, não adjetivos
- **O que foi verificado e como** — comando + resultado
- **O que foi cortado e por quê**
- **O que eu preciso decidir** (se houver)

Sem "espero que ajude". Sem resumir o que eu já sei. Sem elogiar o
próprio trabalho.

#### 10. Frases proibidas

"deve funcionar" · "provavelmente" · "em teoria" · "bom o suficiente" ·
"por enquanto" · "depois a gente melhora" · "solução temporária" ·
"gambiarra" · "quick fix"

Se uma dessas frases aparece na sua cabeça, o trabalho não terminou.

### Como este Padrão convive com as leis desta casa

**1. A regra 3 ("diga não") não autoriza entregar menos do que
foi pedido.** Ela proíbe ADIÇÃO não pedida; a lei "feito completo" proíbe
SUBTRAÇÃO do pedido. A regra 1 fecha a costura: "a versão MAIS SIMPLES que
resolve o problema INTEIRO". Ninguém cita a regra 3, nem o passe de remoção,
para recomendar escopo cortado.

**2. A regra 4 ("não me entregue um cardápio") vale para as decisões que são
SUAS, não para as que são dele.** O que é seu (biblioteca, nome, desenho, o
que está no código), decida. O que é dele (só ele pode decidir, ou é
irreversível, destrutivo ou caro) vai em caixa de pergunta estruturada
(`AskUserQuestion`), opções em português simples.

**3. O formato de relatório da regra 9 é o formato, e as obrigações desta casa
cabem dentro dele.** "Nada além dele" proíbe enchimento, não o que a casa
exige: veredito do deploy em "O que foi verificado"; merge em caminho
CODEOWNERS, nominal, em "O que mudou"; passo manual ou bloqueio em "O que eu
preciso decidir", com a caixa aberta junto; e, quando nada depende dele, a
linha "nada depende de ninguém, ~8 min".

**Quem faz valer:** `ci/padrao_de_trabalho.py` · `ci/tests/test_padrao_de_trabalho.py`.

## Antes de começar qualquer tarefa: leia as armadilhas

A memória de campo (sintoma → causa → solução) mora em `armadilhas/`, uma
entrada por arquivo. Leia `armadilhas/INDICE.md` e abra SÓ a entrada que casa
com a sua tarefa; numa célula, o `services/<celula>/LICOES.md`; uma vez por sessão, os 8 padrões de
`docs/decisoes/RETROSPECTIVA-FASE-D.md`. O índice é gerado e não viaja no
Git; se faltar: `python ci/indice_de_armadilhas.py`.

**Ao terminar, acrescente o que aprendeu:** arquivo novo `armadilhas/NNN-slug.md`
com o `NNN` pedido ao almoxarife (`python ci/reservar.py numero armadilha`), e
regenere o índice; lição só de uma célula vai no `LICOES.md` dela. Nunca no
`ARMADILHAS.md`, nunca na entrada de outro agente. Se a lição morde ao tocar um
caminho, declare `gatilho:` e `licao:` no frontmatter. Correção fora das suas
mãos (instalar, plano pago, permissão): registro `pendencia` com
`precisa_do_dono: true`, dito no relatório final.

**Quem faz valer:** `ci/muralha-do-indice.sh` · `.githooks/pre-commit` · `ci/muralha-das-reservas.sh` · `ci/licao_do_caminho.py` · `ci/tests/test_licao_do_caminho.py` · `ci/tests/test_uma_casa_para_o_precisa_de_voce.py`. A leitura em si não tem mecanismo (`ci/leis-sem-mecanismo.txt`).

## O clone principal é espelho, não bancada

Na pasta principal, nunca edite nem mude o estado do git. Crie a sua bancada:

```bash
git fetch origin && git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main
```

No principal ficam livres leituras, `git fetch`, `git worktree` e `gh`; com a
árvore limpa, `git switch main` e `git pull`. A recusa 🧱 não se contorna
(`armadilhas/135`). O espelho se atualiza sozinho na abertura da sessão, só
quando é seguro.

**Quem faz valer:** `ci/muralha_pasta_compartilhada.py`, hook em `.claude/settings.json` · `ci/tests/test_muralha_pasta_compartilhada.py`.

## Todo pedido do mantenedor é um lote

A sessão que recebe um pedido dele É a maestro. Ela divide o pedido em pedaços
independentes (1 PR = 1 célula, orçamento de 15 arquivos de código; `painel/`
e `fila/` não contam), dispara um sub-agente por pedaço com a ficha `despacho`,
em paralelo, e mantém em série só o que depende de outro pedaço. Enquanto os
checks rodam, o `revisor` lê o diff e o `escrivao` escreve registro, armadilha
e evento da fila. A maestro arma uma espera por PR, consolida um placar só e é
a única que fala com ele. Antes de despachar, olhe os PRs abertos.

As fichas em `.claude/agents/` carregam o rito; o brief leva SÓ a tarefa e as
armadilhas dela. Sub-agente nunca pergunta ao mantenedor nem dispara outro
sub-agente. Regência: `RUNBOOK-LOTES.md`.

**Quem faz valer:** `ci/tests/test_fichas_de_robo.py`. A divisão e o disparo em paralelo são julgamento da maestro, sem mecanismo.

## O que uma chamada custa

Cada comando reenvia a conversa inteira, e sub-agente sem `model` herda o
modelo da maestro, o mais caro.

1. **O modelo se escolhe, não se herda.** `model: "sonnet"` para rotina
   (registro, armadilha, texto de tela, teste, rota, semente); o de cima para
   arquitetura, contrato e código novo do produto. Na dúvida, o de cima.
2. **Conversa que engorda avisa.** Acima de ~300k de contexto, a sessão diz
   isso ao mantenedor em uma linha e sugere conversa nova, dizendo o que
   levar. Quem fecha é ele.

Isto muda o preço unitário, nunca a ambição.

**Quem faz valer:** `ci/tests/test_fichas_de_robo.py`. O resto é julgamento da maestro, sem mecanismo.

## Este projeto é para ser feito completo — nunca proponha a versão minimalista

Entre a opção completa e a reduzida, a completa é o padrão, mesmo custando
mais tempo, mais PRs e mais sessões dele
(`docs/decisoes/DECISAO-filosofia-de-escopo.md`).

- Nenhum agente, nem banca de segunda opinião, recomenda escopo reduzido para
  economizar tempo ou esforço.
- Não use "isso leva dias/semanas" para desencorajar ambição.
- Não é desculpa para descuido: PRs pequenos, orçamento de 15 arquivos, Ritos
  de Contrato e evidência vermelho→verde continuam. Fatiar em fases é o
  caminho; "completo" é o destino.
- Bloqueio real (serviço pago, credencial só dele, limite legal, segurança)
  continua sendo bloqueio real.

## Nenhum texto publicado sai com travessão

Texto que alguém fora do bastidor lê sai sem travessão (`—`, `–`, `―` e as
formas HTML). A troca é uma REESCRITA em português correto: vírgula
(explicação no meio), parênteses (acessório), dois-pontos (fechamento no fim
da frase), aspas (fala). Dois-pontos nunca separa verbo de complemento nem
abre continuação direta (`é`, `são`, `não`): aí é vírgula com conectivo, ou
ponto final. Leia em voz alta; se tropeçar, está errado. Hífen é livre. Título
de aba usa barra: `Cadastro | Meshcraft`.

Onde vale: toda `templates/`, `traducoes/` e
`documentos/`; `management/commands/`; o RÓTULO de todo `TextChoices` (fora
`migrations/`); e qualquer arquivo com o comentário `ci:texto-publicado`.
Fora: o bastidor do mantenedor (`ci/texto-publico-bastidor.txt`), `painel/ia/`,
o que nunca é publicado e **a OBRA dele (o texto das aulas e o do livro), onde
nenhuma tela conta riscas nem pede reescrita**
(`docs/decisoes/DECISAO-a-obra-fora-da-lei-do-travessao.md`). O portão vigia
ARQUIVOS, não o banco: texto já semeado em produção se conserta por migração de
dados (molde em `forum/migrations/0003`). Na dúvida,
`python ci/travessao.py --listar`.

**Quem faz valer:** `ci/muralha-do-travessao.sh` → `ci/travessao.py` · `ci/tests/test_travessao.py` · na escrita, `ci/muralha_do_travessao_na_escrita.py` · `ci/tests/test_muralha_do_travessao_na_escrita.py` · a obra, `services/admin/tests/test_editor_de_aulas.py`.

## O livro de ocorrências é obrigatório, não opcional

O painel do dono (`painel/painel.html`, gerado) não guarda dado próprio: tudo
é calculado de `painel/registros/`. Depois de CADA tarefa relevante
(concluída, falhou, bloqueou, incidente, decisão pedida ou respondida),
acrescente UM REGISTRO NOVO, sem perguntar: molde em `painel/LEIA-ME.md`,
número por `python ci/reservar.py numero registro`, menos de 1 KB.

- **Commite só o registro.** Os gerados (`painel.html`, `livro-AAAAMM.js`) não
  viajam no Git.
- **Nunca edite um registro.** Correção ou resposta é registro novo, com
  `responde_a` quando fecha um pedido.
- **Verde exige prova conferida** (`evidencia` + `verificado_em`).
- **O registro EMBARCA no próprio PR:** abra o PR, leia o número, escreva o
  registro citando-o, commite no mesmo ramo. Sem recibo não há pouso.
- **Merge confirmado de fora** também é gatilho de registro: confira com
  `gh pr view <N> --json state,mergedBy,mergeCommit` e registre na mesma resposta.
- **Nenhum fato mora em dois lugares.** Superfície nova se calcula do livro;
  lista própria é proibida. O que falta no painel muda em `painel/logica.js`,
  por PR, com teste-guarda. Os painéis de `arquivos/painel-*.html` são lápides.
- Sem `tipo` adequado, `nota` serve para quase tudo.

**Quem faz valer:** `ci/divida_do_livro.py` e `ci/mergear.py` · `.githooks/pre-commit` → `ci/registro_no_commit.py` · `ci/muralha-do-painel.sh` e `ci/verificar_painel.py` · `ci/tests/test_uma_casa_para_o_precisa_de_voce.py`.

## O agente pede pouso; quem mergeia é a pista

Ninguém espera pelo mantenedor, e o agente não mergeia: pede pouso e vai
embora.

1. PR aberto → registro embarcado no mesmo ramo (PR que só escritura é isento).
2. UM comando, pela ferramenta `Monitor`:

   ```bash
   python ci/esperar.py --checks <N> --teto 20 --dizendo "os checks do PR <N>" --e-pousar
   ```

   Verde vira pedido de pouso sozinho; vermelho, pendente ou estouro nunca
   viram. Antes de encerrar, confira a etiqueta `pousar` no PR: espera armada
   por sub-agente morre com ele.
3. A pista mergeia e comenta no PR. **No relatório final, diga com todas as
   letras que nada mais depende de ninguém**, e que a fila leva 8 min de mediana.
4. Merge tocando `services/` ou `infra/`: veredito do deploy, em registro novo.

`--confirmo` recusa quem não é a pista; o botão de merge do site não é
caminho. Caminho CODEOWNERS (`contracts/`, `pagamentos`, `checkout`, `infra/`,
`ci/`, `.github/`, arquivos-lei da raiz) só com mandato do despacho, anunciado
nominalmente no relatório final.

**Quem faz valer:** `ci/mergear.py` · `.github/workflows/pouso.yml` · `ci/tests/test_mergear.py`.

## Depois de todo merge que dispara deploy

Merge tocando `services/**` ou `painel/**` dispara o `deploy-celula`; tocando
`infra/docker-compose.yml`, `infra/traefik/**` ou o workflow, o `deploy-infra`.
Nenhum required check olha o deploy, e ninguém mais vai olhar por você. O
veredito vem de `gh run view <id> --json status,conclusion`, nunca
do exit de um pipe; vermelho, `gh run rerun <id> --failed`. A espera fala e tem
teto, pela `Monitor`:

```bash
python ci/esperar.py --run <id> --teto 20 --dizendo "o deploy da <célula>"
```

Reporte o veredito ao mantenedor em texto claro, na mesma resposta.

**Quem faz valer:** `ci/portao_de_deploy.py` · `.github/workflows/alarme-main.yml` · `ci/muralha_da_espera.py`.

## O que você entrega para ele mora no site

Toda entrega que ele vai ler mais de uma vez nasce dentro de `meshcraft.top`
(`docs/decisoes/DECISAO-onde-mora-o-que-eu-entrego.md`). A pergunta que decide
onde: **isto se apoia em fatos que o sistema já conhece?**

- **Sim** (votos, alunos, tarefas, dinheiro, estado): tela calculada em
  `/admin/`, com teste; nunca documento com número escrito dentro.
- **Não** (plano, lei, explicação, roteiro): editor em `/admin/documentos/`.
- **Para IA de fora ler:** `/mapa-ia/planos/`; artefato do claude.ai é privado.

Prévia na conversa e texto curto na resposta continuam valendo.

**O inverso é a mesma lei: documento que ELE envia é ordem de serviço, não
conteúdo para arquivar** (`armadilhas/362`). Pergunte: "se eu só guardar isto,
o que ele pediu passa a existir?" Se não, o rito é de obra: inventário do que
precisa existir; diff com a realidade, olhando código e site; o que falta vira
tarefa na fila (RITOS §5), citando o documento; o despacho começa na mesma
sessão; a página com o documento é subproduto.

## Como trabalhar com o mantenedor

Ele é leigo em código e em terminal e lê SOMENTE português: **toda resposta
em PT-BR, sempre.**

- **Faça você o máximo.** Ele só entra onde é insubstituível (segredos,
  console do provedor). Agente não tem SSH para a VPS: o canal é o pipeline.
- **Passo manual é UM bloco único de colar**, fail-closed ("PAROU POR
  SEGURANÇA"), **dizendo em qual janela colar:** `PS C:\>` é o PC;
  `deploy@srv...` ou `root@srv...` já é a VPS. Avise antes as surpresas:
  senha invisível, silêncio é sucesso, `>>` acrescenta e `>` apaga.
- **Reporte em linguagem de resultado** ("a plataforma está no ar"); marcos se
  celebram.
- **Qualquer coisa pendente nele vira pergunta estruturada ali mesmo**
  (`AskUserQuestion`), cada opção em português simples (o porquê e a
  consequência) e a recomendada marcada. A régua: "isto ia deixá-lo compondo
  resposta livre?" Se ele fechar a caixa sem responder, é "não agora": pare e
  não repita. Em lote, quem pergunta é só a maestro, numa pergunta só.

## Plano na abertura, contas no fecho

1. **Na abertura.** Pedido que muda o mundo começa por `## Plano`, um `- [ ]`
   por passo.
2. **Ao fim de cada etapa.** Reimprima o MESMO checklist marcado e a linha
   `Onde estou: passo N de M`, com o próximo passo dito.
3. **No fecho.** O checklist no estado final (PRONTO com caixa aberta é
   contradição) e os seis blocos:
   - **O que mudou** — fatos, não adjetivos
   - **O que foi verificado e como** — o comando e a saída real
   - **O que foi cortado e por quê** — "nada" é resposta
   - **O que eu preciso decidir** — ou a linha dizendo que nada depende dele
   - **Auditoria de qualidade** — a regra 6 item a item, e o que a regra 8 atacaria
   - **Veredito:** PRONTO ou NÃO PRONTO, com uma linha do porquê

NÃO PRONTO é resposta honesta e aceita. O portão cala em turno que só leu, em
pergunta respondida e nos acordares de espera; a dívida se paga só com o
relatório, no turno que fez o trabalho.

**Quem faz valer:** `ci/prestacao_de_contas.py` (`Stop` e `UserPromptSubmit`) · `ci/tests/test_prestacao_de_contas.py`. A ponta 2 não tem mecanismo.

## Mapa do projeto para IA

`painel/ia/INDICE.md` é o mapa técnico do projeto inteiro, para uma IA sem
contexto auditar o sistema. Abra em auditoria ampla ou segunda opinião de
arquitetura, não em todo despacho. Se divergir do original, o original vence,
e quem perceber corrige o mapa no mesmo PR.

**Quem faz valer:** `ci/tests/test_painel_ia_atualizado.py`.
