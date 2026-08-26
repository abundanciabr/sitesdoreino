# Resposta da consultoria — PAINÉIS DE ACOMPANHAMENTO
### Consultor: Claude (Fable 5) · 25/08/2026 · resposta ao prompt de `PROMPT-CONSULTORIA-PAINEIS.md`

---

## Veredito em três linhas

A reforma aponta na direção certa, mas mira um grau ao lado do alvo. **O problema
não é ter seis painéis; é ter três verdades.** Consolidar num painel único ajuda,
mas o que cura a doença é outra coisa: **uma única fonte de registros, da qual toda
tela é apenas uma vista calculada** — e essa fonte morando no lugar onde as travas
do projeto conseguem protegê-la. Se você fizer o painel único sem essa fundação,
em três meses terá um painel-10X maior.

Há **três discordâncias explícitas** nesta resposta, marcadas com ⚡. Leia-as antes
de aprovar a obra.

---

## 1. A premissa está certa?

**Meio certa.** Consolidar, sim. Mas repare no que o seu próprio sintoma diz: a
lista "precisa de você" existe em três lugares. Isso não é um problema de
*quantidade de painéis* — é um problema de *duplicação de dados*. Se você fundir
os seis painéis num só, mas dentro dele a mesma informação continuar sendo escrita
em duas seções por dois agentes diferentes, a doença volta dentro do painel único.

Sobre o terceiro caminho que você citou (manter painéis separados + um índice com
regras de dono): **você já testou esse caminho, e ele não funcionou.** O cardápio
de painéis É um índice. Índice responde "onde olhar"; não responde "qual dos três
está dizendo a verdade". Não volte a ele.

A resposta certa tem duas camadas, nesta ordem de importância:

1. **Fonte única de registros** (ver pergunta 5 — é a recomendação central desta
   consultoria): cada acontecimento do projeto vira UM registro pequeno, escrito
   uma vez, num lugar só. Nenhum fato mora em dois lugares.
2. **Painel único como consequência**: o hub de três andares vira só o
   *renderizador* dessa fonte. Aí sim ele é a resposta certa — porque deixou de
   ser possível ele divergir de si mesmo.

O medo do "painel gigante que ninguém termina de ler" é legítimo, mas se resolve
na capa por exceção (pergunta 6), não voltando aos seis painéis.

**E uma boa notícia que o seu prompt não menciona: metade dessa arquitetura o
projeto já provou.** Desde 23/08 o painel da fundação é exatamente isso — um HTML
que é só renderizador, lendo um arquivo de dados (`painel-dados.js`) carregado por
`<script src>`. A reforma não parte do zero; ela generaliza um padrão que já
funciona na sua pasta.

⚡ **Discordância 1 — agentes editando o HTML do painel é a raiz da fragilidade.**
Hoje "atualizar o painel" significa um agente editar HTML na mão (ou strings de
HTML dentro de um `.js`, que dá no mesmo). Isso mistura *o que aconteceu* com
*como mostrar*, e faz cada atualização ser uma pequena cirurgia num arquivo grande
— exatamente o tipo de edição que duas sessões paralelas colidem fazendo. Na
reforma: o agente que termina uma tarefa **não edita o painel; ele acrescenta um
arquivo de registro novo** (um arquivo pequeno por acontecimento — o mesmo padrão
que vocês já adotaram nas armadilhas, pelo mesmo motivo). O HTML vira código
estável, que muda raramente e por PR, como qualquer código.

---

## 2. O corte por público é o melhor eixo?

**Sim para o primeiro corte — e vale entender POR QUE funciona**, para não achar
que é gosto: os seus três andares coincidem com *frequência de consulta* (a capa
você abre todo dia; a sala de máquinas, quando algo estranha; a memória,
raramente). Quando o corte por público e o corte por frequência apontam para o
mesmo desenho, o desenho está certo. Se não coincidissem, eu mandaria trocar.

Mas o eixo muda dentro de cada andar:

- **Andar 1 (capa): organize por PERGUNTA, nesta ordem** — (1) o que precisa de
  mim? (2) o que quebrou? (3) o que mudou? (4) como estamos indo? A caixa de
  entrada vem ANTES do placar: placar é conforto, caixa é ação. Se só uma coisa
  couber na primeira dobra da tela, que seja a caixa.
- **Andar 2 (máquinas): por frente de trabalho** (os faróis e o kanban já fazem
  isso).
- **Andar 3 (memória): por tempo**, do mais recente ao mais antigo.

---

## 3. Qual é o modo de falha desta reforma?

O cenário concreto, daqui a três meses: as seções cujos registros dependem de um
agente *lembrar* de escrevê-los param de ser alimentadas nas sessões apressadas.
As seções ficam paradas **com cara de atuais** — que foi exatamente a morte do
painel 10X. O hub não muda essa mecânica por si só; ele só faz o cadáver ficar
maior e mais central.

