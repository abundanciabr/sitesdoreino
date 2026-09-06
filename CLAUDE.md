# CLAUDE.md — sitesdoreino

Instruções para qualquer sessão do Claude Code neste repositório.

## O Padrão de Trabalho (Modelo Steve Jobs / Apple) — a régua de TODA tarefa


O mantenedor trouxe este padrão de fora em 04/09/2026, com uma ordem de duas
partes: que ele valha aqui **integralmente**, e que fique onde **nenhum robô
consiga ignorá-lo**. Por isso ele mora AQUI, e não num arquivo próprio: o
`CLAUDE.md` da raiz é o único documento deste repositório que entra sozinho no
contexto de toda sessão, em toda bancada, sem ninguém precisar abri-lo. Arquivo
separado depende de alguém lembrar, e lei que depende de lembrança é a
doença-mãe desta casa (Constituição, Lei 1). Os outros pontos de partida do
projeto apontam para cá — a Constituição (Lei 10), a declaração de abertura do
`RITOS.md` §1, o cabeçalho do índice de armadilhas que se lê antes de cada
tarefa, o molde de despacho do `CAMINHO-DOURADO.md` e o aviso de abertura de
sessão. Um só texto, muitas portas.

O texto abaixo é o dele, palavra por palavra. A única mudança é o nível dos
títulos (`#` virou `###` e `##` virou `####`), porque neste arquivo `##` é o
marcador de lei que o censo de mecanismos lê (`ci/leis_sem_mecanismo.py`): sem
a demoção, cada uma das onze regras viraria uma "lei" separada cobrando
declaração própria.

Ele não revoga nada do que já estava escrito. As três costuras onde ele encosta
em lei desta casa estão resolvidas logo depois do texto, e é a leitura
conciliada que vale.

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

### Como este Padrão convive com as leis que já existiam aqui

Três pontos, e só três, onde a leitura apressada do Padrão brigaria com uma lei
daqui. Em nenhum deles a resposta é "ignore o Padrão": é a leitura que faz os
dois valerem ao mesmo tempo. Fora destes três, o Padrão vale como está escrito.

