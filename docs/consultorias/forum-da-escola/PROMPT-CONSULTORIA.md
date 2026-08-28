# Prompt para consultoria externa — O FÓRUM DA ESCOLA

> **Como usar:** copie tudo o que estiver **abaixo da linha** e cole numa outra
> IA (GPT, Gemini, outro Claude, Fable...). Uma IA por conversa nova, sempre o
> texto inteiro. Salve a resposta nesta mesma pasta como `resposta-<IA>.txt`.
> Instruções completas da rodada: `LEIA-ME.md`, ao lado deste arquivo.

---

Preciso de uma segunda opinião honesta e técnica sobre **como construir um fórum
de discussão excelente para uma escola online** — para os alunos, para os
professores e para quem administra — dentro de um sistema que já existe e que
tem restrições incomuns.

Quero que você **questione minhas premissas**, não que me elogie. Se achar que o
caminho que eu descrevo está errado, diga com todas as letras e proponha outro.
Uma crítica bem fundamentada vale mais para mim do que uma confirmação.

## Quem sou eu e como este projeto funciona

Sou o dono e **não sou programador**. Não escrevo código e não leio código. Todo
o trabalho é feito por **agentes de IA** (Claude Code) que eu despacho com
instruções escritas: eles criam ramos, escrevem o código, rodam os testes, abrem
a proposta de mudança, **aprovam e publicam sozinhos**. Eu leio painéis e
respondo perguntas. Não há revisor humano lendo o código antes de ele ir ao ar.

O ritmo não é o de uma equipe humana: num dia recente saíram 5 frentes em
paralelo, 7 publicações e nenhuma reversão; em 48 horas o projeto andou cerca de
90 entregas. **Não me avalie com cronograma de equipe humana**, e não estime em
semanas.

## O produto

Uma plataforma de cursos online. A escola em destaque hoje é a **Meshcraft
Academy**: ensina **criação 3D para Roblox** — modelagem, texturização,
publicação de itens e experiências dentro do Roblox. O público é
majoritariamente **jovem** (adolescentes e pré-adolescentes, com pais pagando),
o que traz consequências reais de segurança, moderação e privacidade que eu
quero que você leve a sério.

O site está no ar em **três idiomas** (português do Brasil, inglês e espanhol) e
o idioma padrão mora na raiz do endereço.

## O que existe hoje, tecnicamente

Preciso que você entenda isto, porque é o que torna o meu caso diferente do
"instale um fórum" que você já respondeu mil vezes.

**A arquitetura.** O sistema é feito de **12 serviços isolados** — chamamos cada
um de "célula". Cada célula é um projeto **Django (Python)** autônomo, com o
**seu próprio banco de dados** e o seu próprio contrato de API. Todas rodam em
contêineres numa única VPS Linux, atrás de um roteador de tráfego (Traefik) que
decide, **pelo caminho do endereço**, qual célula responde: `/alunos` vai para
uma, `/checkout` para outra, `/admin` para outra. Um fórum entraria como
`/forum`.

O isolamento entre células **não é convenção, é permissão de banco**: a senha de
uma célula literalmente não consegue abrir o banco de outra. Existe um único
servidor PostgreSQL 17, com um banco e um usuário por célula, e um Redis
compartilhado para filas e eventos.

**O login já está resolvido, e é aqui que mora a maior armadilha da sua
resposta.** Existe uma célula só de identidade: entrada pelo Google, e a sessão
vive num **cookie assinado** que vale para o site inteiro. Outras células
descobrem quem é a pessoa **repassando esse cookie**, sem entendê-lo, para uma
**API interna** protegida por uma senha própria de cada par de células. Essa API
responde: está autenticado? qual o id? qual o nome? — e, para quem tem permissão
extra, o e-mail.

**Isso NÃO é um provedor de login padrão de mercado.** Não é OIDC. Não é OAuth2.
Não é SAML. Não é LDAP. É uma API interna caseira. **Qualquer fórum de prateleira
que você recomendar vai precisar de uma ponte construída à mão** — e o tamanho
dessa ponte é uma das coisas que eu quero que você calcule, não que estime por
alto.

