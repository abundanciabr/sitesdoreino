"""O que esta área GRAVA: quem administra, os documentos do site, e o livro.

## Quem é administrador desta área — a metade que mora no banco

**Isto reverte, em parte, a `DECISAO-celula-admin` §2**, que dizia *"derivada e
nunca gravada"*. A reversão é decisão do mantenedor de 28/08/2026, tomada com o
preço na mesa (`DECISAO-administradores-e-apagar.md` §2): com a lista no banco,
passa a ser possível ganhar acesso de administrador **sem tocar no servidor**.

**A lista efetiva é `ADMIN_EMAILS` (do servidor) ∪ os ativos daqui**, e o env
continua sendo o CHÃO. Duas consequências, as duas desejadas:

- **não existe como se trancar para fora**: quem está no env entra sempre, e o
  botão de remover recusa mexer nele — a saída continua sendo o servidor;
- **banco vazio, corrompido ou restaurado de backup não fecha a porta.**

Ver `apps/core/porta.py`, que é quem soma as duas metades — e que trata falha
de banco como "vale só o env", nunca como "deixa entrar".

## Os documentos do site — a mudança de 31/08/2026

Até aqui, um documento era um ARQUIVO em `documentos/`, e o site só o lia. O
mantenedor pediu em 31/08/2026 uma tela para **gerenciar e editar** os
documentos, e essa frase tem uma consequência mecânica que decide o desenho: o
disco do container é remontado a cada atualização da plataforma. Gravar a
edição dele no arquivo embutido a apagaria no deploy seguinte, **em silêncio**.

Por isso o texto passa a morar AQUI, e a pasta `documentos/` vira SEMENTE: ela
é lida uma vez, pela migração que criou estas linhas, e nunca mais. Não são dois
lugares dizendo a mesma coisa (a lei anti-duplicação do `CLAUDE.md`): depois da
semeadura, quem responde "o que este documento diz" é esta tabela, e só ela.
Mesmo desenho de `semear_areas` no fórum.

Lei: `docs/decisoes/DECISAO-o-editor-de-documentos.md`.

## A Biblioteca do Livro — 04/09/2026

Pedido do mantenedor: *"esse texto abaixo é um dos textos de um livro que eu
escrevi e quero uma página no site onde eu possa salvar ele para ser usado
depois no projeto online do livro"*. `TextoDoLivro` é onde esse texto mora.

**Tabela PRÓPRIA, e não uma bandeira no `Documento`, e o motivo é a fresta que
não existe.** Os dois guardam Markdown escrito pelo mantenedor, e a tentação de
somar um campo `e_do_livro` é real. O que a separação compra: `Documento` tem
`publico`, e toda consulta do site aberto passa por ele; um capítulo de livro
guardado naquela tabela ficaria a UM filtro esquecido de aparecer em
`meshcraft.top/docs/`. Aqui não há filtro para esquecer, porque não existe rota
pública que leia esta tabela — o livro dele não está lançado, e o repositório
deste projeto é público de propósito.

**O corpo é guardado como ele digitou, byte por byte.** É a diferença de
propósito entre as duas tabelas: um documento do site é texto de interface, e a
tela dele RECUSA salvar com risca comprida (`DECISAO-o-editor-de-documentos`
§3); um texto de livro é obra do autor, e a Biblioteca não reescreve obra. A
tela CONTA as riscas e mostra as frases — decisão dele em 04/09/2026, com as
três saídas na mesa — e desde 05/09/2026 essa contagem não é mais um aviso
para o futuro: ver `Livro` logo abaixo e o cabeçalho de `apps/core/livro.py`.

## `Livro` — a tela de LEITURA, 05/09/2026

Um `Livro` agrupa capítulos (`TextoDoLivro.livro`). Nasceu no dia em que o
mantenedor pediu uma tela de leitura ("parecido com o leitor da Amazon
Kindle") e respondeu, entre duas opções na mesa, **"os dois: publicar o meu
agora, já preparando para vários depois"** — por isso o modelo já suporta
vários livros, mesmo só existindo um publicado por ora. A migração `0012`
cria um `Livro` para qualquer capítulo pré-existente, e todo capítulo novo
nasce dentro de um `Livro`, sempre.
"""

