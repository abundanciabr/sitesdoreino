"""A auditoria da área administrativa — append-only, com trigger no banco.

**Por que ela existe, e por que AGORA:** `DECISAO-celula-admin.md` §3 exige que
toda escrita feita por esta área deixe rastro, e o `LICOES.md` da célula fixou o
momento — *"a auditoria entra no MESMO PR que a primeira escrita, ou num PR
imediatamente anterior a ela; nunca depois"*. Este PR traz a primeira escrita
(liberar e recusar quem está na fila), então ela entra aqui.

**O que esta tabela NÃO é, e a distinção decide o desenho.** Ela não é uma
segunda fonte de "quem é aluno" — esse fato mora na `alunos`, que já grava
`decidido_em`, `decidido_por` e `motivo_recusa` na própria matrícula. Duplicar
aquilo aqui criaria duas listas respondendo à mesma pergunta, que é a doença
que o `CLAUDE.md` proíbe.

O que ela guarda é outra coisa, que nada mais responde: **o que foi feito
ATRAVÉS desta área, por quem, e o que aconteceu** — inclusive as tentativas que
FALHARAM. Uma decisão que a `alunos` recusou não deixa rastro nenhum lá (não há
linha para carimbar), e é justamente esse caso que alguém vai querer reconstruir
quando um aluno disser "eu fui liberado e continuo sem acesso".

**Append-only com MECANISMO, não com disciplina** (`armadilhas/079`): o
`save()` sobrescrito é contornado por `QuerySet.update()`, por `psql` e por
qualquer código que não importe esta classe. Quem impede de verdade é o trigger
da migration `0001` — as três metades (UPDATE, DELETE e TRUNCATE) fechadas no
banco.
"""

from django.db import models