**As categorias de pessoa são lei escrita**, com uma porta única que responde a
pergunta "esta pessoa é aluna?": visitante (sem login), cadastrado (tem login,
não comprou), na fila (pediu acesso, aguardando), aluno (matrícula válida) e
administrador (lista de e-mails, e é ortogonal — não é o topo de uma escada).

**Professor não existe ainda.** É uma ausência deliberada e registrada: o papel
"nasce com a escola, que é quem sabe o que é uma turma". **Eu já decidi que ele
nasce agora, com o fórum** — veja a seção de decisões abaixo.

**Já existe uma caixa de avisos central** (um "sininho") que qualquer célula pode
usar para entregar notificação a uma pessoa.

**E existe algo que é quase um fórum.** Uma célula chamada Caixa de Sugestões
está em produção e tem: tópicos com categoria, votos com trava de um voto por
pessoa, **comentários**, estados de moderação, uma lista de moderadores por
configuração, limite de velocidade contra abuso, histórico que não pode ser
adulterado (garantido pelo banco) e avisos que caem no sininho. Ela foi
construída em cerca de 97 arquivos. Não é um fórum — é um quadro de sugestões —
mas é a prova de que este time consegue construir esse tipo de coisa, e é um
molde pronto para copiar.

**Nunca houve fórum, comunidade, bate-papo ou qualquer discussão sobre isso neste
projeto.** É terreno virgem: nenhuma decisão anterior te amarra.

## As quatro decisões que JÁ SÃO MINHAS — não as reabra

Estas eu já tomei. Você pode dizer que discorda e por quê **em uma linha cada**,
mas não gaste a resposta redesenhando-as, e não me devolva como pergunta:

1. **O fórum é misto: áreas abertas e áreas trancadas.** Algumas seções são
   públicas — qualquer visitante lê, e o Google indexa, porque dúvida respondida
   é a melhor porta de entrada gratuita que uma escola tem. Outras seções são só
   para quem comprou, trancadas por curso ou por turma.
2. **O papel de professor nasce junto com o fórum**, com autoridade de verdade:
   resposta com selo, poder de marcar uma dúvida como resolvida, poder de
   moderar sem ser dono do sistema.
3. **Não existe comunidade nenhuma hoje.** Não temos Discord, não temos grupo de
   WhatsApp, não temos nada. O fórum nasce em **salão vazio**.
4. **Faço a versão completa, não a reduzida.** Veja a restrição 7.

## RESTRIÇÕES DURAS — leia antes de recomendar qualquer coisa

Se a sua recomendação violar alguma delas, ela é inútil para mim. Pode
argumentar contra uma restrição, mas argumente — não a ignore.

1. **Nenhum agente de IA tem acesso ao servidor pela porta de trás (SSH).** Não é
   proibição, é inexistência: eles não têm a chave, e a ferramenta bloqueia a
   tentativa. **A única forma de algo mudar no servidor é pela esteira automática
   de publicação**, disparada quando uma entrega é aprovada. Eu, humano, consigo
   entrar no servidor e colar um comando — mas isso é caro, é raro, erra muito
   (já falhou três vezes seguidas num passo só) e não pode ser rotina. **Se a sua
   recomendação exige que alguém entre no servidor toda vez que o fórum precisar
   ser atualizado, diga isso em voz alta — é provavelmente fatal aqui.**
