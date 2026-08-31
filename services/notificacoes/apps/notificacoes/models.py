"""A caixa central de avisos — uma linha por carta recebida.

Lei da gênese: `docs/decisoes/DECISAO-notificacoes.md` (Fase 0) e
`docs/decisoes/DECISAO-fase-2-do-sininho.md` (as três escolhas do mantenedor no
Rito de Contrato de 26/08/2026). Mapa: `docs/notificacoes/PLANO-MESTRE.md` §6.

**Esta célula é BURRA de propósito, e é isso que a mantém barata.** Ela não faz
leque: cada carta que chega no fio (`notificacao.devida.v1`) já vem endereçada a
UMA pessoa, porque quem publica é que faz o fan-out, em lote, na transação do
fato. Aqui uma carta é uma linha. Quando dez células estiverem publicando, o
custo por carta continua o mesmo.
"""

from django.db import models


class Notificacao(models.Model):
    """Um aviso de uma pessoa. DADO, nunca frase pronta.

    **A irreversibilidade que este model existe para respeitar**
    (`DECISAO-notificacoes` §5.1): guardamos `assunto` + `parametros`, e a frase
    nasce na LEITURA, no idioma de quem está lendo. O site serve três idiomas —
    gravar *"Sua ideia mudou para Em desenvolvimento"* congela o idioma de quem
    gravou, e quem lê em espanhol recebe português para sempre. Texto já gravado
    não se traduz depois: por isso é lei, e não recomendação.

    `destinatario_id` e `ator_id` são ids da PLATAFORMA — os únicos que
    atravessam as células. NUNCA e-mail (`DECISAO-EVO-01` §3).
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    # Nulável porque nem todo fato tem gente por trás: um pagamento aprovado
    # pelo provedor não tem ator. A carta declara isso no contrato, e a coluna
    # diz a mesma coisa. Decisão do mantenedor: GUARDAR quem mexeu, MOSTRAR "a
    # equipe" — mostrar o nome depois é reversível, não ter guardado não é.
    ator_id = models.CharField(max_length=64, null=True, blank=True)
    assunto = models.CharField(max_length=64)
    parametros = models.JSONField()
    # O event_id do FATO que gerou esta carta. As N cartas de uma mesma mudança
    # compartilham este valor — é o que permite reconstruir o leque inteiro e é
    # a parte "rastreável" da promessa nova (`DECISAO-notificacoes` §2).
    origem_event_id = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)
    lido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            # O caminho quente é sempre o mesmo: "os avisos DESTA pessoa NESTE
            # site, os mais novos primeiro" — e o `-criado_em` faz a página 1
            # sair sem ordenar nada em memória.
            #
            # **`site_id` E `destinatario_id` lideram JUNTOS, de propósito —
            # não simplifique para um dos dois.** As três rotas da porta de
            # consulta (Fase 4) sempre filtram pelos dois juntos: "cada site
            # mostra só os avisos que vieram dele" (decisão do mantenedor,
            # 27/08/2026, CONSTITUICAO.md Lei 9). Um índice liderado só por
            # `destinatario_id` chegou a existir por algumas horas neste PR,
            # entre uma versão do contrato sem `site_id` e a emenda que passou
            # a exigi-lo — `EXPLAIN ANALYZE` mediu essa versão (não suposição:
            # 500 pessoas de ruído + 1 pessoa com 1.500 linhas em 5 sites, 300
            # no site pedido) e achou "Rows Removed by Filter: 1200" — o
            # índice lia TODA linha da pessoa em qualquer site e só depois
            # descartava as de fora. Liderar pelas duas colunas (a forma que
            # já estava aqui desde a gênese, PR #247) faz o Postgres usar
            # `Index Cond` para as duas e não descartar nada. A medição
            # completa está em `LICOES.md`; o guarda que a mantém viva é
            # `tests/test_indices_da_porta_de_consulta.py`.
            models.Index(
                fields=["site_id", "destinatario_id", "-criado_em"],
                name="notif_caixa_da_pessoa",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.assunto}→{self.destinatario_id}"


class ContadorDeNaoLidos(models.Model):
    """Quantos avisos não lidos uma pessoa tem — em UMA linha, lida em O(1).

    **Por que uma tabela e não `COUNT(*)`** (`DECISAO-notificacoes` §5.2): o sino
    aparece em TODA página do site. Um `COUNT(*)` numa tabela que cresce para
    sempre fica lento exatamente quando o produto der certo — e o custo apareceria
    na página inicial de todo mundo, não numa tela escondida.

    O contador é mantido na MESMA transação que escreve a notificação. Um
    contador atualizado depois, "quando der", é um contador que diverge no
    primeiro erro de rede e nunca mais volta ao lugar sozinho. O guarda que prova
    a igualdade é `tests/test_inv_contador_bate_com_a_tabela.py`.
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    nao_lidos = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "destinatario_id"], name="contador_um_por_pessoa"
            )
        ]
        # SEM índice extra de propósito — resista à tentação de acrescentar
        # um "para garantir". `GET /resumo` (Fase 4) lê por `(site_id,
        # destinatario_id)`, exatamente a chave do `UniqueConstraint` acima
        # (desde a gênese, PR #248), que JÁ é um índice único nessas duas
        # colunas. Um índice extra liderado só por `destinatario_id` chegou a
        # existir por algumas horas neste PR — `EXPLAIN ANALYZE` mostrou o
        # Postgres preferindo `contador_um_por_pessoa` (`Index Cond` nas DUAS
        # colunas, zero linha descartada) assim que a query passou a filtrar
        # as duas, tornando o índice extra dead weight: nunca escolhido para
        # leitura, e ainda assim custando em todo `INSERT`. Removido. A
        # medição completa está em `LICOES.md`; o guarda que a mantém viva é
        # `tests/test_indices_da_porta_de_consulta.py`.

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.destinatario_id}={self.nao_lidos}"