from django.db import models


class Administrador(models.Model):
    """Um e-mail promovido pela TELA. O do env não passa por aqui."""

    # `unique` para promover duas vezes não criar duas linhas — e para o
    # "remover" ter um alvo só. Guardado sempre em minúsculas: a porta compara
    # normalizado, e uma linha com maiúscula seria uma promoção que não vale
    # nada e que ninguém consegue explicar depois.
    email = models.EmailField(unique=True)
    # Remover é DESATIVAR, não apagar: a linha é o que dá contexto às linhas de
    # auditoria que falam dela, e promover de novo vira uma reativação em vez
    # de uma segunda história.
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["ativo"])]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.email}{'' if self.ativo else ' (removido)'}"


class Documento(models.Model):
    """Um documento que o site publica. A ÚNICA fonte do texto, desde 31/08/2026."""

    class Formato(models.TextChoices):
        """Como o corpo deste documento vira tela. Ver o campo `formato`.

        Dois valores, e não uma lista que cresce: o formato não é um tema nem
        um estilo, é a resposta a UMA pergunta com duas respostas possíveis.
        Quem escreve prosa quer o renderizador que escapa; quem quer desenhar
        uma página inteira quer a folha em branco, e a folha em branco só é
        segura dentro do sandbox.

        Os rótulos aparecem na tela do editor, então são texto publicado: sem
        risca comprida, como manda `ci/travessao.py`.
        """

        TEXTO = "texto", "Texto escrito"
        PAGINA = "pagina", "Página visual"

    # O endereço, e a chave: `como-funciona-a-entrada` sai em
    # `meshcraft.top/docs/como-funciona-a-entrada`. `unique` porque dois
    # documentos com o mesmo nome seriam dois textos disputando um endereço.
    #
    # O formato (minúsculas, números e hífen) é o mesmo `RE_NOME` que a rota
    # exige, e a conferência acontece na borda de escrita, não aqui: um
    # `SlugField` aceita maiúscula e sublinhado, que a rota não casa — um nome
    # assim viraria um documento inalcançável, existindo só na lista.
    nome = models.SlugField(max_length=80, unique=True)
    titulo = models.CharField(max_length=200)

    # FAIL-CLOSED, e este `default=False` é a lei do §2 da
    # `DECISAO-a-area-de-documentos` escrita no banco: documento novo nasce
    # PRIVADO, e sair para o mundo exige um gesto de propósito. Enquanto o
    # texto morava em arquivo, quem garantia isso era a igualdade exata com
    # "true" no cabeçalho; aqui é o default da coluna.
    publico = models.BooleanField(default=False)

    # Menor primeiro. O default alto manda o documento novo para o FIM: um
    # default pequeno o faria pular na frente dos que alguém posicionou.
    ordem = models.IntegerField(default=1000)
    corpo = models.TextField(blank=True, default="")

    # Arquivar tira do site sem destruir o texto (a escolha do mantenedor em
    # 31/08/2026, e o mesmo desenho de `DECISAO-arquivar-ideia`). É por isso que
    # `publico` sozinho não responde "está no ar?": ver `no_ar` abaixo.
    arquivado = models.BooleanField(default=False)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # O CABEÇALHO DE APÊNDICE VIVO (TAR-247, degrau 3.3 do
    # `PLANO-CELULA-CURSOS.md` §3.8). FAIL-CLOSED: `default=False` é o mesmo
    # desenho de `publico` acima — um documento comum não ganha cabeçalho
    # nenhum, e virar apêndice vivo exige um gesto de propósito no editor.
    #
    # As datas ficam NULAS para quem não é apêndice vivo — não há pergunta
    # "verificado quando?" para um documento comum. A borda de escrita (o
    # editor) exige as duas quando a caixa é marcada, e o `CheckConstraint`
    # abaixo é a segunda tranca: recusa a gravação direta pelo modelo, por
    # fora do editor, que é o caminho que `armadilhas/079` ensina a fechar.
    apendice_vivo = models.BooleanField(default=False)
    verificado_em = models.DateField(null=True, blank=True)
    proxima_verificacao_em = models.DateField(null=True, blank=True)

    # O FORMATO (TAR-596, 21/09/2026). Pedido dele: *"o documento pode ser uma
    # página visual inteira, não só texto"*.
    #
    # A saída NÃO foi ampliar o renderizador de Markdown — ele continua
    # escapando o texto inteiro antes de aplicar qualquer regra, e é isso que
    # mantém o `|safe` dos dois templates seguro. O que este campo escolhe é
    # ONDE o corpo é desenhado: `texto` na própria página, pelo renderizador;
    # `pagina` dentro de um `<iframe>` de origem opaca, servido cru pela rota
    # da moldura (`apps/core/documento_em_pagina.py`).
    #
    # `default=TEXTO`, e o default é a regra: todo documento que já existe, e
    # todo documento novo criado sem ninguém pensar nisto, continua passando
    # pelo renderizador que escapa. Virar página é um gesto de propósito no
    # editor, como publicar.
    formato = models.CharField(
        max_length=6, choices=Formato.choices, default=Formato.TEXTO
    )

    class Meta:
        # A pergunta que a área pública faz a cada visita: os que estão no ar,
        # na ordem da lista.
        indexes = [models.Index(fields=["publico", "arquivado", "ordem"])]
        constraints = [
            # Documento comum (apendice_vivo=False) passa livre, com as duas
            # datas do jeito que estiverem. Apêndice vivo EXIGE as duas datas
            # preenchidas, e a próxima verificação sempre DEPOIS da última —
            # a mesma regra que `editor_de_documentos.py` já recusa na tela,
            # aqui como segunda tranca contra escrita direta pelo modelo.
            models.CheckConstraint(
                condition=models.Q(apendice_vivo=False)
                | (
                    models.Q(apendice_vivo=True)
                    & models.Q(verificado_em__isnull=False)
                    & models.Q(proxima_verificacao_em__isnull=False)
                    & models.Q(proxima_verificacao_em__gt=models.F("verificado_em"))
                ),
                name="apendice_vivo_exige_datas_coerentes",
            ),
        ]

    @property
    def no_ar(self) -> bool:
        """Se qualquer pessoa de fora consegue ler isto agora.

        DUAS condições, e a segunda foi acrescentada junto com o botão de
        arquivar. Quem perguntar só por `publico` deixará um documento
        arquivado visível no site — e é exatamente o tipo de esquecimento que
        uma propriedade com nome próprio evita.
        """
        return self.publico and not self.arquivado

    @property
    def endereco(self) -> str:
        """O endereço PÚBLICO deste documento, sem o prefixo da célula."""
        # Importado AQUI dentro, e não no topo do arquivo: `documentos.py`
        # importa este módulo, e um import no topo fecharia o ciclo. O prefixo
        # mora lá porque é lá que está escrito por que ele não sai de
        # `{% url %}` — e uma constante só é o que impede a explicação de virar
        # caminho cravado espalhado por três templates.
        from .documentos import PREFIXO_PUBLICO

        return f"{PREFIXO_PUBLICO}/{self.nome}"

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.nome}{'' if self.no_ar else ' (fora do ar)'}"