2. **A máquina é pequena, já está ocupada — mas eu topo trocá-la.** É uma VPS
   Hostinger do plano KVM 1: **1 núcleo de processador, 4 GB de memória**, 50 GB
   de disco e 4 TB de franquia de tráfego. Nela já rodam **24 contêineres**: as
   12 células, o roteador de tráfego, o PostgreSQL, o Redis e 9 processos
   auxiliares. Medido no painel do provedor em 28/08/2026: **processador em 50%**
   de forma sustentada, **memória em 35%**, disco em 12 dos 50 GB, tráfego
   praticamente zerado.
   **Leia esses dois números com atenção, porque eles apontam para lados
   diferentes:** sobra memória (65% livre), e **falta processador** — 50% de um
   único núcleo, com o fórum ainda nem instalado.
   E o mais importante para a sua recomendação: **quando for necessário, eu subo
   para o plano KVM 2** (2 núcleos, 8 GB de memória, 100 GB de disco). Ou seja,
   **o tamanho da máquina não é um teto rígido — é uma questão de custo mensal.**
   Não descarte uma boa solução só porque ela não cabe na máquina de hoje: diga
   que ela exige a máquina maior, e diga se vale a pena. O que **não** se resolve
   trocando de plano é a restrição 1, que é sobre acesso, não sobre tamanho.
3. **Nada de serviço pago, nada de SaaS, nada de mensalidade.** O repositório é
   privado num plano gratuito. Fóruns hospedados (Circle, Mighty Networks,
   Discourse hospedado) estão fora. Se você acha essa decisão errada, argumente —
   mas dê também a resposta que respeita a restrição.
4. **Nada pode depender de disciplina diária minha.** Eu não modero fila todo dia,
   não arrasto cartão, não preencho formulário. Qualquer desenho em que eu sou a
   engrenagem vai falhar — eu durmo, e o spam não.
5. **Nada pode depender de disciplina do robô.** Toda regra que ficou só "escrita
   no documento" neste projeto acabou violada por uma sessão sob pressão. **Boa
   recomendação é a que RECUSA, não a que PEDE.**
6. **Eu leio somente português e não entendo jargão cru.** Sigla sem tradução,
   para mim, é ruído. Escreva para mim — o robô que vai executar entende o resto.
7. **Não recomende "comece pequeno" ou "faça uma versão mínima para economizar
   tempo".** É regra firme e informada deste projeto: entre a opção completa e a
   reduzida, escolho a completa, mesmo custando mais tempo e mais sessões.
   Fatiar a construção em etapas seguras é bem-vindo; **cortar escopo por pressa,
   não.** Se algo for genuinamente inviável ou perigoso, diga que é inviável —
   isso é fato, não é o conselho que estou recusando.
8. **Assunto fora desta consulta:** cobrança e pagamento estão deliberadamente
   pausados por decisão minha. Não desenhe fórum pago, assinatura de comunidade
   nem nível de acesso por plano.

## A pergunta do Discourse — quero ela respondida de frente

Eu li que o **Discourse** cabe em pouca memória quando há poucos usuários, e
gostei dele. Um agente me contestou. **Na discussão, ele errou um número a meu
favor e acertou um ponto que nenhum de nós tinha visto** — quero o seu veredito,
não uma diplomacia entre os dois:

- **O que o agente errou:** ele calculou com 2 GB de memória, porque foi o número
  que eu passei. **São 4 GB, e só 35% estão em uso.** Existe folga de memória
  real. O argumento "não cabe por falta de memória" ficou bem mais fraco do que
  ele apresentou — e some de vez se eu trocar de plano.
- **O que ele acertou, e que eu não tinha olhado:** o gargalo aqui não é memória,
  é **processador**. É **um único núcleo**, já em **50% de uso sustentado** sem
  fórum nenhum instalado. O Discourse traz servidor web em Ruby mais uma fila de
  tarefas em segundo plano, e os dois disputam processador.
- **O que continua de pé, e não se resolve com dinheiro:** a forma canônica de
  instalar e **atualizar** o Discourse é rodar o instalador dele **dentro do
  servidor** — colisão frontal com a restrição 1. Trocar de plano não muda isso.
- **A favor dele:** o Discourse é o único fórum de prateleira cujo mecanismo de
  login externo (DiscourseConnect) é simples o bastante para a minha célula de
  identidade implementar sem virar um provedor OAuth2 inteiro.