Três mecanismos (não intenções) que mudam a mecânica:

1. **Selo de frescor CALCULADO, nunca escrito.** Cada registro carrega data/hora;
   a página compara com o relógio *no momento em que você a abre* e desbota a
   seção sozinha, com a denúncia escrita ("esta seção não recebe registro há 12
   dias"). O ponto fino: mentir passa a exigir **fraude ativa** (forjar uma data)
   em vez de **esquecimento passivo** (não escrever). Esquecimento é o modo de
   falha natural de agente sob pressão; fraude ativa é raro e a auditoria pega.
   Você já contratou o selo de frescor na sua lista de 13 — o que estou
   acrescentando é: ele só funciona se for *computado pela página*, jamais um
   texto que alguém escreve.

2. **A trava no rito que já existe.** Vocês já têm um portão de merge
   (`mergear.py`) e um robô de conferência (CI) que recusa PR sem certas coisas —
   já se faz isso com as lições das armadilhas. Estenda: **PR de trabalho sem o
   seu arquivo de registro correspondente é recusado.** Aí "esquecer o painel"
   deixa de ser possível, porque o caminho falha fechado. Isso exige a
   discordância 2 abaixo.

3. **Registros escritos por máquina para os fatos que mais importam.** Merge e
   publicação (deploy) podem ser registrados **pelo próprio robô do GitHub**, sem
   passar por agente nenhum: uma pequena automação que, a cada merge/deploy,
   acrescenta o arquivo do evento com o resultado real. Registro que nenhuma
   inteligência escreve é registro que não apodrece e não mente.

⚡ **Discordância 2 — "os painéis ficam fora do controle de versão" está errado
para os DADOS.** Mantenha o HTML fora do Git se quiser; mas **os registros devem
morar no repositório**, por três motivos que são mecanismo, não preferência:
(a) o registro **viaja dentro do próprio PR** que fez o trabalho — zero cerimônia
extra, e o robô de conferência pode exigi-lo (mecanismo do item 2 acima; fora do
Git, nenhuma trava alcança os dados); (b) histórico automático de graça — a sua
restrição 4 ("o que precisa sobreviver tem que ser registrado em outro lugar")
deixa de existir por desenho; (c) o desempate entre sessões paralelas passa a ser
feito pela máquina de merge que vocês já operam todos os dias. O seu painel
continua abrindo por duplo clique exatamente como hoje: o repositório está no seu
disco, e a página lê os registros dali mesmo. **Nada muda para você; muda quem
protege os dados.**

Um detalhe técnico que o agente construtor PRECISA saber (senão a primeira versão
nasce quebrada): página aberta por duplo clique (`file://`) no Chrome **não
consegue "buscar" arquivos** `.json` — uma regra de segurança do navegador
bloqueia. A solução é a que o painel da fundação já usa: dados em arquivos `.js`
carregados por `<script src>`. Como serão muitos arquivos de registro, um script
(igual ao que gera o índice das armadilhas) mantém um **manifesto** — o
arquivo-lista que diz à página quais registros existem. O agente roda o script; o
robô de conferência confere que o manifesto está em dia.

Sobre a aposentadoria dos 6: faixa e link não bastam — o hábito reabrirá o painel
antigo e lerá o conteúdo velho abaixo da faixa. **Lápide de verdade:** o arquivo
antigo passa a conter SÓ a faixa ("aposentado em DATA, o painel vivo é este") e
redireciona sozinho para o hub em poucos segundos. E troque os pontos de entrada:
o atalho/favorito do seu navegador e as menções nos documentos de despacho — o
ponto de entrada real é o atalho, não o arquivo.

---

## 4. Como manter honesto um painel escrito pelos próprios agentes?

O medo é justo, e as suas duas defesas (evidência crua + auditoria por outra
sessão) são boas — **e insuficientes**: as duas ainda são a mesma espécie
conferindo a si mesma, e auditoria é disciplina agendada, que é exatamente o que
você disse que não funciona aqui. Acrescente, em ordem de força:

1. **Mude fatos de "relatados" para "MEDIDOS".** Tudo que a página conseguir
   verificar sozinha, na hora em que você a abre, deixa de depender da honestidade
   de quem escreveu. E dá para verificar mais do que parece, sem servidor nenhum:
   - **O site está no ar?** A página carrega uma imagenzinha do próprio site
     (o ícone dele); se carregou, está no ar — medido do SEU Chrome, agora, sem
     depender de registro de ninguém.
   - **O PR foi mesmo mergeado? O teste foi mesmo verde?** Como o repositório é
     público, a página pode perguntar **diretamente ao GitHub**, do seu navegador
     (o GitHub permite isso; o limite — 60 consultas por hora — sobra para um
     painel aberto algumas vezes ao dia). Aí a afirmação do agente e a realidade
     aparecem **lado a lado**, e divergência acende sozinha. Um agente pode
     escrever "mergeei o PR 214"; ele não pode fazer o GitHub confirmar um merge
     que não houve.
   - **Que horas são?** Toda comparação de frescor (pergunta 3) é uma medição.
   O princípio é o mesmo da lição nº 3 da Fase D que vocês já têm: *a prova vem
   de fora*. Só que aplicado ao próprio painel.

2. **Registros de máquina** para merge e deploy (pergunta 3, item 3). O agente
   relata o que quiser; o registro que conta é o que o robô do GitHub escreveu.

3. **Tela que falha fechada.** O formato do registro exige o campo "evidência"
   (endereço do PR, número da execução). Registro sem evidência a página mostra
   em âmbar, carimbado **"não comprovado"**. O agente não precisa ser pego
   mentindo — a omissão se denuncia sozinha, na tela que você lê. É a versão
   visual do fail-closed que vocês já praticam no código.

4. **Separe FATO de AVALIAÇÃO no próprio formato.** "O deploy foi verde
   (evidência X)" é fato; "acredito que a frente está estável" é opinião do
   agente. Hoje os dois se misturam na mesma frase dos relatórios. No registro,
   são campos diferentes; na tela, aparências diferentes. Você passa a saber, a
   cada linha, se está lendo medição ou juízo.

5. **A auditoria vira linha do painel, com selo de frescor próprio.** "Última
   auditoria independente: DATA — resultado", calculada dos registros de
   auditoria. Auditoria que não deixou registro não aconteceu; e quando ela
   atrasar, o painel a denuncia como denuncia qualquer seção velha. Hoje a sua
   auditoria existe, mas nada vigia se ela está sendo feita.

---

## 5. O que falta nas 13 ideias?

Uma recomendação forte, e ela é o alicerce de tudo acima: **o livro de
ocorrências** — um diário do projeto onde só se ACRESCENTA, nunca se edita, um
arquivo pequeno por acontecimento (tarefa concluída, incidente, decisão pedida,
decisão respondida, merge, deploy, auditoria…), e **todas as vistas do painel são
calculadas dele**.

Não é uma 14ª ideia ao lado das outras — é o que faz várias das 13 saírem de
graça, em vez de serem seções mantidas à mão:

- O **changelog** é "os registros dos últimos 7 dias, traduzidos".
- A **linha de incidentes** é "os registros do tipo incidente".
- O **registro de decisões** é "os do tipo decisão".
- As **métricas DORA** e o **gráfico de subida** são contas feitas sobre os
  registros de merge e deploy — ninguém as "atualiza".
- E — o mais importante para o seu pior sintoma — **a caixa "precisa de você"
  deixa de ser uma lista que alguém mantém: ela é calculada** como "todo pedido
  aberto que ainda não tem registro de resposta". Uma lista mantida esquece; uma
  lista calculada **não consegue esquecer** — o pedido só sai da caixa quando
  existir o registro da resposta dele. Três listas divergentes viram impossíveis
  por construção, não por disciplina.

**Quem usa isso na prática:** é o princípio do livro-caixa da contabilidade (há
séculos: lançamento não se apaga, se estorna), do diário de bordo da aviação, e
do próprio Git que sustenta o seu projeto. Em software o nome técnico é *event
sourcing* — mas você não precisa do nome, precisa da regra: **acontecimento se
acrescenta; estado se calcula.**

**O que custa quando aplicado errado (para você vigiar):** (a) o livro cresce
para sempre e a página fica lenta — o antídoto já está contratado na sua lista:
as fotografias datadas funcionam como fechamentos de período (a página carrega o
período atual e abre o passado sob demanda); (b) a lógica que calcula as vistas
precisa estar certa, senão ela esconde sem ninguém mentir — o antídoto está na
pergunta 7, primeiro item.

---

## 6. Quanto mostrar de uma vez?

Regra de ouro: **a capa é calculada por exceção, nunca curada por alguém.** Três
propriedades verificáveis:

1. **Cabe numa tela, sem rolar.** Se não coube, a regra de cálculo está errada —
   não é caso de fonte menor.
2. **Saúde se comprime; só desvio ocupa espaço.** Tudo que está bem vira UMA
   linha ("11 serviços no ar · nada quebrado · nada aguardando você"). A aviação
   chama isso de *cabine escura*: painel apagado = tudo bem; luz acesa = desvio.
   É o desenho certo para um leigo, porque a ausência de alarme é informação, e
   o olho vai direto ao que importa.
3. **Vermelho borbulha.** Problema em qualquer andar aparece na capa
   automaticamente, porque é a REGRA que decide o que sobe — não um agente
   decidindo "se isso te incomoda". Esconder problema de você passaria a exigir
   mudar a regra de cálculo — que é código, que muda por PR, que fica registrado.

Profundidade: a capa mostra a manchete de cada coisa + um "ver detalhes" que leva
ao andar de baixo. Nunca a análise inteira na capa; nunca só um número sem a
frase que o traduz.

**O custo quando se erra a mão** (para calibrar depois de rodando): regra
sensível demais gera *fadiga de alarme* — o fenômeno, conhecido dos hospitais, de
tanta luz acesa que se para de olhar. Se a sua capa passar uma semana com mais de
~5 itens acesos permanentes, o problema é a régua, e ela se ajusta na regra, por
PR, com registro do porquê.

---

## 7. O que você não perguntou

1. **Quem vigia o vigia da tela.** Você perguntou como manter honestos os
   *dados*; não perguntou quem confere a *lógica que calcula as vistas*. Um erro
   nela esconde problema sem ninguém ter mentido — e é o único componente novo
   desta reforma que ninguém está vigiando. Antídoto: a lógica mora no
   repositório com **testes-guarda** (o padrão que vocês já dominam): dado de
   exemplo entra → capa esperada sai; um registro de pedido sem resposta →
   OBRIGATORIAMENTE acende a caixa. Quebrar de propósito e ver ficar vermelho,
   como a lei do projeto já exige para todo o resto.

2. **O OneDrive é um risco silencioso debaixo de tudo.** O repositório inteiro
   vive dentro da pasta sincronizada do OneDrive. Duas sessões paralelas
   escrevendo + um sincronizador de nuvem = risco real de "cópia em conflito"
   criada em silêncio — um segundo arquivo, quase igual, que ninguém pediu. Um
   arquivo por registro reduz muito a chance de colisão; registros no Git dão o
   desempate. Mas fica registrado: vale uma conversa separada, fora desta
   reforma, sobre o repositório morar fora da pasta sincronizada. Não decida
   agora; apenas não deixe ninguém te dizer que esse risco não existe.

3. **O seu tempo de resposta também é parte do sistema.** A caixa de entrada
   deve mostrar a **idade** de cada pedido ("aguardando há 3 dias"). Não para te
   culpar — para que pedido velho grite mais alto que pedido novo, e para que os
   agentes vejam o que está travado em você (o gargalo que a Fase D mediu em
   horas era exatamente isso, invisível).

4. **A migração dos hábitos é parte da obra, não acabamento.** Aposentar painéis
   sem trocar atalhos, favoritos e as menções nos documentos de despacho mantém
   os mortos vivos. A lápide com redirecionamento (pergunta 3) + uma varredura
   nos documentos que citam painéis antigos fazem parte do escopo.

⚡ **Discordância 3 — a sua lei anti-proliferação mira o alvo errado.** "Painel
novo é proibido" mira *superfícies*; a doença é *duplicação de fatos*. Uma
segunda vista especializada lendo o mesmo livro de ocorrências é inofensiva — não
pode divergir, é só outra lente. Uma lista mantida à parte é o câncer voltando,
**mesmo que ela more dentro do painel único**. Reescreva a lei assim: *"nenhum
fato do projeto mora em dois lugares; toda superfície nova se calcula do livro de
ocorrências, e superfície que mantém lista própria é proibida"*. Essa lei
continua valendo dentro do hub — que é onde a violação vai tentar acontecer.

---

## Em que ordem construir

Sem prazos, em fatias seguras — escopo completo, como é a regra da casa:

1. **O formato do registro + a pasta de registros no repositório + o script do
   manifesto.** É a fundação de tudo; nada de tela ainda. (Aproveite o molde das
   armadilhas: um arquivo por entrada, índice gerado por script, trava no CI.)
2. **O hub com a capa calculada (andar 1)** lendo os registros — com selo de
   frescor computado e caixa de entrada calculada **desde o primeiro dia**. A
   capa nasce junto com o mecanismo que a mantém honesta, nunca antes.
3. **Migração dos fatos vivos dos 6 painéis** para registros (o conteúdo
   histórico vira fotografias datadas no andar 3 — nada se perde).
4. **Andares 2 e 3.**
5. **As travas:** exigência do registro no rito de merge · registros de máquina
   para merge/deploy · testes-guarda da lógica de cálculo · verificações ao vivo
   na página (site no ar, GitHub).
6. **As lápides + a troca de atalhos + a lei reescrita** (mirando duplicação, não
   superfícies).

A ordem importa por um motivo só: **cada andar nasce já ligado ao mecanismo que o
impede de mentir.** Construir as telas primeiro e "depois a gente põe as travas"
é como o painel 10X nasceu.

---

*Resposta escrita para ser lida ao lado do `cardapio-de-paineis.html` — ela não
repete as 13 ideias contratadas; corrige a fundação sobre a qual elas vão se
apoiar.*