class VersaoDoDocumento(models.Model):
    """O retrato de um documento a cada gravacao. Nunca editado, nunca reescrito.

    **Por que ele existe, e por que no MESMO PR do editor.** Ao tirar o texto do
    Git (`DECISAO-o-editor-de-documentos` §6), a plataforma perdeu o `git log`
    dos documentos: nao ha mais como ver quem mudou uma frase, nem como voltar
    atras. Esta tabela e o que entra no lugar, e ela entra junto com a primeira
    escrita — a mesma regra que a auditoria desta celula seguiu na dela, porque
    "a versao anterior" so existe se alguem a guardou ANTES de sobrescrever.

    **Guarda o estado DEPOIS de cada gravacao**, e nao o de antes. As duas
    escolhas descrevem a mesma historia, e esta poe a versao que esta no ar como
    a ultima linha da lista — que e como uma pessoa le um historico. Voltar
    atras vira copiar uma linha antiga por cima do documento, o que grava mais
    uma versao: nem a volta apaga historia.
    """

    documento = models.ForeignKey(
        "Documento", on_delete=models.CASCADE, related_name="versoes"
    )

    # O retrato: os quatro campos que o formulario escreve. `arquivado` fica de
    # FORA de proposito — ele nao e conteudo, e sim onde o documento esta; um
    # historico que misturasse os dois faria "voltar a versao de ontem"
    # significar tambem "e traga-o de volta ao ar", que e outra decisao.
    titulo = models.CharField(max_length=200)
    publico = models.BooleanField(default=False)
    ordem = models.IntegerField(default=1000)
    corpo = models.TextField(blank=True, default="")

    salvo_em = models.DateTimeField(auto_now_add=True)
    # O e-mail de quem salvou, como na auditoria: e o identificador que o
    # mantenedor reconhece numa lista, e ja e a chave de autorizacao da area.
    salvo_por = models.EmailField(blank=True, default="")
    # O que aconteceu, em palavra de gente: "criou", "editou", "voltou para uma
    # versao de <data>". Texto livre de proposito — quem le esta lista e uma
    # pessoa procurando quando algo mudou, nao uma maquina filtrando.
    gesto = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        # A pergunta da tela de historico: as versoes deste documento, da mais
        # nova para a mais velha.
        indexes = [models.Index(fields=["documento", "-salvo_em"])]

    def __str__(self) -> str:  # pragma: no cover - conveniencia de shell
        return f"{self.documento_id} @ {self.salvo_em:%Y-%m-%d %H:%M}"