**Responda diretamente: o Discourse entra ou não entra aqui?** E responda a
versão difícil da pergunta, não a fácil: **se eu subir para 2 núcleos e 8 GB, o
Discourse passa a valer a pena?** Quero a comparação honesta entre "pagar mais
por mês e ganhar um produto maduro" e "rodar no que já existe com uma solução
que se atualiza sozinha". Se ele não entra nem assim, diga o que morre junto —
o que eu perco de concreto ao construir em vez de instalar.

## O leque que eu enxergo — critique, corte e acrescente

Não me devolva esta lista organizada; me diga qual caminho seguir e por quê.

**A) Instalar um fórum pronto ao lado, como programa separado.** Discourse
(Ruby), NodeBB (Node), Flarum (PHP, mas exige MySQL e eu só tenho PostgreSQL),
Misago (Python/Django, mesma tecnologia da casa, comunidade pequena). Ganho um
produto maduro de graça; pago em memória, numa segunda tecnologia dentro de
casa, na ponte de login feita à mão e no atrito com a restrição 1.

**B) Instalar um motor de fórum DENTRO de uma célula Django.** O `django-machina`
é uma biblioteca que se instala com um comando e já traz fóruns, tópicos,
respostas, permissões, moderação, anexos e busca — rodando no mesmo processo, no
mesmo banco e na mesma esteira de publicação que todo o resto. Não briga com
nenhuma restrição. **Quero que você avalie honestamente se esse projeto está vivo
o suficiente para eu apostar nele**, e o que acontece comigo se ele parar de ser
mantido daqui a dois anos.

**C) Construir a célula do fórum na casa**, copiando o molde da Caixa de
Sugestões, que já tem 70% das peças em produção. Controle total, casa perfeita
com o login e com as categorias de pessoa; pago reconstruindo coisas que o mundo
já resolveu (busca boa, editor de texto, anti-spam, e-mail de resposta).

**D) Algo que eu não enxerguei.** Um híbrido, um caminho diferente, uma peça
pronta que se encaixa em B ou C.

## O que eu chamo de "super fórum" — o escopo que quero que você ataque

Estas são as capacidades que eu quero. Diga quais são essenciais, quais são
armadilha, quais faltam, e — importante — **quais dessas cada opção do leque te
dá de graça e quais teriam que ser construídas de qualquer jeito**:

1. **Formato da conversa.** Pergunta-e-resposta com "melhor resposta" marcada
   (estilo Stack Overflow) ou conversa linear (estilo fórum clássico)? Ou os
   dois, dependendo da seção? Numa escola, qual funciona melhor — e por quê?
2. **Autoridade do professor.** Resposta com selo visível, poder de marcar a
   dúvida como resolvida, poder de fixar e de corrigir. Como isso não vira
   "professor vira administrador"?
3. **"Mostre seu trabalho".** Numa escola de criação 3D isto é o coração: o aluno
   quer postar o modelo, o print, o vídeo curto — e receber crítica. Isso exige
   anexo de imagem e vídeo, e talvez um visualizador 3D dentro da página. Como
   fazer isso sem estourar disco e sem virar porta de entrada de arquivo
   malicioso?
4. **Encontrar a dúvida já respondida.** A busca é o que decide se um fórum de
   escola vira patrimônio ou lixeira. O que é busca boa aqui, sem serviço pago?
5. **As áreas públicas precisam ser boas para o Google** — endereço limpo, página
   rápida, conteúdo legível sem login. É a minha aposta de crescimento.
6. **Celular em primeiro lugar.** O público é jovem; a maioria vai entrar pelo
   telefone.
7. **Reputação, conquistas, progresso.** Vale a pena numa escola? Ou vira
   competição tóxica entre adolescentes?
8. **Moderação e anti-spam com público menor de idade.** Fila de aprovação,
   denúncia, palavra proibida, bloqueio. O que precisa existir **antes** do
   primeiro post público, não depois do primeiro problema?
9. **Notificações.** Já existe um sininho central no site. O fórum deve usá-lo ou
   ter o próprio? E e-mail: quanto é útil e a partir de onde vira spam?
