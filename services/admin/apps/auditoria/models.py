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
    # [SENHA] 31/08/2026 (`DECISAO-login-por-senha.md`): o reset manual de
    # senha, pelo prontuário de um aluno. Verbo próprio pelo mesmo motivo dos
    # de cima — e com o agravante de que a senha em si NUNCA entra em
    # `detalhe` nem em lugar nenhum desta tabela (só o hash fica do lado da
    # `identidade`); esta linha registra só QUEM pediu, QUANDO, e para QUAL
    # e-mail, nunca o segredo.
    RESETAR_SENHA = "resetar_senha"
    ACOES = [
        (LIBERAR, "liberar"),
        (RECUSAR, "recusar"),
        (EDITAR, "editar"),
        (PROMOVER, "promover a administrador"),
        (DESPROMOVER, "remover de administrador"),
        (APAGAR, "apagar de vez"),
        (CADASTRAR, "cadastrar alguem a mao"),
        (MOVER_IDEIA, "mover a ideia de fase"),
        (AVALIAR_IDEIA, "escrever a avaliacao da ideia"),
        (ASSINAR_OBRA, "assinar a obra de uma ideia"),
        (ARQUIVAR_IDEIA, "arquivar a ideia"),
        (DESARQUIVAR_IDEIA, "desarquivar a ideia"),
        (APAGAR_IDEIA, "apagar a ideia definitivamente"),
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
        (RESETAR_SENHA, "resetar a senha de um aluno"),
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