class Midia(models.Model):
    """Uma imagem ou um vídeo que o mantenedor enviou para dentro de um documento.

    Nasceu em 21/09/2026 (TAR-597), no dia em que ele autorizou a plataforma a
    guardar arquivo no disco da VPS. Até então não havia `FileField` nenhum
    nesta casa, e um documento só podia falar de uma imagem hospedada fora.

    **O arquivo mora no disco e esta linha é o catálogo dele** — não há
    `FileField`, e a ausência é a decisão: um `FileField` guarda o caminho que
    lhe entregaram, e aqui o caminho é montado a partir de duas colunas que a
    borda de escrita escreveu (`sorteio` e `nome`), nunca de texto que veio de
    fora. `apps/core/midia.py` explica a conferência inteira.

    **Presa ao documento**, e não numa biblioteca solta: a pergunta que a tela
    faz é "que imagens este documento tem", e apagar o documento precisa apagar
    os arquivos dele junto — o que uma biblioteca sem dono deixaria órfãos no
    disco para sempre.
    """

    documento = models.ForeignKey(
        "Documento", on_delete=models.CASCADE, related_name="midias"
    )

    # O endereço: 32 dígitos sorteados. É ele que impede o arquivo de uma
    # pessoa de ser encontrado por tentativa, e é ele que substitui o caminho
    # de disco na URL — a rota procura esta coluna e lê o resto do banco.
    sorteio = models.CharField(max_length=32, unique=True)

    # O nome com que o arquivo foi gravado: o apelido aparado do original, com
    # a extensão REESCRITA a partir do tipo lido no conteúdo. O nome que o
    # navegador mandou não sobrevive à passagem.
    nome = models.CharField(max_length=80)

    # O `Content-Type` que NÓS conferimos lendo os primeiros bytes, e o único
    # que a rota devolve. Guardado, e não recalculado a cada leitura, porque a
    # conferência é da hora do ENVIO: é ali que existe alguém para avisar.
    tipo = models.CharField(max_length=32)

    tamanho = models.PositiveIntegerField()
    enviado_por = models.EmailField(blank=True, default="")
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A pergunta da tela do editor: os arquivos deste documento, do mais
        # novo para o mais velho.
        indexes = [models.Index(fields=["documento", "-enviado_em"])]

    @property
    def megabytes(self) -> str:
        """O tamanho do jeito que uma pessoa lê, para a lista da tela."""
        return f"{self.tamanho / (1024 * 1024):.1f} MB".replace(".", ",")

    def __str__(self) -> str:  # pragma: no cover - conveniencia de shell
        return f"{self.sorteio}/{self.nome}"