class Registro(models.Model):
    """Uma linha por AÇÃO tentada nesta área. Nunca editada, nunca apagada."""

    LIBERAR = "liberar"
    RECUSAR = "recusar"
    # [GESTAO] Mudar o estado de quem JÁ é aluno, ou corrigir os dados dele.
    # Verbo próprio, e não um `liberar` reaproveitado: quem for ler esta tabela
    # daqui a meses precisa distinguir "deixei entrar" de "mexi no cadastro".
    EDITAR = "editar"
    # [ADMINS/APAGAR] Verbos próprios, 28/08/2026. Cada gesto que muda a vida de
    # alguém tem o seu: quem ler esta tabela em meses precisa distinguir
    # "mexi no cadastro" de "dei poder de administrador" e de "apaguei a ficha".
    PROMOVER = "promover"
    DESPROMOVER = "despromover"
    APAGAR = "apagar"
    # [CAIXA] A gestao das ideias dos alunos mudou de casa para esta area em
    # 28/08/2026 (DECISAO-a-gestao-da-caixa-mora-no-admin). Verbos proprios pelo
    # mesmo motivo dos de cima — e um deles nao muda a vida de um aluno, muda a
    # de um projeto inteiro: ASSINAR autoriza uma obra a comecar.
    #
    # A Caixa ja guarda o que MUDOU (historico append-only). O que esta tabela
    # acrescenta, e que nenhuma outra guarda, e a tentativa RECUSADA: quando a
    # Caixa diz nao, nada e escrito la, e sem esta linha o gesto nao teria
    # deixado rastro em lugar nenhum.
    # [A MAO] 29/08/2026: o mantenedor pode pôr alguém na escola sem esperar a
    # pessoa pedir. Verbo próprio pelo mesmo motivo dos de cima — "liberei quem
    # pediu" e "cadastrei alguém que não pediu" são gestos diferentes, e quem
    # ler esta tabela em meses precisa saber qual dos dois aconteceu.
    CADASTRAR = "cadastrar"
    # [RECUSADOS] 02/09/2026: o mantenedor volta atrás numa recusa e aceita a
    # pessoa. Verbo PRÓPRIO, e não um `LIBERAR` reaproveitado, porque é o único
    # gesto desta área em que ele desfaz uma decisão dele mesmo — e a pergunta
    # que se faz a estas linhas ("quantas vezes eu voltei atrás, e sobre quem?")
    # não se responde lendo os `liberar`, que são milhares e falam de gente que
    # nunca foi recusada.
    #
    # UMA linha no caminho feliz, e não duas — a mesma disciplina do CADASTRAR
    # acima, que também é um gesto de dois passos: o `detalhe` conta a viagem
    # inteira ("voltou para a fila e foi liberada"), e uma linha por salto
    # encheria a tabela de metades que ninguém consulta separadas. O passo que
    # FALHA é que ganha linha própria, porque aí os dois desfechos são
    # diferentes e a diferença é exatamente o que alguém vai querer reconstruir.
    RECONSIDERAR = "reconsiderar"
    MOVER_IDEIA = "mover_ideia"
    AVALIAR_IDEIA = "avaliar_ideia"
    ASSINAR_OBRA = "assinar_obra"
    # [ARQUIVAR] 29/08/2026 (`DECISAO-arquivar-ideia.md`). Verbo próprio, e não
    # `APAGAR` reaproveitado: aquele já nasceu para a ficha do aluno (e está
    # aposentado desde `DECISAO-a-ficha-nao-se-apaga.md` — o verbo fica no
    # vocabulário só para linhas antigas continuarem legíveis, nenhum caminho
    # novo o escreve); arquivar é reversível, e quem ler esta tabela em meses
    # precisa distinguir os dois gestos.
    ARQUIVAR_IDEIA = "arquivar_ideia"
    DESARQUIVAR_IDEIA = "desarquivar_ideia"
    # [APAGAR-IDEIA] 29/08/2026 (`DECISAO-apagar-ideia.md`). De novo um verbo
    # PRÓPRIO, e não `APAGAR`: aquele é sobre a ficha do aluno (aposentado,
    # comentário acima) — este é sobre a ideia, é um alvo diferente, e a
    # mesma palavra "apagar" nos dois criaria ambiguidade sobre QUEM sumiu.
    APAGAR_IDEIA = "apagar_ideia"
    # [FUNDIR] 05/09/2026 (`DECISAO-fundir-ideias.md`). Dois verbos, e não um
    # com um campo dizendo o sentido: juntar e desfazer são gestos com
    # consequências opostas para quem escreveu a ideia absorvida, e quem ler
    # esta tabela em meses precisa distingui-los sem interpretar detalhe.
    FUNDIR_IDEIAS = "fundir_ideias"
    DESFAZER_FUSAO = "desfazer_fusao"
    # [CORRIGIR-IDEIA] 31/08/2026 (`DECISAO-corrigir-o-texto-de-uma-ideia.md`).
    # Verbo próprio pela razão mais forte da lista: a correção é CALADA para o
    # aluno, por decisão do mantenedor. A Caixa guarda o texto anterior de cada
    # campo; o que ESTA tabela acrescenta, e nenhuma outra tem, é a tentativa
    # RECUSADA — quando a Caixa diz não (texto igual, nome vazio, ideia já
    # apagada), nada é escrito lá, e sem esta linha o gesto de mexer no texto de
    # um aluno não teria deixado rastro em lugar nenhum.
    CORRIGIR_IDEIA = "corrigir_ideia"
    # [MENU] 31/08/2026: o menu do topo do site passou a ser configuravel pelo
    # mantenedor (/admin/menu/). Verbo proprio pelo mesmo motivo dos de cima, e
    # com um agravante: o alvo aqui nao e uma pessoa nem uma ideia, e o SITE
    # INTEIRO — o que se muda por esta tela aparece para todo visitante. Uma
    # linha por gesto, inclusive quando o catalogo recusa.
    EDITAR_MENU = "editar_menu"
    # [DOCUMENTOS] 31/08/2026: o mantenedor passou a escrever os documentos do
    # site por uma tela (`DECISAO-o-editor-de-documentos.md`). Verbos proprios
    # pelo mesmo motivo dos de cima, e com o agravante do menu: o alvo nao e uma
    # pessoa nem uma ideia — e um texto que qualquer visitante pode ler.
    #
    # E ha um motivo a mais, que so vale para estes. Ao tirar o texto do Git, a
    # plataforma perdeu o `git log` dos documentos; a auditoria e o historico de
    # versoes sao o que entra no lugar. CRIAR e EDITAR sao separados porque
    # "este texto nasceu hoje" e "este texto mudou hoje" sao perguntas
    # diferentes na hora de reconstruir o que aconteceu.
    CRIAR_DOCUMENTO = "criar_documento"
    EDITAR_DOCUMENTO = "editar_documento"
    # [HISTORICO] 31/08/2026: voltar um documento a uma versao anterior. E um
    # verbo, e nao um EDITAR reaproveitado, porque e o unico gesto desta area
    # que escreve um texto que NINGUEM digitou naquele momento. Confundi-lo com
    # uma edicao esconderia justamente o que aconteceu, e este verbo entra junto
    # com o historico porque ele e metade do que substituiu o `git log` destes
    # textos (`DECISAO-o-editor-de-documentos.md` §6).
    RESTAURAR_DOCUMENTO = "restaurar_documento"
    # [LUGAR] 31/08/2026: os tres gestos que mexem no LUGAR do documento, e nao
    # no texto dele. Separados de EDITAR pela mesma razao que ARQUIVAR_IDEIA nao
    # e APAGAR_IDEIA: quem ler esta tabela em meses precisa distinguir "reescrevi
    # o texto" de "tirei a pagina do ar" e de "destrui o documento".
    ARQUIVAR_DOCUMENTO = "arquivar_documento"
    DESARQUIVAR_DOCUMENTO = "desarquivar_documento"
    APAGAR_DOCUMENTO = "apagar_documento"
    # [ECONOMIA] 31/08/2026: ligar e desligar cada regra de pontuacao da escola
    # (/admin/economia/). DOIS verbos, e nao um "mudar_regra", porque ligar e
    # desligar sao perguntas diferentes na hora de reconstruir o que aconteceu:
    # "desde quando esta regra paga?" e a pergunta que importa quando um aluno
    # estranha o proprio numero, e ela se responde lendo os LIGAR.
    #
    # Este registro e METADE do "anunciado" que a lei §10.5 exige. A outra
    # metade e a `vigente_desde` da propria regra, na celula `gamificacao`: la
    # mora DESDE QUANDO a regra vale, aqui mora QUEM mandou e QUANDO pediu. Sao
    # fatos diferentes, e nenhum e copia do outro — e por isso que esta tela
    # nao guarda copia nenhuma das regras (a lei anti-duplicacao do CLAUDE.md).
    LIGAR_REGRA = "ligar_regra"
    DESLIGAR_REGRA = "desligar_regra"
    # [CONQUISTAS] 01/09/2026: ligar uma MEDALHA ou um MARCO. Verbos proprios, e
    # nao os dois de cima com outro alvo, porque a pergunta que se faz ao
    # historico e diferente: "desde quando esta regra paga?" se responde lendo os
    # LIGAR_REGRA, e "quando a escola passou a reconhecer isto?" se responde
    # lendo estes. Um verbo so obrigaria quem audita a adivinhar pelo slug.
    LIGAR_CONQUISTA = "ligar_conquista"
    DESLIGAR_CONQUISTA = "desligar_conquista"
    # [DEGRAUS] 02/09/2026: ligar um DEGRAU da escada de niveis. Verbo proprio
    # pela mesma razao dos dois de cima, e com uma diferenca que vale registrar:
    # ligar um degrau nao paga nada, e a regua com que o XP ja existente e lido.
    # A pergunta que se faz a estas linhas e "quando a escola passou a chamar
    # alguem de Oficial?", que nao se responde por nenhum dos outros verbos.
    LIGAR_DEGRAU = "ligar_degrau"
    DESLIGAR_DEGRAU = "desligar_degrau"
    # [SENHA] 31/08/2026 (`DECISAO-login-por-senha.md`): o reset manual de
    # senha, pelo prontuário de um aluno. Verbo próprio pelo mesmo motivo dos
    # de cima — e com o agravante de que a senha em si NUNCA entra em
    # `detalhe` nem em lugar nenhum desta tabela (só o hash fica do lado da
    # `identidade`); esta linha registra só QUEM pediu, QUANDO, e para QUAL
    # e-mail, nunca o segredo.
    RESETAR_SENHA = "resetar_senha"
    # [AVISO DE TESTE] 03/09/2026: a pessoa mandou um aviso de teste para o
    # proprio aparelho, para saber se os avisos na tela do celular estao
    # funcionando. Verbo proprio porque a pergunta que se faz a estas linhas e
    # "quantas vezes o mantenedor precisou confirmar o canal?", que nenhum
    # outro verbo responde. Nao muda estado de aluno nenhum: e diagnostico.
    TESTAR_AVISO = "testar_aviso"
    # [APAGAR-RECUSADO] 03/09/2026 (`DECISAO-apagar-recusado-definitivamente.md`).
    # Verbo PROPRIO, e nao o `APAGAR` aposentado em 29/08: aquele era sobre a
    # ficha de um ALUNO (nunca mais acontece, so continua legivel em linha
    # antiga); este e sobre um pedido RECUSADO, que nunca chegou a ser aluno.
    # A mesma palavra "apagar" nos dois confundiria QUAL dos dois era possivel
    # na data em que a linha foi escrita.
    APAGAR_RECUSADO = "apagar_recusado"
    # [SEQUENCIAS] 04/09/2026, a tela `/admin/escola/jornadas/` (degrau 7 do
    # `PLANO-SEQUENCIAS-DE-MENSAGENS.md`). TRÊS verbos, e não um só, porque as
    # perguntas que se fazem a estas linhas são três e nenhuma responde a outra:
    #
    #   · "desde quando a escola manda esta sequência?" (ligar/desligar)
    #   · "quando a mensagem 2 passou a dizer isto, e quem trocou?" (publicar)
    #
    # Ligar e desligar são separados pelo mesmo motivo de `LIGAR_REGRA` e
    # `DESLIGAR_REGRA`: um verbo só, com o estado no `detalhe`, faria a leitura
    # do histórico depender de ler o texto livre de cada linha.
    #
    # `PUBLICAR_TEXTO` é o verbo mais pesado desta tabela e vale dizer por quê:
    # ele muda o que pessoas de verdade vão ler, e do outro lado ele não EDITA
    # nada — publica uma versão nova, imutável por gatilho no Postgres. Então
    # esta linha é a única resposta possível para "quem trocou aquela frase?":
    # a versão antiga continua lá, mas ela não sabe quem escreveu a nova.
    LIGAR_SEQUENCIA = "ligar_sequencia"
    DESLIGAR_SEQUENCIA = "desligar_sequencia"
    PUBLICAR_TEXTO = "publicar_texto"
    # [LIVRO] 04/09/2026: a Biblioteca do Livro (`/admin/livro/`), onde o
    # mantenedor guarda os textos do livro que ele escreve. Quatro verbos, na
    # mesma gramática dos documentos logo acima.
    #
    # A razão de existirem é mais forte aqui do que em qualquer outra tela
    # desta lista: o texto do livro NÃO viaja no Git, porque este repositório é
    # público e o livro não está lançado. Não há `git log`, não há PR, não há
    # revisão. Esta tabela e o histórico de versões são a memória inteira do
    # que aconteceu com uma obra que não tem cópia em outro lugar.
    CRIAR_TEXTO_LIVRO = "criar_texto_livro"
    EDITAR_TEXTO_LIVRO = "editar_texto_livro"
    RESTAURAR_TEXTO_LIVRO = "restaurar_texto_livro"
    APAGAR_TEXTO_LIVRO = "apagar_texto_livro"
    # [LIVRO] 05/09/2026: o `Livro` que agrupa capítulos, nascido junto com a
    # tela de LEITURA. Um verbo só, porque criar é o único gesto que a tela
    # nova do formulário oferece hoje — não há editar nem apagar um `Livro`
    # ainda.
    CRIAR_LIVRO = "criar_livro"
    # [AULAS] 05/09/2026: o editor de encomendas do curso (`/admin/escola/aulas/`,
    # degrau 1.5 do `PLANO-CELULA-CURSOS.md`). Tres verbos, porque as perguntas
    # que se fazem a estas linhas sao tres: "quem mexeu na aula E07, e quando?",
    # "quando a E07 foi aberta para os alunos?" e "quem trocou a escala do
    # cartao de topologia?". Publicar e verbo proprio e nao um detalhe de
    # gravar: gravar sobe a versao e nao muda o que o aluno ve; publicar nao
    # muda uma letra e abre a aula. Sao gestos de pesos diferentes.
    #
    # Como no livro, o texto mora fora do Git (no banco da `cursos`, pela porta
    # de maquina): esta tabela e o historico de versoes da `cursos` sao a
    # memoria inteira de quem escreveu o que. O `detalhe` guarda a versao e a
    # contagem de travessoes, NUNCA o texto: obra nao lancada nao entra numa
    # tabela append-only (a regra do `LICOES.md` sobre a auditoria nao guardar o
    # que a pessoa escreveu vale aqui com mais forca ainda).
    EDITAR_AULA = "editar_aula"
    PUBLICAR_AULA = "publicar_aula"
    EDITAR_INSTRUMENTO = "editar_instrumento"
    ACOES = [
        (LIBERAR, "liberar"),
        (RECUSAR, "recusar"),
        (EDITAR, "editar"),
        (PROMOVER, "promover a administrador"),
        (DESPROMOVER, "remover de administrador"),
        (APAGAR, "apagar de vez"),
        (CADASTRAR, "cadastrar alguem a mao"),
        (RECONSIDERAR, "aceitar quem tinha sido recusado"),
        (MOVER_IDEIA, "mover a ideia de fase"),
        (AVALIAR_IDEIA, "escrever a avaliacao da ideia"),
        (ASSINAR_OBRA, "assinar a obra de uma ideia"),
        (ARQUIVAR_IDEIA, "arquivar a ideia"),
        (DESARQUIVAR_IDEIA, "desarquivar a ideia"),
        (APAGAR_IDEIA, "apagar a ideia definitivamente"),
        (FUNDIR_IDEIAS, "juntar ideias numa so"),
        (DESFAZER_FUSAO, "desfazer a juncao de ideias"),
        (CORRIGIR_IDEIA, "corrigir o texto da ideia"),
        (EDITAR_MENU, "mudar o menu do topo do site"),
        (CRIAR_DOCUMENTO, "criar um documento do site"),
        (EDITAR_DOCUMENTO, "editar um documento do site"),
        (RESTAURAR_DOCUMENTO, "voltar um documento a uma versao anterior"),
        (ARQUIVAR_DOCUMENTO, "tirar um documento do ar, guardando o texto"),
        (DESARQUIVAR_DOCUMENTO, "devolver um documento arquivado"),
        (APAGAR_DOCUMENTO, "apagar um documento definitivamente"),
        (LIGAR_REGRA, "ligar uma regra de pontuacao da escola"),
        (DESLIGAR_REGRA, "desligar uma regra de pontuacao da escola"),
        (LIGAR_CONQUISTA, "ligar uma medalha ou marco da escola"),
        (DESLIGAR_CONQUISTA, "desligar uma medalha ou marco da escola"),
        (LIGAR_DEGRAU, "ligar um degrau da escada de niveis"),
        (DESLIGAR_DEGRAU, "desligar um degrau da escada de niveis"),
        (RESETAR_SENHA, "resetar a senha de um aluno"),
        (TESTAR_AVISO, "mandar um aviso de teste para o proprio aparelho"),
        (APAGAR_RECUSADO, "apagar de vez um pedido recusado"),
        (LIGAR_SEQUENCIA, "ligar uma sequencia de mensagens"),
        (DESLIGAR_SEQUENCIA, "desligar uma sequencia de mensagens"),
        (PUBLICAR_TEXTO, "trocar o texto de uma mensagem automatica"),
        (CRIAR_TEXTO_LIVRO, "guardar um texto novo do livro"),
        (EDITAR_TEXTO_LIVRO, "editar um texto do livro"),
        (RESTAURAR_TEXTO_LIVRO, "voltar um texto do livro a uma versao anterior"),
        (APAGAR_TEXTO_LIVRO, "apagar um texto do livro definitivamente"),
        (CRIAR_LIVRO, "criar um livro novo na biblioteca"),
        (EDITAR_AULA, "gravar uma encomenda do curso"),
        (PUBLICAR_AULA, "publicar uma encomenda do curso para os alunos"),
        (EDITAR_INSTRUMENTO, "gravar um instrumento de avaliacao do curso"),
    ]

    OK = "ok"
    RECUSADO_PELA_CELULA = "recusado"
    NAO_RESPONDEU = "nao_respondeu"
    DESFECHOS = [
        (OK, "ok"),
        (RECUSADO_PELA_CELULA, "recusado pela célula dona"),
        (NAO_RESPONDEU, "não respondeu"),
    ]

    quando = models.DateTimeField(auto_now_add=True)

    # QUEM: o e-mail é o identificador que o mantenedor consegue reconhecer numa
    # auditoria — e ele já é a chave de autorização desta célula
    # (`ADMIN_EMAILS`), então guardá-lo aqui não amplia o alcance do dado. O id
    # opaco vem junto porque e-mail pode mudar de dono numa organização; o id,
    # não.
    quem_email = models.EmailField()
    quem_id = models.CharField(max_length=64, blank=True, default="")

    # 32, e nao 20: `desarquivar_documento` tem 21 caracteres e o Django recusa
    # o modelo inteiro quando a coluna nao cabe a maior escolha. Alargar uma
    # coluna de texto e a metade "expand" do Expand-and-Contract — o codigo
    # anterior continua escrevendo e lendo as mesmas palavras, e nenhuma linha
    # antiga precisa ser tocada. CUIDADO ao mexer aqui: no SQLite isso
    # reconstroi a tabela e derruba os gatilhos (`armadilhas/246`).
    acao = models.CharField(max_length=32, choices=ACOES)

    # SOBRE O QUÊ. `alvo` é o id da linha na `alunos` — um identificador opaco
    # de OUTRA célula, guardado como texto de propósito: não é chave estrangeira
    # e não pode virar uma (Lei 3), e o dia em que aquela linha for embora esta
    # continua contando o que aconteceu.
    alvo = models.CharField(max_length=64)
    # Sem PII do aluno: nem nome, nem telefone. Para saber de quem se trata,
    # cruza-se o `alvo` com a `alunos` — que é onde esse dado mora, e é ela
    # quem decide quem pode vê-lo (lei da fila §5).

    desfecho = models.CharField(max_length=20, choices=DESFECHOS)
    # O que o OPERADOR fez e escreveu — nunca o que a PESSOA forneceu.
    #
    # **A regra vale daqui em diante e tem motivo mecânico**
    # (`DECISAO-administradores-e-apagar` §4): esta tabela é append-only por
    # trigger, e o painel ganhou um botão que apaga uma pessoa de vez. Se o
    # detalhe guardasse nome ou telefone, apagar seria impossível sem furar a
    # própria trava. Então ele guarda os NOMES dos campos tocados, não os
    # valores.
    #
    # O motivo de uma recusa CONTINUA aqui: é texto que o mantenedor escreveu,
    # não dado da pessoa — e sem ele a linha diz "recusou" sem dizer o que a
    # pessoa recusada leu.
    detalhe = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["-quando"])]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.quando:%Y-%m-%d %H:%M} {self.quem_email} {self.acao} {self.alvo}"