10. **Três idiomas.** O fórum é um só com conteúdo misturado, ou um por idioma?
    O que menos machuca uma comunidade que ainda vai nascer?
11. **Amarrar a dúvida à aula.** O aluno está no minuto 7 da aula 3 e trava. A
    dúvida deveria nascer dali, com contexto, e voltar para a aula depois de
    respondida. Isso vale o custo?
12. **O salão vazio.** Esta é a que mais me preocupa. Um fórum sem ninguém
    **parece abandonado e afasta quem chega**. Não tenho comunidade nenhuma para
    migrar. O que se faz nos primeiros 90 dias para o fórum não nascer morto — e
    o que disso é mecanismo, e não força de vontade minha?

## As perguntas que quero que você responda

Responda na ordem, com franqueza e priorizando. Prefiro uma recomendação forte e
justificada a cinco fracas.

1. **Qual caminho — A, B, C ou D — e por quê?** Comece por aqui, na primeira
   linha, sem rodeio. Se a resposta for "depende", diga do que depende e qual é
   a sua aposta com a informação que você tem.
2. **O Discourse entra ou não entra?** Veja a seção dedicada acima. Quero conta
   de memória e uma resposta sobre a atualização sem acesso ao servidor.
3. **Qual é o tamanho real da ponte de login?** Para o caminho que você
   recomendar, o que exatamente precisa ser construído para que a pessoa que já
   entrou no site esteja logada no fórum, sem uma segunda senha e sem um segundo
   cadastro? E como isso falha quando falha?
4. **Do escopo de 12 itens acima, o que é essencial no primeiro dia público, o
   que espera, e o que é armadilha** que parece boa ideia e envenena uma
   comunidade de escola? Justifique os cortes — lembrando a restrição 7: cortar
   por pressa não vale, cortar porque **faz mal** vale.
5. **O salão vazio.** Qual é o desenho, mecanismo por mecanismo, que faz um fórum
   novo de escola atravessar os primeiros 90 dias sem parecer deserto? Quem
   escreve o primeiro conteúdo? O que acontece automaticamente quando ninguém
   responde uma dúvida em 48 horas?
6. **Segurança e moderação com menores de idade.** O que é obrigatório antes de
   abrir, o que a lei brasileira exige de uma escola que hospeda conteúdo de
   adolescente, e o que se faz com dado pessoal que vaza em um post público?
7. **Qual é o modo de falha do que você propuser?** Descreva concretamente como
   isso apodrece daqui a um ano — comunidade tóxica, fórum deserto, biblioteca
   que ninguém acha, sobrecarga de moderação em cima de mim — e que **mecanismo**
   (não que boa intenção) impede o apodrecimento.
8. **O que você vê que eu não perguntei?** Pontos cegos, riscos, e as coisas que
   costumam matar fóruns de comunidade educacional.

## Como quero a resposta

- **Em português**, direta e priorizada. Comece pela sua escolha entre A, B, C e
  D — não me faça caçar a sua posição.
- **Discorde explicitamente** onde discordar, inclusive das minhas quatro
  decisões, em uma linha cada.
- Toda recomendação precisa ser **executável por um agente de IA escrevendo
  arquivos no repositório e publicando pela esteira automática**. Se depender de
  alguém entrar no servidor, de ferramenta paga, ou de alguém vigiando todo dia,
  **diga isso na hora**, para eu já descartar.
- **Prefira mecanismos que recusam a regras que pedem.** Para cada coisa que você
  recomendar, responda numa linha: *o que exatamente acontece quando alguém tenta
  fazer errado?* Se a resposta for "está escrito na regra que não pode", eu já
  sei que não funciona aqui.
- Se citar um produto, uma biblioteca ou um método, diga **quem o usa na prática,
  em que escala**, e o que ele custa quando aplicado errado.
- **Nada de plano por fases com prazos em semanas.** Diga o que fazer e em que
  ordem; aqui o tempo se mede em dias.