class Livro(models.Model):
    """Um livro do mantenedor. Um `TextoDoLivro` é um capítulo de um `Livro`.

    Nasceu em 05/09/2026, quando ele pediu a tela de LEITURA (o cabeçalho de
    `apps/core/livro.py` conta a decisão inteira). A resposta dele, entre duas
    opções na mesa, foi "os dois: publicar o meu agora, já preparando para
    vários depois" — o modelo já nasce com um `Livro` por cima dos capítulos,
    mesmo só existindo um hoje.
    """

    slug = models.SlugField(max_length=80, unique=True)
    titulo = models.CharField(max_length=200)

    # Mesmo desenho de `TextoDoLivro.ordem`: menor primeiro, default alto joga
    # o livro novo para o fim da lista.
    ordem = models.IntegerField(default=1000)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["ordem", "slug"])]

    def __str__(self) -> str:  # pragma: no cover - conveniencia de shell
        return self.titulo


class TextoDoLivro(models.Model):
    """Um texto do livro do mantenedor, do jeito que ele escreveu.

    Ver o cabecalho deste arquivo para por que esta tabela e separada de
    `Documento`, e por que o corpo nunca e reescrito.
    """

    # O endereco desta pagina dentro do bastidor: `/admin/livro/<nome>`. Ele
    # nao sai para lugar nenhum de fora, e mesmo assim segue o mesmo padrao
    # apertado (minusculas, numeros e hifen) dos documentos: a rota casa esse
    # formato, e um nome fora dele seria um texto que existe na lista e nunca
    # abre.
    nome = models.SlugField(max_length=80, unique=True)
    titulo = models.CharField(max_length=200)

    # O livro a que este capítulo pertence. Todo capítulo tem um, sempre — a
    # migração `0012` associa qualquer capítulo pré-existente a um `Livro`
    # criado por ela antes de fechar a coluna em `null=False`.
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name="capitulos")

    # Menor primeiro, e o default alto manda o texto novo para o FIM. Num livro
    # a ordem e o sumario: e ela que diz o que vem antes do que.
    ordem = models.IntegerField(default=1000)

    # O MARKDOWN CRU, exatamente como ele colou. Nada aqui e aparado, corrigido
    # ou normalizado na gravacao — a unica troca que a tela faz e o fim de linha
    # do Windows pelo do resto do mundo, porque o navegador manda `\r\n` e o
    # texto colado voltaria com uma risca invisivel a cada linha.
    corpo = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        # A unica pergunta que a lista faz: os textos, na ordem do sumario.
        indexes = [models.Index(fields=["ordem", "nome"])]

    @property
    def palavras(self) -> int:
        """Quantas palavras este texto tem.

        Um autor mede o livro em palavras, e nao em caracteres nem em linhas.
        Contagem grosseira de proposito (separa por espaco): a pergunta que ela
        responde e "de que tamanho isto ficou", nao "quantas palavras cabem na
        pagina impressa".
        """
        return len(self.corpo.split())

    def __str__(self) -> str:  # pragma: no cover - conveniencia de shell
        return self.nome