class NotificacaoArquivada(models.Model):
    """Aviso lido e velho — fora do caminho quente, mas não apagado.

    **Tabela separada, e não uma coluna `arquivada`** (`DECISAO-notificacoes`
    §5.2: *"arquivamento desde o começo — notificação lida e velha sai do caminho
    quente"*). Uma coluna deixaria as linhas velhas no mesmo lugar, engordando o
    índice que a página do sino percorre em toda visita; o ganho seria só de
    filtro, e o custo continuaria crescendo. Mudar de tabela é o que faz a caixa
    quente parar de crescer de verdade.

    Nada se perde: o histórico continua consultável, só não está no caminho que
    toda página percorre.
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    ator_id = models.CharField(max_length=64, null=True, blank=True)
    assunto = models.CharField(max_length=64)
    parametros = models.JSONField()
    origem_event_id = models.UUIDField()
    criado_em = models.DateTimeField()
    lido_em = models.DateTimeField()
    arquivada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Mesma correção e mesmo motivo do índice de `Notificacao`: as
            # três rotas da porta de consulta filtram por `site_id` E
            # `destinatario_id` juntos (decisão do mantenedor, 27/08/2026,
            # CONSTITUICAO.md Lei 9) — os dois lideram o índice.
            models.Index(
                fields=["site_id", "destinatario_id", "-criado_em"],
                name="notif_arquivo_da_pessoa",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"[arquivada] {self.assunto}→{self.destinatario_id}"


class InscricaoPush(models.Model):
    """Um APARELHO que aceitou receber o aviso na tela, mesmo com o site fechado.

    Canal novo da Fase 7 (`docs/notificacoes/PLANO-MESTRE.md`), autorizado pelo
    mantenedor em 31/08/2026 depois de o site virar app instalável (PR #706).
    No iPhone essa ordem é obrigatória e não tem atalho: só um site instalado na
    tela de início pode receber aviso.

    **Uma linha por APARELHO, nunca por pessoa.** A mesma pessoa no celular e no
    tablet tem duas linhas, e cada uma morre sozinha quando aquele aparelho
    desinstala. Por isso a chave única é o `endpoint`, e não o par
    pessoa+site: é o aparelho que o servidor de push conhece.

    **E é por isso que `destinatario_id` pode MUDAR numa linha que já existe.**
    Um aparelho emprestado, ou uma segunda conta no mesmo celular, reinscreve o
    MESMO endpoint com outro dono, e a linha passa a ser da pessoa que está
    entrando. A alternativa (uma linha por par pessoa+aparelho) mandaria o aviso
    da primeira pessoa para o aparelho da segunda, que é vazamento de aviso
    alheio e não é reversível depois de acontecer.

    O que vive aqui é opaco de propósito: `endpoint` é o endereço do servidor de
    push do fabricante, e as duas chaves são o material que CIFRA o conteúdo do
    aviso de ponta a ponta. Nem esta célula guarda texto de aviso, nem o
    fabricante consegue ler o que passou por ele. Nada aqui é e-mail
    (`DECISAO-EVO-01` §3).
    """

    site_id = models.CharField(max_length=64)
    destinatario_id = models.CharField(max_length=64)
    # 2048 é o teto do contrato. Os endpoints reais de hoje têm ~200 caracteres,
    # mas o valor é opaco e do fabricante: apertar isto seria decidir, por ele,
    # o formato que ele pode usar amanhã.
    endpoint = models.CharField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=256)
    auth = models.CharField(max_length=64)
    criado_em = models.DateTimeField(auto_now_add=True)
    # Quando este aparelho foi visto pela última vez reinscrevendo-se. O
    # navegador reemite a inscrição sozinho de tempos em tempos, então esta
    # coluna é o sinal mais honesto de "este aparelho ainda existe" — e é o que
    # permitirá, um dia, uma limpeza por idade sem chutar.
    visto_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # O caminho quente é um só: "os aparelhos DESTA pessoa NESTE site",
            # perguntado uma vez por carta que chega. Mesma dupla que lidera o
            # índice da caixa, e pelo mesmo motivo (Lei 9: nada atravessa sites).
            models.Index(
                fields=["site_id", "destinatario_id"], name="notif_aparelhos_da_pessoa"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.destinatario_id}@{self.endpoint[:32]}"