**1. A regra 3 ("diga não", "menos, sempre") não autoriza entregar menos do que
foi pedido.** A regra 3 proíbe **adição** não pedida: flag "para dar
flexibilidade", abstração para futuro hipotético, dependência nova, arquivo
`utils`, "melhoria" fora de escopo. A lei desta casa (seção "Este projeto é para
ser feito completo") proíbe **subtração** do que foi pedido. As duas dizem a
mesma coisa por lados opostos, e a própria regra 1 já fecha a costura: **"a
versão MAIS SIMPLES que resolve o problema INTEIRO"**. A simplicidade é dos
MEIOS; o alvo continua inteiro. Nenhum robô cita a regra 3, nem o passe de
remoção da regra 7, para recomendar escopo cortado, versão reduzida ou "faz só
o núcleo por enquanto" quando o mantenedor pediu a coisa completa — isso já
custou caro em 03/09/2026, e a memória está em
`docs/decisoes/DECISAO-filosofia-de-escopo.md`.

**2. A regra 4 ("não me entregue um cardápio") vale para as decisões que são
SUAS, não para as que são dele.** Ela proíbe empurrar para o mantenedor escolha
que o robô tinha como fazer sozinho: qual biblioteca, qual nome, qual desenho,
e qualquer pergunta cuja resposta está no código (vá olhar). Quando a decisão é
genuinamente dele — só ele pode decidir, ou ela é irreversível, destrutiva ou
cara, que é a exceção escrita na própria regra 4 — continua valendo a lei desta
casa e a instrução global dele: **caixa de pergunta estruturada
(`AskUserQuestion`) ali mesmo, opções traduzidas para português simples, nunca
uma frase solta esperando que ele digite resposta livre.** Ele é leigo em código
e pediu isso com força em 25/08 e em 27/08/2026. O que ele não quer é escolher
no lugar do robô; não é clicar num botão.

**3. O formato de relatório da regra 9 é o formato, e as obrigações desta casa
cabem dentro dele.** "Nada além dele" proíbe enchimento: "espero que ajude",
resumo do que ele já sabe, elogio ao próprio trabalho. Não dispensa o que esta
casa exige que seja dito, e que entra nos quatro títulos:

- veredito do deploy disparado pelo merge → **O que foi verificado e como**;
- merge em caminho CODEOWNERS, anunciado nominalmente → **O que mudou**;
- passo manual, bloqueio, ou qualquer coisa que dependa dele → **O que eu
  preciso decidir**, com a caixa de pergunta aberta junto;
- quando nada depende dele, a linha que diz isso ("nada depende de ninguém,
  ~8 min") — a ausência dela já o fez esperar horas achando que a bola estava
  com ele.

Marco de verdade pode ser comemorado em uma linha: comemorar um fato não é
elogiar o próprio trabalho.

**Quem faz valer:** `ci/padrao_de_trabalho.py` (confere que o texto íntegro continua no lugar, que as portas apontam para cá, e é ele que imprime o aviso de abertura de sessão, derivado deste texto) · `ci/tests/test_padrao_de_trabalho.py`.


## Antes de começar qualquer tarefa: leia as armadilhas


A memória de campo do projeto — o que já custou tempo aqui, em formato sintoma →
causa → solução — mora em **`armadilhas/`**, uma entrada por arquivo. Desde
23/08/2026 ela **não é mais um monólito**: o antigo `ARMADILHAS.md` de 1.490 linhas
era 48% da carga de contexto de todo despacho (PLANO-10X, Alavanca 2).

**A regra de leitura, em uma frase: leia `armadilhas/INDICE.md` e abra SÓ a entrada
que casa com a sua tarefa.** O índice tem uma linha por armadilha, com a mensagem de
erro crua como chave — dê Ctrl+F pelo erro que você está vendo, ou pela tecnologia
que vai tocar. Ler a pasta inteira desfaz o motivo de ela existir. Leia também o
`ARMADILHAS.md` (que ficou curto: a regra de uso + a partida rápida do §2) e, se for
trabalhar dentro de uma célula, o `services/<celula>/LICOES.md` quando existir.

**O índice é GERADO e não viaja mais no Git (desde 30/08/2026, TAR-022).** Ele, o
`armadilhas/GUARDAS.json` e o `armadilhas/SINAIS.json` saem de
`ci/indice_de_armadilhas.py` — e por isso **não existem num checkout novo até serem
materializados**. Quem materializa por você: o `SessionStart` de
`.claude/settings.json`, ao abrir a sessão (no clone principal, de onde o sino lê, e
no seu worktree). Se mesmo assim faltar, é uma linha:

```bash
python ci/indice_de_armadilhas.py    # ou: make indice
```

Não procure o índice com `git show origin/main:armadilhas/INDICE.md` — ele não está
mais lá, e o comando falha. **Por que saiu:** a lei manda todo robô acrescentar uma
armadilha ao fim de cada tarefa, e cada entrada nova reescrevia os três arquivos
inteiros; dois robôs do mesmo lote colidiam sem ter escrito uma linha em comum. Em
30/08/2026, num lote de 4, DOIS PRs foram devolvidos pela pista por esse conflito
(o #573, duas vezes). É a doença do painel (`armadilhas/156`), curada com o mesmo
desenho da Onda 3 — fonte multiescritor, materialização de escritor único, validação
independente. Arquivo ausente dá erro na hora e você regenera; o conflito diário era
silencioso até a pista devolver o PR.

Não é formalidade: as mesmas armadilhas já pegaram mais de um agente — sombreamento
de nome entre model Django e `ninja.Schema`, o middleware que derruba o `/healthz`, o
orçamento de 15 arquivos que decide a arquitetura antes de você escrever código. Cada
redescoberta custa tokens e uma rodada de teste.

**E leia também, uma vez por sessão, os 8 padrões de
`docs/decisoes/RETROSPECTIVA-FASE-D.md`** — é curto e é o *andar de cima* do catálogo:
as categorias que atravessam as armadilhas individuais (falso-verde · garantia sem
mecanismo · prova de fora · fail-closed na borda · humano no caminho crítico · contexto
é orçamento · sessões paralelas · viabilidade sem ler a config). O catálogo cura o caso;
só o padrão cura a classe — e a Fase D provou isso do jeito caro: em 48h, uma sessão
repetiu **duas** falhas que já estavam documentadas em outra forma, por conhecer os casos
e não a categoria.

**Ao terminar, acrescente o que aprendeu** — isso faz parte de terminar a tarefa, como
o painel. Regra de onde escrever: se serve para qualquer célula, **crie um arquivo
novo** `armadilhas/NNN-slug.md` — e o **`NNN` se PEDE, não se escolhe**
(`python ci/reservar.py numero armadilha`, que reserva no servidor; `ci/muralha-das-reservas.sh`
reprova o PR que escolheu à mão) — e rode
`python ci/indice_de_armadilhas.py` para regenerar o índice; se só faz sentido dentro
de uma célula, vai no `LICOES.md` dela. **Nunca acrescente ao fim do `ARMADILHAS.md`
nem edite a entrada de outro agente para encaixar a sua** — arquivo novo por entrada
é exatamente o que faz duas sessões paralelas pararem de colidir no mesmo hunk.

**Se a correção definitiva não estiver nas suas mãos** — depende de instalar algo na
máquina, de plano pago, de permissão — **abra um registro** em `painel/registros/`
(tipo `pendencia`, com `precisa_do_dono: true`) **e diga isso ao usuário no relatório
final, em texto claro**. Ele não lê documento a cada sessão; se você contornar em
silêncio, o mesmo atrito volta no próximo despacho, e no seguinte.

**O que espera por ele mora num lugar só — e esse lugar é o livro.** A caixa
"Precisa de você" do painel é CALCULADA (pedido sem resposta), então ela não
consegue esquecer nem inventar. A `§1` do `ARMADILHAS-OPERACAO.md` **deixou de ser
lista de pendências em 26/08/2026**: ela guarda o histórico de cada atrito e as
instruções técnicas dos passos manuais, e **nada de estado**. Não acrescente linha
nova lá, e não devolva marcador 🔴/🟡 às que existem —
`ci/tests/test_uma_casa_para_o_precisa_de_voce.py` reprova as duas coisas.

Por que a regra é dura: até 26/08 as duas listas coexistiam e **já discordavam** —
7 itens "abertos" na tabela contra 6 no painel, com um deles invisível para o
mantenedor. Foi a doença do H18 voltando por dentro da própria lei que a curou
(a auditoria que achou isso está no registro `20260826-019`).

**Quem faz valer:** `ci/muralha-do-indice.sh` (constrói o índice em todo PR, prova que reconstrói igual, e reprova se um gerado voltar ao índice do Git) · `.githooks/pre-commit` (o mesmo, aqui na máquina) · `ci/muralha-das-reservas.sh` (número pedido ao almoxarife). **A LEITURA em si não tem mecanismo** e está declarada em `ci/leis-sem-mecanismo.txt`.

## Mapa do projeto para IA (desde 27/08/2026)


Existe um mapa técnico do projeto inteiro — leis, células, contratos,
infraestrutura, CI/CD, decisões de produto — escrito especificamente para
uma IA sem contexto prévio auditar o sistema de ponta a ponta e sugerir
melhorias: **`painel/ia/INDICE.md`**. Não é leitura obrigatória de todo
despacho (é mais longo que a dieta normal de contexto, e a maioria das
tarefas cabe na leitura de armadilhas + a constituição da célula) — abra
quando a tarefa for uma auditoria ampla, uma segunda opinião externa sobre
arquitetura, ou quando faltar a visão geral do sistema inteiro. Como os
outros mapas deste projeto, ele é um resumo curado: se divergir do
documento original, o original vence, e quem perceber a divergência corrige
o mapa no mesmo PR.

**Quem faz valer:** `ci/tests/test_painel_ia_atualizado.py`.

## O livro de ocorrências é obrigatório, não opcional (desde 26/08/2026)


O painel do dono é **`painel/painel.html`** — a porta única, que **não guarda
nenhum dado próprio**: toda vista é calculada de **`painel/registros/`** (o
livro de ocorrências, versionado) e de medições ao vivo. Decisão do mantenedor
em 26/08/2026, após 8 rodadas de consultoria externa; análise em
`docs/paineis/VEREDITO-DAS-CONSULTORIAS.html`, contrato em `painel/LEIA-ME.md`.

**Regra permanente:** depois de CADA tarefa relevante — concluída, falhou,
ficou bloqueada, mudou de estado, incidente, decisão pedida ou respondida —
**acrescente UM REGISTRO NOVO** em `painel/registros/` (molde no
`painel/LEIA-ME.md`), **sem perguntar se deve**. Registrar é parte de terminar a
tarefa; a muralha-do-painel do CI recusa PR com o livro inconsistente.

**O que você commita é o registro, e SÓ o registro** (desde 28/08/2026, Onda 3
do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). `painel/painel.html` e
`painel/livro-AAAAMM.js` são **gerados**, estão no `.gitignore` e quem os
constrói é a integração — a muralha em todo PR e o deploy antes de montar a
imagem. Rodar `node painel/gerar_manifesto.js` na sua máquina continua sendo
bom (ele valida o registro e você vê o painel), mas o resultado **não entra no
commit**: `.githooks/pre-commit` barra aqui e `ci/verificar_painel.py` reprova
no CI. Motivo medido: enquanto os dois viajavam no Git, todo registro reescrevia
os arquivos inteiros e dois robôs no mesmo dia colidiam sem ter escrito uma
linha em comum — um PR de 4 arquivos levou oito tentativas para entrar
(`armadilhas/156`). Para VER o painel na sua máquina: dois cliques em
`painel/abrir-o-painel.cmd`. O painel de verdade é
<https://meshcraft.top/admin/painel/>.

As regras que importam:

- **Nunca edite um registro existente.** Atualização, correção ou resposta é
  um registro NOVO — se ele fecha um pedido, aponte `responde_a`. A caixa
  "precisa de você" é CALCULADA (pedido sem resposta): ela não esquece, e
  ninguém a mantém à mão.
- **Verde exige prova conferida** (`evidencia` + `verificado_em`). Sem prova,
  registre como está — o painel mostra "não comprovado", e isso é honesto.
- **O registro EMBARCA no próprio PR, antes do pedido de pouso** (desde
  31/08/2026). Abra o PR, leia o número, escreva o registro citando esse
  número e commite no MESMO ramo — o portão (`ci/mergear.py`) recusa pouso de
  PR sem o próprio recibo a bordo. Não é falso-verde: o registro só entra no
  livro SE o merge acontecer, o recibo não existe sem o fato. Por que mudou:
  o rito manda pedir pouso e ir embora, e "registrar depois do merge" deixava
  o livro sem ninguém para escrevê-lo — em 31/08, 12 das 25 aterrissagens de
  um dia foram PRs pagando dívida atrasada (`armadilhas/248`).
- **Merge confirmado de FORA ainda é gatilho de registro, não pergunta.**
  Alguém confirmou um merge que não veio pela pista ("feito", "ok", um link,
  um "✓"): confira de verdade
  (`gh pr view <N> --json state,mergedBy,mergeCommit`) e registre na MESMA
  resposta — esse é o caso raro que o embarque não cobre.
- **A LEI ANTI-DUPLICAÇÃO: nenhum fato do projeto mora em dois lugares.**
  Superfície nova de acompanhamento se calcula do livro; superfície que
  mantém lista própria é proibida — inclusive dentro do próprio painel, e
  inclusive "só um HTML rapidinho em `arquivos/`". Se o painel não mostra algo
  que deveria, a mudança é na regra de cálculo (`painel/logica.js`, por PR,
  com teste-guarda) — nunca uma lista paralela.
- Os painéis antigos de `arquivos/painel-*.html` são **lápides e fotografias**
  (história congelada). Não os atualize; não crie novos.

**Quem faz valer:** `ci/divida_do_livro.py` e `ci/mergear.py` (o recibo embarca no PR e o portão confere NA PORTA; a cobrança pós-merge vira rede de segurança, que ainda lista os pagamentos já em voo) · `ci/muralha-do-painel.sh` e `ci/verificar_painel.py` (o livro válido e materializado) · `ci/tests/test_uma_casa_para_o_precisa_de_voce.py`.

## O clone principal é espelho, não bancada (desde 26/08/2026)


Duas sessões dividindo a pasta principal já apagaram o trabalho uma da outra
(26/08/2026 — uma trocou o ramo, as edições da outra sumiram). Desde então a
regra do RITOS §1 (worktree por agente) tem muralha mecânica: os hooks de
`.claude/settings.json` chamam `ci/muralha_pasta_compartilhada.py`, que RECUSA
no clone principal qualquer edição e qualquer git que mude estado
(switch/checkout/reset/commit/stash/...). Se a recusa 🧱 aparecer, não é
defeito e não se contorna: crie seu worktree —
`git fetch origin && git worktree add ../wt-<area>-<tarefa> -b
agent/<area>/<tarefa> origin/main` — e trabalhe lá. No principal ficam livres
leituras, `git fetch`, `git worktree` e `gh`; com a árvore limpa, também
`git switch main` e `git pull` (para manter o espelho fresco). Detalhes e
fronteiras: `armadilhas/135`.

**E desde 05/09/2026 o espelho se põe em dia sozinho, na abertura da sessão.**
Decisão do mantenedor, em pergunta estruturada, depois de medirmos o preço do
desenho anterior: a pasta dele estava **758 commits atrás**, e como os ganchos
são lidos do `.claude/settings.json` DAQUELA pasta, o gancho do
`ci/padrao_de_trabalho.py` — mergeado em 04/09 — **nunca rodou uma única vez na
máquina dele**. Todo mecanismo novo nascia inerte, em silêncio
(`armadilhas/343`). Avisar a idade e esperar que um leigo lembrasse de digitar
`git pull` era garantia sem mecanismo com outro nome.

O `--aviso` agora avança a pasta, e **só quando é seguro**: no clone principal,
no ramo `main`, com a árvore limpa de arquivos versionados. Fora disso ele não
encosta — e DIZ por que não encostou, com o número do atraso na tela. O avanço
é `merge --ff-only`, que se recusa a fazer qualquer coisa além de andar para a
frente; arquivo não versionado sobrevive. A busca na rede é melhor esforço: sem
internet, ele alcança o que o cache já sabia em vez de desistir.

**A defasagem de uma sessão é dita na cara, não escondida:** o `CLAUDE.md` do
prompt e os ganchos da sessão que dispara a atualização já foram lidos antes
dela. Quem colhe tudo novo é a conversa seguinte. O agente continua proibido de
atualizar o espelho por conta própria.

**Quem faz valer:** `ci/muralha_pasta_compartilhada.py`, ligado como hook em `.claude/settings.json` · `ci/tests/test_muralha_pasta_compartilhada.py` (inclusive o guarda que exige a janela do gancho MAIOR que os tetos internos dos dois `git`, para o harness nunca matar um merge no meio e deixar um `index.lock` na pasta dele).

## O agente pede pouso; quem mergeia é a pista (desde 29/08/2026)


Decisão do mantenedor em 22/08/2026 tirou o merge das mãos dele (motivos em
`docs/decisoes/DECISAO-merge-pelo-agente.md`); decisão dele em 29/08/2026
(registro `20260829-006`) tirou o merge das mãos do AGENTE e o entregou à pista.
Lei: `CONSTITUICAO.md` Lei 4 (com a emenda); rito: `RITOS.md` §2 peças 4 e 5.
**O que não mudou: ninguém espera por ele.** Quem mergeia continua sendo
máquina — mudou qual, e a nova tem paciência.

O fluxo, sem perguntar nada:

1. PR aberto dentro do escopo de um despacho → leia o número que o `gh`
   devolveu e **embarque o registro no mesmo ramo** (`painel/registros/`,
   citando o número — molde em `painel/LEIA-ME.md`; PR que só escritura é
   isento).
2. **UM comando, pela ferramenta `Monitor`, e vá embora** (desde 03/09/2026):

   ```bash
   python ci/esperar.py --checks <N> --teto 20 --dizendo "os checks do PR <N>" --e-pousar
   ```

   Ele espera os checks UMA vez e, ao ficarem verdes, passa pelo MESMO portão
   (`ci/mergear.py <N> --pousar`) e pede o pouso sozinho. Vermelho, estouro ou
   medição impossível nunca viram pedido. **Não deixe o pedido de pouso para
   um passo seu depois:** em 03/09/2026 o rito tinha três passos, a sessão
   acabou entre um e outro, e o mantenedor passou horas esperando um pouso
   que esperava por ele. `--conferir` e `--pousar` à mão continuam existindo
   para depurar, não como caminho normal.
3. A pista atualiza com a `main` de agora, confere pelo MESMO portão e
   mergeia; ela comenta no PR o que aconteceu (pousou, devolveu, ou está
   esperando). O registro aterrissa junto — depois do pouso não fica devendo
   nada ao livro. **No relatório final, diga com todas as letras que nada mais
   depende de ninguém** e quanto a fila costuma levar (8 min de mediana): o
   mantenedor não distingue "o robô está esperando" de "o robô está
   trabalhando", e uma frase solta o deixou esperando um dia inteiro.
4. Se o merge toca `services/` ou `infra/`, o veredito do run de deploy
   (seção "Depois de todo merge que dispara deploy") — esse é registro NOVO,
   pós-merge, porque só existe depois mesmo.

`--confirmo` **recusa** para quem não é a pista, e a recusa ensina o caminho.
Vermelho, pendente, ausente ou ERROR **nunca** vira pedido de pouso — conserte
ou reporte. O botão de merge do site não é caminho para ninguém. Merge em
caminho CODEOWNERS (`contracts/`, `pagamentos`, `checkout`, `infra/`, `ci/`,
`.github/`, arquivos-lei da raiz) só com mandato do despacho, e **anunciado
nominalmente no relatório final**.

**A pista é a única porta, e é opt-out só para emergência** (desde 29/08/2026):
antes dela o agente insistia — atualizar, esperar 90s de checks, a `main` andar,
repetir. Medido: oito voltas num PR de 4 arquivos (`armadilhas/156`). Hoje esse
laço não existe mais, porque o agente não fica na corrida: ele pede pouso e sai.
Os três desfechos possíveis e a mecânica da pista: `RITOS.md` §2 peça 5.

**Vários despachos em paralelo (lote):** a sessão raiz rege pelo
`RUNBOOK-LOTES.md` — composição, as sete regras de inteligência, janela de
merge serial e fechamento. Se o mantenedor pedir "toque um lote", é esse
documento que define o como.

Se o livro não tiver um `tipo` adequado para o que aconteceu, registre com o
tipo mais próximo (`nota` serve para quase tudo) e anote no detalhe — mudar o
vocabulário de tipos é mudança em `painel/logica.js`, por PR, com teste-guarda.
A capa do painel tem teto de blocos e se RECUSA a crescer: realidade nova entra
como registro, não como seção nova.

**Quem faz valer:** `ci/mergear.py` (recusa `--confirmo` para quem não é a pista) · `.github/workflows/pouso.yml` · `ci/tests/test_mergear.py`.

## Como trabalhar com o mantenedor (vale para TODA sessão)


O dono do projeto é leigo em código e em terminal, e lê SOMENTE português —
**toda resposta em PT-BR, sempre**. O resto foi aprendido a custo alto em
21-22/08/2026, no dia em que a plataforma subiu (ele quase desistiu do projeto
no meio dos passos manuais):

- **Faça você o máximo.** Tudo que der por `gh`, pipeline e arquivos, o agente
  faz — o mantenedor só entra onde é insubstituível (segredos, console do
  provedor; desde 22/08/2026 nem o merge: ele é do agente, seção acima).
  Agente não tem SSH para a VPS (Lei 5) e o harness bloqueia a tentativa —
  não insista; o canal do agente é o pipeline.
- **Quando sobrar passo manual, entregue UM bloco único de colar**, fail-closed
  (que se recusa a agir se algo estiver estranho, com uma mensagem tipo "PAROU
  POR SEGURANÇA"), nunca uma sequência de comandos avulsos para digitar um a um.
- **Diga SEMPRE em qual janela colar.** A confusão mais repetida da história do
  projeto: rodar comando do PC dentro da VPS e vice-versa. Regra de bolso que
  funcionou: linha começando com `PS C:\>` = PC; começando com `deploy@srv...`
  ou `root@srv...` = já está DENTRO da VPS (não use `ssh` aí).
- **Avise as surpresas de terminal antes delas acontecerem**: senha invisível ao
  digitar, silêncio = sucesso, a diferença entre `>>` (acrescenta) e `>` (apaga).
- **Reporte em linguagem de resultado** ("a plataforma está no ar"), não de
  processo — e marcos merecem ser celebrados. O ânimo do mantenedor é parte da
  infraestrutura do projeto.
- **Qualquer coisa pendente nele ao fechar uma tarefa ou uma conversa vira
  pergunta estruturada ali mesmo — nunca uma frase solta esperando que ele
  digite uma resposta livre.** Use `AskUserQuestion` (ou equivalente) com cada
  opção traduzida para português simples — o porquê e a consequência prática
  de cada lado, sem jargão cru ("evento ou HTTP" vira "os números podem
  demorar alguns segundos, ou precisam ser sempre exatos?") — e marque a
  opção recomendada quando houver uma. Vale para decisão técnica real E para
  algo tão simples quanto agendar uma conversa futura ("quer que eu explique
  agora, prefere um resumo primeiro, ou fica para depois") — a régua não é
  "isto é grande o bastante para virar pergunta", é "isto ia deixar ele
  compondo uma resposta livre". Se ele fechar a pergunta sem responder, é
  "não agora": pare e espere, não repita a mesma pergunta.
  **Confirmado com força por ele em 25/08 e reforçado em 27/08/2026** — na
  segunda vez, depois de eu fechar um relatório com "isso vai precisar de uma
  conversa sua quando puder" em vez de abrir a caixa ali mesmo; ele reagiu
  pedindo por essa "caixa que aparece pedindo a resposta" em vez do texto
  cair na caixa de digitar dele. A regra virou instrução permanente dele
  também em `~/.claude/CLAUDE.md` (todo projeto, toda conversa) — este
  parágrafo é a camada específica do sitesdoreino, que soma à de lá.
  **Em lote (RUNBOOK-LOTES.md):** quem fala com ele é a sessão-maestro, nunca
  os despachos individuais — um despacho que topa com algo do mantenedor
  registra e devolve à maestro (RUNBOOK-LOTES.md §7, Lote 3 lição 11), e é a
  maestro quem consolida numa única pergunta estruturada. Sem essa regra, um
  lote de 5 despachos em paralelo viraria 5 caixas de pergunta simultâneas.

## O que você entrega para ele mora no site (desde 05/09/2026)

Decisão dele, com as palavras dele: *"Você consegue colocar esse artefato em uma
página do site? E sempre criar isso no site ao invés de artefatos?"*. Lei
completa em `docs/decisoes/DECISAO-onde-mora-o-que-eu-entrego.md`.

**Toda entrega que ele vai ler mais de uma vez nasce dentro de
`meshcraft.top`**, nunca como página solta fora do site. Análise, relatório,
plano, comparação, painel: se ele vai voltar nisso, tem endereço no site.

A pergunta que decide ONDE é uma só: **isto se apoia em fatos que o sistema já
conhece?**

- **Sim** (votos, alunos, tarefas, dinheiro, estado de qualquer coisa): é uma
  **tela calculada** em `/admin/`, com teste. Nunca um documento com os números
  escritos dentro, que é fotografia e começa a mentir no dia seguinte. O padrão
  é **fato vivo mais julgamento guardado**: o texto de análise fica no código, os
  números vêm da fonte a cada abertura (exemplo vivo:
  `services/admin/apps/core/analise_da_caixa.py`, aba `/admin/caixa/analise/`).
- **Não** (plano, lei, explicação, roteiro): vai para o **editor de documentos**
  em `/admin/documentos/`, que ele edita sem pedir nada a ninguém.
- **Para IA de fora ler**: `/mapa-ia/planos/`, que já era lei.

Continua valendo mandar **arquivo na conversa** (uma prévia, uma captura) e
**texto curto direto na resposta**: prévia não é entrega, e o que cabe em dez
linhas não precisa de página. O que não vale é a entrega definitiva morar fora
do site.

**O caminho inverso é a mesma lei, e já foi confundido: documento que ELE envia
é ordem de serviço, não conteúdo para arquivar (desde 06/09/2026).** Aconteceu
assim: ele mandou três documentos do curso dizendo que eles instruem os robôs a
construir o que ainda não existe; a sessão leu os três, transformou UM em
trabalho na fila e publicou o resto como página, e ele teve de corrigir à mão —
"IMPORTANTISSIMO: o que eu quero não é apenas ENVIAR os documentos para o site"
(`armadilhas/362`). A pergunta que decide é uma só: **"se eu só guardar isto, o
que ele pediu passa a existir?"** Texto do livro indo para a Biblioteca: sim,
guardar É a obra. Documento descrevendo curso, agente, tela ou fluxo que ainda
não existe: não — e aí o rito é o de obra, sempre:

1. **Inventário**: tudo que o documento diz que precisa EXISTIR (telas, fluxos,
   agentes, conteúdo, integrações), em lista.
2. **Diff com a realidade**: o que já está no ar e o que falta — olhando o
   código e o site, nunca a memória.
3. **O que falta vira tarefa na fila** (RITOS §5), uma por pedaço independente,
   citando o documento de origem — a fila sobrevive à sessão; conversa
   arquivada, não.
4. **E o despacho começa na mesma sessão**, pela lei "Todo pedido do mantenedor
   é um lote": tarefa na fila não é adeus, é linha de partida.
5. **A página com o documento é subproduto** (o mapa do que falta), nunca a
   entrega. O relatório final diz o que passou a EXISTIR, o que foi despachado
   e o que só ele pode dar — este último em pergunta estruturada.

**Quem faz valer:** ninguém, mecanicamente — a lei está declarada em
`ci/leis-sem-mecanismo.txt`. Um portão que adivinhasse "isto devia ser uma tela"
reprovaria trabalho honesto e deixaria o descuido passar.

## Este projeto é para ser feito completo — nunca proponha a versão minimalista


Decisão do mantenedor em 25/08/2026 (lei completa, com as palavras dele:
`docs/decisoes/DECISAO-filosofia-de-escopo.md`): **entre uma opção completa/robusta
e uma reduzida/rápida, a completa é a escolha padrão — mesmo custando mais tempo,
mais PRs, mais sessões dele.** Não é ingenuidade sobre custo: é decisão informada,
depois de outros projetos dele terem falhado por seguir justamente o conselho de
"comece pequeno e rápido".

Na prática:

- **Nenhum agente — nem uma "banca" convocada para dar segunda opinião —
  recomenda escopo reduzido como forma de economizar tempo ou esforço.** Pode
  registrar a análise; a recomendação final não escolhe uma opção só por ser
  mais barata.
- **Não use "isso vai levar dias/semanas" para desencorajar ambição.** O
  mantenedor já viu, na prática, robôs deste projeto fazendo em minutos o que
  esse vocabulário sugere levar semanas — não avalie por cronograma de equipe
  humana.
- **Isto não é desculpa para descuido.** PRs pequenos, orçamento de 15
  arquivos, Ritos de Contrato, evidência vermelho→verde —
  nada disso muda. Fatiar em fases seguras não é reduzir escopo, é a forma
  responsável de construir algo grande. "Completo" é o destino; a escada de
  PRs é o caminho.
- **Bloqueio real continua sendo bloqueio real** — custo de serviço pago,
  credencial que só ele tem, limite legal, vulnerabilidade de segurança. Isso
  é fato sobre o que é possível, não "conselho de ir devagar", e continua
  reportado como sempre (`ARMADILHAS-OPERACAO.md` §1).

## Nenhum texto publicado sai com travessão (desde 30/08/2026)


Decisão do mantenedor em 30/08/2026: **todo texto escrito para ser publicado
online sai sem travessão.** No lugar dele entram vírgula, parênteses,
dois-pontos ou aspas. A escolha depende do papel que o travessão fazia na
frase, e é de quem escreve:

- **Vírgula (troca neutra)** — explicação comum no meio da frase, que mantém a
  leitura fluida e natural. `O motorista — que estava muito cansado — parou no
  posto.` vira `O motorista, que estava muito cansado, parou no posto.`
- **Parênteses (menor destaque)** — dado puramente acessório, que pode ser
  ignorado sem perda. `A inflação — principal vilã do orçamento — voltou a
  subir.` vira `A inflação (principal vilã do orçamento) voltou a subir.`
- **Dois-pontos (fechamento)** — quando o trecho isolado fica no FIM da frase e
  serve de esclarecimento ou conclusão. `Ele só queria uma coisa — paz.` vira
  `Ele só queria uma coisa: paz.`
- **Aspas (diálogo)** — quando o travessão marcava fala de personagem.
  `— Não quero ir hoje — disse Pedro.` vira `"Não quero ir hoje", disse Pedro.`

**A troca é uma REESCRITA, não um caractere trocado.** Esta é a metade da lei
que faltava, e ela custou uma dúzia de frases ruins publicadas no site antes de
o mantenedor apontar o erro em 30/08/2026. A régua não é "sumiu o travessão": é
**a frase ficou em português correto do Brasil**. Se a troca mais próxima
deixar a frase torta, a resposta é reescrever, não aceitar a torta.

**O erro que já aconteceu, para ninguém repetir:** dois-pontos **não** separa o
verbo do seu complemento, nem abre uma oração que continua direto o pensamento
anterior. Quando o trecho depois do travessão é continuação direta (começa por
`é`, `são`, `não`, um imperativo), dois-pontos quebra a frase:

```
travessão:  Modelo pela metade também conta — é vendo o meio do caminho…
ERRADO:     Modelo pela metade também conta: é vendo o meio do caminho…
certo:      Modelo pela metade também conta, pois é vendo o meio do caminho…
certo:      Modelo pela metade também conta: afinal, é vendo o meio do caminho…
```

A saída é **vírgula com conectivo** (`pois`, `porque`, `e`, `mas`), ou um
**ponto final** quando o que vem depois é uma frase nova (`Nada foi criado.
Tente de novo.`), ou dois-pontos **com** palavra de transição (`: afinal,`).

**Onde dois-pontos está certo, e continua:** lista de definição
(`**Aluno**: você entra normalmente`), enumeração seguida de síntese
(`…o que está pronto: isso é calculado`), anúncio do único item
(`tem uma forma só: a situação Ex-aluno`) e rótulo antes do conteúdo.

**A régua final, em uma pergunta:** leia a frase em voz alta. Se você tropeçar,
a troca está errada, ainda que o travessão tenha sumido.

Contam como travessão as três riscas longas (`—`, `–`, `―`) e as formas
escritas em HTML que viram risca na tela (`&mdash;`, `&#8212;` e parentes). O
**hífen continua livre**: ele é letra de palavra composta ("guarda-chuva"), não
pontuação de frase — um portão que o caçasse recusaria português correto.

**Título de aba usa barra vertical, não uma das quatro.** Em `<title>` e em
`{% block titulo %}` o travessão não era pontuação de frase: era separador entre
a página e o nome do lugar (`Cadastro — Meshcraft`). Nenhuma das quatro trocas
encaixa ali, e o mantenedor escolheu a barra em 30/08/2026, depois de ver a
proposta de parênteses: **`Cadastro | Meshcraft`**. A barra vale SÓ para
separador de título; dentro de uma frase, as quatro continuam sendo a régua.
Não "conserte" isto de volta para parênteses.

**Onde a regra vale:** em tudo que alguém que não é o mantenedor lê. A vitrine
do site, cadastro, login, checkout, quiz, fórum, área do aluno, Caixa de
Sugestões, os documentos publicados e as traduções. A superfície é DERIVADA, não
listada à mão: toda pasta `templates/` de toda célula, toda `traducoes/` e
`documentos/`. Célula nova, ou tela nova numa célula que já existe, entra
sozinha — mapa mantido à mão envelhece em silêncio, e é a Classe 8 do
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.

**Onde ela NÃO vale:** o bastidor do mantenedor (o painel e as telas de
administração), que sai por lista curta em `ci/texto-publico-bastidor.txt`, uma
linha por tela e com o motivo escrito; e o que nunca é publicado — este
arquivo, as armadilhas, os documentos internos e os comentários dentro do
código. O portão DESPE os comentários antes de contar (`{% comment %}`, `{# #}`,
`<!-- -->`, `#` de YAML): sem essa poda a dívida medida seria quatro vezes maior
e quase toda falsa, e medir a coisa errada com precisão é como um portão morre.

**Cuidado com a célula `admin`:** ela não é bastidor inteira. As páginas de erro
e a área pública de documentos (`/docs/…`, isenta na porta) moram nela e
continuam sob a regra.

**Onde a regra alcança o código:** três lugares, e os dois últimos entraram em
31/08/2026 (TAR-087, `armadilhas/254`, com mandato do mantenedor porque `ci/` é
caminho CODEOWNERS). Em todos, só as constantes de string contam; docstring e
comentário, não.

1. **A pasta `management/commands/` inteira, de toda célula.** É de lá que sai
   conteúdo que o visitante lê: o nome e a descrição de uma área do fórum, as
   categorias da Caixa.
2. **O RÓTULO de todo `TextChoices`, em qualquer arquivo de célula.** Entra
   sozinho, sem marca e sem lista. Uma linha dessas tem duas metades, e só a
   segunda é interface:

   ```python
   EM_ANALISE = "em_analise", "Em análise"
   #            ^ contrato       ^ o que a pessoa lê no selo
   ```

   A primeira viaja em contrato congelado, migration e banco, e trocá-la é um
   Rito; a segunda sai em `{{ objeto.get_status_display }}` e nunca esteve sob
   régua nenhuma até esta data. Só o rótulo é medido. `migrations/` fica de
   fora: o rótulo lá é fotografia do modelo naquele dia, não a frase viva.
3. **Qualquer arquivo que se declare**, com o comentário `ci:texto-publicado` em
   qualquer linha dele. Aí o arquivo INTEIRO é medido, pela mesma peneira dos
   comandos. É para a cópia de site que não cabe em `Choices`: um dicionário de
   frases escrito para o aluno, como o `EXPLICACAO_DAS_ETAPAS` da Caixa.

**A terceira é opt-in, e a fraqueza está dita na cara:** quem esquecer a marca
fica de fora. Não existe forma mecânica barata para essa classe. Medido em
31/08/2026, varrer toda constante MAIÚSCULA de módulo nas células públicas daria
2758 strings e 94 travessões, quase todos em mensagem de erro que só um
programador lê, e vários no próprio painel de travessões do Admin, que lista as
riscas como DADO. Medir a coisa errada com precisão é como um portão morre. O
que segura a lei é a segunda regra não depender de marca nenhuma, e ela é o caso
comum.

A fronteira já foi estreita demais duas vezes, e nas duas quem achou o buraco
foi o mantenedor olhando o site. Na primeira ela era `semear_*.py`, e
`seed_sugestoes.py` escapava pelo NOME do arquivo. Na segunda ela era só
`templates/`, e os seis rótulos de `Sugestao.Status` viviam em `models.py`, fora
de tudo. Régua que depende de alguém escolher o prefixo certo, ou de o texto
estar na pasta que alguém imaginou, não é régua.

**O limite que fica, e é o mais importante desta lei:** o portão vigia
ARQUIVOS. **Texto que já está gravado no banco ele não vê, e nunca verá.**
Corrigir um semeador NÃO corrige a linha que ele criou, porque `semear_areas` é
`get_or_create` e de propósito não altera o que existe. Foi assim que um
travessão sobreviveu no fórum a uma varredura que se declarou completa: o
mantenedor o viu no site depois de eu reportar tudo limpo (registro
`20260830-051`). Quando mexer no texto de um semeador, pergunte **se aquilo já
foi semeado em produção** — e, se foi, o conserto é uma migração de dados que
casa o texto antigo inteiro (molde em `forum/migrations/0003`). O teste não
avisa: ele roda em banco vazio, onde o `UPDATE` não encontra linha nenhuma.

O rótulo de `TextChoices` NÃO tem esse problema, e a diferença vale saber: o
banco guarda o VALOR (`em_analise`), e o rótulo é montado na hora de desenhar a
tela. Corrigir o rótulo conserta o site na mesma hora, sem migração de dados.

Fica de fora também `painel/ia/`, que sai em `/mapa-ia/` sem porta: é mapa
técnico para uma IA de fora auditar o sistema, e a régua do mantenedor é a
leitura de PESSOAS.

**O que já estava publicado** quando a regra nasceu está em
`ci/travessoes-herdados.txt`, arquivo por arquivo, com a contagem exata. A
catraca é a mesma das outras dívidas da casa: o número declarado é compromisso,
não teto frouxo — crescer reprova, e encolher também reprova até o número novo
aparecer no diff. Texto NOVO nunca nasce devendo.

Na dúvida sobre uma frase, rode `python ci/travessao.py --listar`: ele mostra
frase por frase, com o número da linha. A recusa do portão já traz as quatro
trocas com exemplo, na mesma tela — não é preciso voltar aqui.

**Quem faz valer:** `ci/muralha-do-travessao.sh` → `ci/travessao.py` (roda em
todo PR via `ci/ci.py --apenas muralhas`; fail-closed) · `ci/tests/test_travessao.py`
· e, desde 06/09/2026, NA HORA DA ESCRITA: o gancho `PreToolUse` de
`.claude/settings.json` → `ci/muralha_do_travessao_na_escrita.py` recusa o
Write/Edit que aumentaria os travessões de um arquivo público, com as quatro
trocas na própria recusa — o robô reescreve antes de o texto entrar no arquivo,
não depois de tudo pronto. O que o gancho não vê (escrita por shell, texto já
no banco) continua com o portão do PR · `ci/tests/test_muralha_do_travessao_na_escrita.py`.


## Depois de todo merge que dispara deploy


Merge tocando `services/**` **ou `painel/**`** dispara o `deploy-celula` (a
célula `admin` embute `painel/` no build — registro novo no livro também
conta); tocando `infra/docker-compose.yml`, `infra/traefik/**` ou o próprio
workflow, dispara o `deploy-infra`. **Merge confirmado ⇒ conferir o run
disparado**, na mesma
resposta — o veredito REAL vem de `gh run view <id> --json status,conclusion`,
nunca do exit de um comando com `| tail`/`| head` pendurado (ARMADILHAS §5.10:
já houve falso-verde assim, e os greens históricos do deploy-celula mentiram
até 21/08/2026 — H13). Run vermelho: `gh run view <id> --log-failed` mostra
onde parou; repete-se sem novo merge com `gh run rerun <id> --failed`. Reporte
o veredito ao mantenedor em texto claro — desde 26/08/2026 a `main` tem sim
required checks (`muralhas` e `ci-celula-gate`, H3), mas **nenhum deles olha o
deploy**: ele roda DEPOIS do merge, e ninguém mais vai olhar por você.

**E essa conferência NUNCA se espera em silêncio** (desde 29/08/2026): rode
`python ci/esperar.py --run <id> --teto 20 --dizendo "o deploy da <célula>"`
pela ferramenta `Monitor` — a espera fala sozinha na janela do mantenedor e
morre no teto. Toda espera tem voz e tem teto: RITOS.md §2 peça 6
(`armadilhas/161`).

**Quem faz valer:** `ci/portao_de_deploy.py` (nenhuma imagem sobe sem evidência verde) · `.github/workflows/alarme-main.yml` (abre issue se a `main` fica vermelha) · `ci/muralha_da_espera.py` (espera muda e sem teto é comando recusado).


## Todo pedido do mantenedor é um lote (desde 05/09/2026)


Decisão dele em 05/09/2026, em pergunta estruturada (registro `20260905-013`;
lei em `docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md`). O que ele
quer, nas palavras dele: "quando eu passar aqui uma tarefa, que ela seja
executada por vários agentes e sub-agentes, para mais agilidade, porque hoje as
tarefas demoram bastante". Medido na fila: uma tarefa sozinha leva 19 minutos
de mediana; o que demora é o pedido grande virando 5, 7, 10 tarefas feitas em
série pela mesma sessão, cada uma esperando seus 10 minutos de pista.

**A regra:** a sessão que recebe um pedido dele É a maestro daquele pedido, sem
ninguém precisar dizer "toque um lote". Ela divide o pedido em pedaços
independentes (1 PR = 1 célula, orçamento de 15), dispara um sub-agente por
pedaço com a ficha `despacho`, em paralelo, e mantém em série só o que depende
de outro pedaço. Enquanto os checks de cada PR rodam, o `revisor` lê o diff e o
`escrivao` escreve o registro, a armadilha e o evento da fila. A maestro arma
uma espera por PR (`ci/esperar.py --checks N --e-pousar`, pela `Monitor`),
consolida um placar só e é a única que fala com ele.

**As fichas moram em `.claude/agents/`** (`despacho.md`, `revisor.md`,
`escrivao.md`): o rito fixo está nelas, e o brief leva SÓ a tarefa e as
armadilhas dela. Sub-agente nunca pergunta ao mantenedor e nunca dispara outro
sub-agente: o time é plano, e quem pergunta é a maestro.

O que isto NÃO muda: uma corrente de passos que dependem um do outro continua
em série; a espera da pista continua existindo por PR (ela só deixa de somar);
o `RUNBOOK-LOTES.md` continua sendo o como da regência.

**Quem faz valer:** `ci/tests/test_fichas_de_robo.py` (as três fichas existem, só
usam campos que o harness reconhece, nenhuma pergunta nem dispara sub-agentes, e
o revisor só lê). A divisão do pedido e o disparo em paralelo são julgamento da
maestro, e isso não tem mecanismo: nada no CI vê quantos sub-agentes uma sessão
disparou. Está dito aqui com todas as letras para ninguém tomar o teste das
fichas por garantia da regra inteira.

## Plano na abertura, contas no fecho (desde 05/09/2026)


Pedido do mantenedor em 05/09/2026, com a palavra "urgente" e o motivo escrito:
"eu estou tendo que pedir várias vezes a mesma coisa porque ao final das tarefas
que eu peço aqui para os robôs fazerem eles simplesmente, ao invés de prestarem
contas da tarefa, como qualquer pessoa que acabou de fazer algo naturalmente
faria, eles apenas arquivam as conversas, sem ao menos explicarem o que foi
feito, se realmente foi resolvido o problema".

**A lei já existia e não era obedecida.** É a regra 9 do Padrão de Trabalho
("Como entregar"), na primeira seção deste arquivo. Das onze regras do Padrão
ela é a única cujo cumprimento é observável de fora, e era a única sem ninguém
que a fizesse valer: `ci/padrao_de_trabalho.py` confere que o TEXTO da régua
continua no lugar e **declara na cara que não confere obediência**. Enquanto foi
só prosa, foi obedecida enquanto alguém lembrava — e a medição diz quanto isso
custava: das 40 sessões mais recentes deste projeto, **24 mudaram o mundo e
terminaram sem prestar contas**. A maioria. Quem pagava era ele, uma pergunta
repetida por vez.

**A regra, nas três pontas:**

1. **Na abertura.** Pedido que vai mudar o mundo (editar arquivo, rodar comando
   que altera algo, abrir PR) começa pelo **plano em caixinhas** — um título
   `## Plano` e um `- [ ]` por passo. Ele é vivo: serve para o mantenedor ver
   onde a tarefa está sem perguntar, e para o robô não perder metade do escopo
   no meio do caminho.
2. **Ao fim de cada etapa.** Pedido dele em 05/09/2026, no mesmo dia, com as
   palavras dele: *"quero que toda e cada tarefa mostre um checklist e um
   roadmap claro de onde está e o que ainda precisa ser feito ao final de cada
   etapa, fase, parte, executada"*. O checklist da abertura sumia da tela
   depois de vinte chamadas de ferramenta, e ele não sabia se a tarefa estava
   no passo 2 ou no 5. A regra: **cada etapa fechada termina com o checklist
   inteiro reimpresso e marcado** — `- [x]` no que caiu, `- [ ]` no que falta —
   e a linha `Onde estou: passo N de M`, com o próximo passo dito. Não é um
   segundo documento: é o MESMO checklist do plano, atualizado. "Etapa" é um
   passo do próprio plano; tarefa de um passo só tem uma etapa, e o fecho a
   cobre.
3. **No fecho.** O turno que mudou o mundo termina com a prestação de contas,
   nesta ordem, e ela é o formato da regra 9 com os dois blocos que ele pediu
   em 05/09/2026. **Ela começa pelo checklist no estado final** (todo `- [x]`
   quando PRONTO; o `- [ ]` que sobrou, com o motivo, quando NÃO PRONTO;
   PRONTO com caixa aberta é contradição, e o portão recusa), e segue com os
   seis blocos:

   - **O que mudou** — fatos, não adjetivos
   - **O que foi verificado e como** — o comando e a saída real, não a promessa
   - **O que foi cortado e por quê** — "nada" é resposta, e é comum
   - **O que eu preciso decidir** — se nada depende dele, a linha que diz isso
   - **Auditoria de qualidade** — a Definição de Pronto (regra 6) item a item, e
     o que o crítico mais implacável do mundo (regra 8) atacaria neste trabalho
   - **Veredito:** PRONTO ou NÃO PRONTO, com UMA linha dizendo por quê

**O veredito é a linha mais importante do relatório**, e existe porque o
mantenedor é leigo em código: o que ele precisa saber, antes de tudo, é se
acabou. **NÃO PRONTO é resposta honesta e aceita** — o portão a aceita de
propósito. Um portão que só aceitasse PRONTO ensinaria o robô a mentir, que é a
doença que ele veio curar.

**Isto não briga com a costura 3 do Padrão** ("nada além dele" proíbe
enchimento, não o que esta casa exige que seja dito). Os dois blocos novos são
exigência dele, da mesma data, e cabem no mesmo lugar: a auditoria é onde a
regra 6 e a regra 8 finalmente aparecem na tela em vez de morrerem na cabeça do
robô.

**Onde o portão CALA, e por que isso é metade do desenho:** turno que só leu,
pergunta respondida, e — principalmente — os turnos em que o harness reacorda o
robô para dar notícia de uma espera. Medido no transcript da sessão que motivou
esta lei: de 232 mensagens de "usuário", **225 eram `<task-notification>`**. Um
portão que cobrasse relatório em cada acordar pediria 225 relatórios, e o
mantenedor aprenderia a ignorar todos. O discriminador não é adivinhação de
texto: é o campo `origin.kind` de cada entrada do transcript.

**A dívida atravessa as falas dele — e essa foi a correção mais cara, no mesmo
dia.** A primeira versão só olhava para o que aconteceu DEPOIS da última fala
do mantenedor. Ele mandou a tela que provou o erro: a sessão abriu o PR #1092,
mergeou, e ficou esperando o deploy; no meio disso ele respondeu uma pergunta
("deixe assim: só admin pode ver, ler"); e a partir dali não houve mais
nenhuma mudança no mundo. A dívida do trabalho já feito tinha sido apagada
porque **ele digitou uma frase**, e a conversa ia ser arquivada com
"Aguardando." como última palavra.

A regra certa é a de qualquer dívida: **ela se paga com o relatório, nunca com
o devedor falando outra coisa.** Por isso a varredura é da SESSÃO inteira: a
última mudança contra a última prestação de contas.

**O que foi tentado e NÃO funcionou, escrito para ninguém refazer:** adiar a
cobrança até "não haver mais nada em voo", para o relatório sair com o veredito
do deploy dentro. O sinal não existe de forma confiável — medido no transcript
real daquela sessão, **4 tarefas de fundo tinham terminado** (o `✅` do
desfecho está lá) e **nenhuma recebeu a notificação com
`<status>completed</status>`**. Um portão apoiado nisso ficaria mudo justamente
no caso reclamado. Sinal que some sem avisar não vira guarda.

**O que sobra, dito na cara:** a cobrança cai no fim do turno que FEZ o
trabalho, e não depois do deploy. O veredito do deploy continua sendo obrigação
de texto (seção "Depois de todo merge que dispara deploy"), sem mecanismo.

**O que o portão NÃO mede, dito na cara:** que a prestação de contas seja
verdadeira. Nenhum portão barato mede "isto foi mesmo verificado". O que ele
torna impossível é o SILÊNCIO — os seis blocos aparecem, o checklist marcado
aparece, o veredito fica em cima da mesa, e quem lê consegue cobrar. Mentira
escrita é falsificável; ausência não é. O plano de abertura também só é
exigido, nunca bloqueado: no fim do turno ele já não tem conserto, e travar o
robô por algo irreparável só produz um robô travado. **O checklist ao fim de
cada etapa (ponta 2) está na mesma situação, e é dito aqui para ninguém tomar o
portão do fecho por garantia dele:** "etapa" não existe para a máquina, e um
portão que contasse reimpressões por chamada de ferramenta cobraria checklist
a cada `ls`. O que o `Stop` mede é a ponta 3: o relatório final SEM caixinha é
recusado, PRONTO com `- [ ]` aberta é recusado, e a recusa ensina as três
pontas. O que ele NÃO distingue é o checklist do plano colado no fim com tudo
marcado sem que nada tenha sido feito: isso é mentira escrita, falsificável,
e fica para quem lê. A ponta 2 fica na lei, no aviso de
abertura (`--plano`) e na memória do robô — sem mecanismo, declarado.

**Quem faz valer:** `ci/prestacao_de_contas.py` (o gancho `Stop` recusa o fim do turno que mudou o mundo sem os seis blocos e sem o checklist marcado; o `UserPromptSubmit` exige o plano na abertura) · `ci/tests/test_prestacao_de_contas.py`. O checklist ao fim de cada etapa em si não tem mecanismo, e está dito acima com todas as letras.