class VersaoDoTexto(models.Model):
    """O retrato de um texto do livro a cada gravacao. Nunca editado.

    Mesmo desenho de `VersaoDoDocumento`, e pelo motivo mais forte: o texto do
    livro NAO viaja no Git (o repositorio e publico e o livro nao esta
    lancado), entao aqui nao existe nem o `git log` de que os documentos
    abriram mao. Esta tabela e a unica memoria de "o que estava escrito antes",
    e por isso ela nasce no mesmo PR da primeira escrita: a versao anterior so
    existe se alguem a guardou ANTES de sobrescrever.
    """

    texto = models.ForeignKey(
        "TextoDoLivro", on_delete=models.CASCADE, related_name="versoes"
    )

    # O retrato guarda o CONTEUDO, e so ele. `ordem` fica de fora de proposito,
    # como `arquivado` ficou no historico dos documentos: ela e onde o texto
    # esta no sumario, nao o que ele diz — e um historico que a misturasse faria
    # "voltar para a versao de ontem" significar tambem "e volte para o lugar de
    # ontem no livro", que e outra decisao.
    titulo = models.CharField(max_length=200)
    corpo = models.TextField(blank=True, default="")

    salvo_em = models.DateTimeField(auto_now_add=True)
    salvo_por = models.EmailField(blank=True, default="")
    gesto = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["texto", "-salvo_em"])]

    def __str__(self) -> str:  # pragma: no cover - conveniencia de shell
        return f"{self.texto_id} @ {self.salvo_em:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------- a equipe
#
# O painel da equipe (01/10/2026): o trabalho das quatro pessoas da casa, numa
# tela. Pedido do mantenedor: "abrir o site, enxergar o trabalho da equipe,
# criar uma tarefa, definir quem responde por ela e acompanhar a execução até a
# conclusão". É o MVP; objetivos, compromissos semanais e placar virão por cima
# desta base, e por isso a tarefa já nasce com dono, prazo e situação próprios.


class MembroDaEquipe(models.Model):
    """Uma pessoa da equipe, e a conta do site que responde por ela.

    O NOME e a CONTA são duas coisas de propósito. "Arameu" é quem responde
    pela tarefa na tela; `email` é a conta da `identidade` com que essa pessoa
    entra. O painel reconhece a pessoa pelo e-mail da sessão, e só por ele:
    uma pessoa sem e-mail associado aparece como responsável, mas ainda não
    tem como entrar. A associação é feita pelo mantenedor em
    `/admin/equipe/pessoas`.
    """

    nome = models.CharField(max_length=80)
    area = models.CharField(max_length=120, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    # A senha que a própria pessoa escolhe em "Meus dados", para entrar com
    # e-mail e senha num aparelho sem link (01/10/2026). Guardada só como hash
    # do Django; vazia quer dizer "não entra por senha".
    senha = models.CharField(max_length=128, blank=True, default="")
    erros_de_senha = models.PositiveSmallIntegerField(default=0)
    senha_travada_ate = models.DateTimeField(null=True, blank=True)
    # E-mail que a PRÓPRIA pessoa escreveu em "Meu perfil" e que o mantenedor
    # ainda não conferiu. Serve de nome de usuário para entrar com senha, mas
    # não abre a porta para a conta Google desse e-mail: digitar o e-mail de
    # outra pessoa não pode dar a ela o painel. Salvar o e-mail em Pessoas e
    # contas confere.
    email_a_conferir = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=~models.Q(email=""),
                name="um_membro_por_email",
            )
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return self.nome


class LinkDeAcesso(models.Model):
    """Um link que conecta UM aparelho a uma pessoa da equipe (01/10/2026).

    O código do link mora depois do `#` do endereço, que o navegador nunca
    manda ao servidor: não fica em log, nem em pré-visualização de mensagem.
    Aqui só se guarda o hash dele. Vale uma vez e tem prazo; gerar outro da
    mesma `origem` cancela o que ainda não foi usado.
    """

    class Origem(models.TextChoices):
        MANTENEDOR = "mantenedor", "Gerado na ficha da pessoa"
        PROPRIO = "proprio", "Conectar meu celular"

    membro = models.ForeignKey(
        MembroDaEquipe, on_delete=models.CASCADE, related_name="links"
    )
    origem = models.CharField(max_length=12, choices=Origem.choices)
    codigo_hash = models.CharField(max_length=64, unique=True)
    criado_por = models.CharField(max_length=200, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]


class AparelhoDaEquipe(models.Model):
    """Um aparelho que ficou conectado ao painel da equipe, pelo link ou pela
    senha. O navegador guarda a chave num cookie; aqui só o hash dela.
    Desconectar marca a hora e não apaga a linha."""

    membro = models.ForeignKey(
        MembroDaEquipe, on_delete=models.CASCADE, related_name="aparelhos"
    )
    chave_hash = models.CharField(max_length=64, unique=True)
    como_entrou = models.CharField(max_length=10)
    tipo = models.CharField(max_length=20, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_uso_em = models.DateTimeField()
    desconectado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-ultimo_uso_em"]


class Objetivo(models.Model):
    """Um objetivo da equipe, ao qual as tarefas se ligam (01/10/2026).

    É a base para ligar as tarefas à MCI depois: por ora, só título, descrição,
    prazo e se ainda vale. Objetivo não se apaga pela tela; DESATIVA. Ele some
    das escolhas de tarefa nova, e as tarefas que já apontam para ele continuam
    mostrando o nome dele.
    """

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    prazo = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.CharField(max_length=200, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ativo", "prazo", "titulo"]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return self.titulo


class Tarefa(models.Model):
    """Uma tarefa do trabalho diário da equipe.

    Quem criou, quem alterou por último e quando concluiu moram na própria
    linha, como texto: é o rastro que a tela mostra, e não um sistema de
    auditoria. `responsavel` é PROTECT porque apagar uma pessoa com tarefas
    apagaria trabalho junto; a saída é desativar a pessoa. O mesmo vale para
    `objetivo`.
    """

    class Situacao(models.TextChoices):
        A_FAZER = "a_fazer", "A fazer"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        BLOQUEADA = "bloqueada", "Bloqueada"
        CONCLUIDA = "concluida", "Concluída"

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    responsavel = models.ForeignKey(
        MembroDaEquipe,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tarefas",
    )
    objetivo = models.ForeignKey(
        Objetivo,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tarefas",
    )
    prazo = models.DateField(null=True, blank=True)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.A_FAZER
    )
    impedimento = models.TextField(blank=True, default="")

    criada_por = models.CharField(max_length=200, blank=True, default="")
    criada_em = models.DateTimeField(auto_now_add=True)
    alterada_por = models.CharField(max_length=200, blank=True, default="")
    alterada_em = models.DateTimeField(auto_now=True)
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em"]
        indexes = [
            models.Index(fields=["situacao"]),
            models.Index(fields=["responsavel", "situacao"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return self.titulo


class Compromisso(models.Model):
    """Uma tarefa que alguém assumiu como compromisso de UMA semana.

    `semana` é a segunda-feira daquela semana. Uma linha por (tarefa, semana),
    e não uma marca na própria tarefa: a tarefa que ficou para trás na semana
    passada e foi assumida de novo nesta precisa continuar contando como "ficou"
    lá. Cumprido é a tarefa concluída até o domingo da semana; não há campo
    para isso, porque seria a mesma informação escrita duas vezes.
    """

    tarefa = models.ForeignKey(
        Tarefa, on_delete=models.CASCADE, related_name="compromissos"
    )
    semana = models.DateField()
    marcado_por = models.CharField(max_length=200, blank=True, default="")
    marcado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["semana", "marcado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["tarefa", "semana"], name="um_compromisso_por_semana"
            )
        ]
        indexes = [models.Index(fields=["semana"])]


class Comentario(models.Model):
    """Um comentário curto numa tarefa: o texto, quem e quando. Não se edita
    nem se apaga pela tela; não é sistema de auditoria, é a conversa da tarefa."""

    tarefa = models.ForeignKey(
        Tarefa, on_delete=models.CASCADE, related_name="comentarios"
    )
    texto = models.CharField(max_length=500)
    autor = models.CharField(max_length=200, blank=True, default="")
    # A PESSOA da equipe que comentou, pelo identificador: trocar nome ou
    # e-mail em "Meu perfil" não desliga o comentário de quem o escreveu.
    # Vazio quando quem comentou é o administrador sem ficha na equipe.
    autor_membro = models.ForeignKey(
        MembroDaEquipe,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="comentarios",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]
