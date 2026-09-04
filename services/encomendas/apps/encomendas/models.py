"""As tabelas da Fila do Primeiro Dólar, e as três promessas que viram banco.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (§3.8 os parâmetros, §5 os
invariantes, §6 as 27 chaves). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`
§7.1 (entidades) e §7.2 (máquinas de estado). Contrato em papel:
`docs/decisoes/CONTRATO-encomendas-v1-rascunho.md`.

Este é o degrau 2.2 da escada. **Não há motor de oferta, não há relógio, não há
tela e não há porta de máquina** — eles são os degraus 2.3, 2.4, 2.7 e as Fases 3
e 4. O que existe aqui é a fundação, e nela as três coisas que o resto vai poder
tratar como verdade:

1. **A máquina de estado da encomenda não é um `if` espalhado.** As transições da
   §7.2 do plano são DADO (`Encomenda.TRANSICOES`), e o PostgreSQL recusa a
   transição proibida por gatilho — inclusive vinda de `queryset.update()`, de
   uma migração de dados ou de um `psql` de madrugada (`armadilhas/023`).
2. **Os parâmetros são DADO, com histórico por linha nova.** `Parametro` é
   append-only NO BANCO: `UPDATE` e `DELETE` são recusados por gatilho. Mudar um
   valor é acrescentar uma linha com `desde`, `motivo` e `quem`; o motor lê o
   valor vigente **em `agora`**, e por isso um parâmetro mudado às 15h não
   reescreve uma oferta feita às 14h (lei §3.8).
3. **Nenhum dado de um site aparece em outro.** `site_id` em toda entidade
   (Lei 9 / [INV-P11]), e a coluna denormalizada não pode mentir: a `Oferta` só
   aponta para encomenda e perfil DO MESMO SITE, por chave estrangeira composta
   (`armadilhas/274`).

`site_id` EM TODA ENTIDADE, COM UMA EXCEÇÃO DECLARADA
-----------------------------------------------------
A exceção é `Pessoa`, e é de desenho: o espelho copia a identidade da
PLATAFORMA, que é uma só por pessoa em todos os sites (quem a emite é a célula
`identidade`). A fronteira de site desta célula mora no `PerfilProfissional`,
com `Unique(pessoa, site_id)` — o mesmo desenho da gamificação. Quem mantém a
exceção visível: `tests/test_modelo_de_dados.py::test_site_id_em_toda_entidade`.

O QUE ESTE ARQUIVO NÃO GUARDA, DE PROPÓSITO
-------------------------------------------
- **`responsavel_id` não existe.** A escola é 18+ (lei §3.1, reconfirmada pelo
  mantenedor em 03/09/2026). O plano previa o campo porque foi escrito por IAs
  que não sabiam disso. Se a escola um dia admitir menores, a trava volta ao §3.1
  da lei ANTES de a funcionalidade que a exige ser ligada — e este parágrafo é
  onde o próximo a ler descobre que a ausência foi decidida, não esquecida.
- **Cobrança, retenção, repasse e reembolso.** São da célula `pagamentos` (lei
  §9, critério de morte 3). `preco_cents` e `taxa_cents` estão aqui porque o
  CONTRATO de `encomenda.paga` e `encomenda.aprovada` os exige no evento que
  ESTA célula emite: guardar o número que a `pagamentos` confirmou não é cobrar.
- **Entrega, Revisao, Correcao, Mediacao, Cliente e Portfolio.** São das Fases 5,
  6 e 7. `Encomenda.status` já nomeia os estados delas, porque a máquina de
  estado é uma só e parti-la seria inventar uma segunda.
- **Entrega de arquivo.** A plataforma não guarda arquivo hoje; onde moram
  `.fbx` e `.blend` é decisão da Fase 5 com o mantenedor (constituição, item 2
  do "ainda NÃO resolvido").
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Length

# O `CHECK (char_length(motivo) >= 15)` do `Parametro` precisa de `__length`, e o
# Django nao registra essa transformacao de fabrica. Registrar aqui e o caminho
# que a propria documentacao do Django indica; a alternativa seria `RunSQL` na
# migracao, que sairia do vocabulario do ORM e some do `makemigrations` de quem
# vier depois. O efeito e do processo desta celula, e ela e a unica que roda
# neste container.
models.TextField.register_lookup(Length)

# ---------------------------------------------------------------------------
# As peças comuns
# ---------------------------------------------------------------------------


def id_do_site() -> models.CharField:
    """O campo de fronteira de site, um só, para não haver dois formatos.

    Texto opaco de 64, como TODO id que atravessa fronteira nesta plataforma —
    nunca `UUIDField`. Um `UUIDField` aqui criaria uma fronteira que não casa com
    a casa e obrigaria conversão silenciosa em cada consumidor.
    """
    return models.CharField(max_length=64, db_index=True)


def id_da_plataforma() -> models.CharField:
    """Um id OPACO de outra célula: pessoa, pagamento, conta de recebimento.

    Nunca chave estrangeira (a tabela é de outra célula, com outro banco e outro
    papel) e nunca e-mail (o e-mail muda de dono). Vazio significa "ainda não
    sei", e é por isso que ele é `blank=True, default=""` em vez de `null=True`:
    duas formas de "não sei" na mesma coluna é a origem de metade das consultas
    erradas.
    """
    return models.CharField(max_length=64, blank=True, default="")


class TransicaoProibida(ValidationError):
    """A máquina de estado recusou o passo pedido.

    Existe como exceção com nome próprio para que o chamador possa distinguir
    "este gesto não é permitido agora" (que vira mensagem na tela) de qualquer
    outro erro de banco. O gatilho do PostgreSQL recusa o mesmo passo, e é ele
    quem vale contra `queryset.update()`; esta classe é a porta educada.
    """


# ---------------------------------------------------------------------------
# A MÁQUINA DE ESTADO DA ENCOMENDA — a §7.2 do plano, transcrita como DADO
# ---------------------------------------------------------------------------
# Mora no MÓDULO, e não dentro da classe, por três razões práticas: o corpo de
# uma `class Meta` aninhada não enxerga os nomes da classe que a contém, a
# migração precisa da mesma tabela para escrever o gatilho, e o teste precisa
# dela para provar, par a par, que o Python e o PostgreSQL concordam.
#
# Os 15 estados, na ordem da linha principal. `Encomenda.Status` repete os
# mesmos valores porque é ele quem dá o RÓTULO que a tela mostra; que as duas
# listas nunca divirjam é o que
# `tests/test_maquinas_de_estado.py::test_os_estados_do_textchoices_sao_os_da_maquina`
# faz valer.
ESTADOS_DE_ENCOMENDA = [
    "aguardando_pagamento",
    "na_fila",
    "oferecida",
    "aberta",
    "em_producao",
    "entregue",
    "em_revisao",
    "aguardando_cliente",
    "em_correcao",
    "para_reclassificar",
    "abandonada",
    "em_mediacao",
    "aprovada",
    "concluida",
    "cancelada",
]

# "Qualquer estado ativo -> em_mediacao" (plano §7.2). Ativo = tudo que ainda
# não terminou. `aprovada` fica de fora de propósito: dali só se vai para
# `concluida`, e reabrir uma aprovação é decisão de produto que ninguém tomou.
ESTADOS_ATIVOS_DA_ENCOMENDA = frozenset(
    {
        "aguardando_pagamento",
        "na_fila",
        "oferecida",
        "aberta",
        "em_producao",
        "entregue",
        "em_revisao",
        "aguardando_cliente",
        "em_correcao",
        "para_reclassificar",
        "abandonada",
    }
)

_LINHA_PRINCIPAL = {
    "aguardando_pagamento": {"na_fila", "cancelada"},
    "na_fila": {"oferecida", "aberta", "para_reclassificar", "cancelada"},
    "oferecida": {"na_fila", "em_producao", "aberta", "para_reclassificar"},
    "aberta": {"em_producao"},
    "em_producao": {"entregue", "abandonada"},
    # A auditoria automática reprovou: volta ao aluno antes de humano nenhum ver.
    "entregue": {"em_revisao", "em_producao"},
    # O revisor devolveu com notas.
    "em_revisao": {"aguardando_cliente", "em_producao"},
    "aguardando_cliente": {"aprovada", "em_correcao"},
    "em_correcao": {"entregue"},
    "para_reclassificar": {"na_fila", "cancelada"},
    "abandonada": {"na_fila"},
    "em_mediacao": {"aprovada", "cancelada"},
    "aprovada": {"concluida"},
    "concluida": set(),
    "cancelada": set(),
}

TRANSICOES_DA_ENCOMENDA = {
    estado: frozenset(
        destinos | ({"em_mediacao"} if estado in ESTADOS_ATIVOS_DA_ENCOMENDA else set())
    )
    for estado, destinos in _LINHA_PRINCIPAL.items()
}


# ---------------------------------------------------------------------------
# 1. QUEM É A PESSOA — o espelho, nunca a fonte da verdade
# ---------------------------------------------------------------------------


class Pessoa(models.Model):
    """O espelho local de quem participa. Molde: `services/forum` e `services/gamificacao`.

    Quem sabe quem é a pessoa é a célula `identidade`; quem sabe se ela é aluna é
    a célula `alunos`. Esta tabela guarda o mínimo para a Fila conseguir dizer
    "de quem é este perfil" sem uma chamada de rede por linha exibida.

    **E aqui o mínimo é menor que o dos moldes: não há `email`.** O fórum e a
    gamificação guardam o e-mail porque EVENTOS chegam a eles por e-mail
    (`quiz.completado.v1`), e sem a coluna não haveria como resolver o evento
    contra o espelho. Esta célula não consome evento nenhum (`celulas.yml`:
    `consome: []`), e o e-mail de que `getStudentStanding` precisa chega na
    própria requisição, vindo da sessão, no instante em que a pergunta é feita.
    Copiar um dado alheio que não se usa é a Lei 2 ao contrário: uma segunda
    verdade que ninguém mantém. A constituição desta célula já dizia isto com
    todas as letras — *"`Pessoa` é espelho mínimo (id da plataforma, nome de
    exibição)"*.

    Também não entram idade nem data de nascimento: a escola é 18+ e nenhuma
    regra desta célula depende de saber quantos anos alguém tem (lei §3.1).
    """

    # O id OPACO da plataforma, como a `identidade` o devolve. É a chave de
    # ligação com o resto do site.
    id_da_plataforma = models.CharField(max_length=64, primary_key=True)
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    vista_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "pessoas"

    def __str__(self) -> str:
        return self.nome_exibido or self.id_da_plataforma


# ---------------------------------------------------------------------------
# 2. O PERFIL PROFISSIONAL — o lugar na fila, e o que decide a ordem
# ---------------------------------------------------------------------------


class PerfilProfissional(models.Model):
    """Um por aluno por site: o título, a disponibilidade e o lugar na fila.

    **Os dois campos que decidem a ordem da fila são `entregas_aprovadas` e
    `data_entrada_fila`**, nesta ordem (plano §6.2: menos entregas primeiro;
    empate, quem entrou antes). A fila tem UMA regra, e ela é esta: uma segunda
    regra de ordem (peso, prioridade paga, destaque) é o critério de morte 2 da
    lei §9. Não acrescente coluna de prioridade aqui sem reabrir a decisão.

    **O título vem do professor, com data e autor** (lei §3.6): não existe Banca
    ainda, e a gamificação de propósito não fala língua de credencial. Quando a
    célula de cursos tiver a Banca, ela passa a ser a segunda fonte do MESMO
    campo, por evento — e por isso `titulo_dado_por` já nasce aceitando tanto o
    id do professor quanto a marca de quem o concedeu.

    **`cerimonias_pendentes` é o [INV-P12] em forma de coluna.** A cerimônia do
    primeiro dólar é tela cheia, uma vez só (plano §5.8), e toda tela assim
    precisa responder "esta pessoa já viu?". O caminho curto é
    `request.session[...]`, que funciona em dev, passa em teste de unidade e
    desloga a plataforma inteira em produção, sem erro em lugar nenhum
    (`armadilhas/143`). O estado mora AQUI, como a gamificação faz com
    `celebracoes_pendentes`.
    """

    class Titulo(models.TextChoices):
        NIVEL_1 = "nivel_1", "Modelador Nível 1"
        NIVEL_2 = "nivel_2", "Modelador Nível 2"
        NIVEL_3 = "nivel_3", "Modelador Nível 3"

    class Disponibilidade(models.TextChoices):
        DISPONIVEL = "disponivel", "Disponível para receber ofertas"
        PAUSADO = "pausado", "Pausado (mantém o lugar na fila)"
        TRABALHANDO = "trabalhando", "Trabalhando numa encomenda"

    class ModoDaPausa(models.TextChoices):
        MANUAL = "manual", "O próprio aluno desligou o interruptor"
        POR_SILENCIO = "automatica_por_silencio", "Três silêncios seguidos"
        POR_SEGUNDO_ABANDONO = "por_segundo_abandono", "Segundo abandono na janela"
        SUSPENSAO = "suspensao_pelo_plantao", "Suspensão pelo plantão"

    # As transições de `disponibilidade` (plano §7.2). Dado, não `if`.
    TRANSICOES: dict[str, frozenset[str]] = {
        Disponibilidade.DISPONIVEL: frozenset(
            {Disponibilidade.PAUSADO, Disponibilidade.TRABALHANDO}
        ),
        # Pausado NÃO vai direto a "trabalhando": quem está fora das ofertas não
        # recebe oferta, então não há aceite para atravessar. Religar primeiro é
        # o que mantém [INV-ENC-J7] possível de provar no degrau 2.3.
        Disponibilidade.PAUSADO: frozenset({Disponibilidade.DISPONIVEL}),
        # Aprovada, abandono ou mediação encerrada devolvem à fila; o plantão
        # ainda pode suspender quem está no meio de um trabalho.
        Disponibilidade.TRABALHANDO: frozenset(
            {Disponibilidade.DISPONIVEL, Disponibilidade.PAUSADO}
        ),
    }

    pessoa = models.ForeignKey(Pessoa, related_name="perfis", on_delete=models.PROTECT)
    site_id = id_do_site()

    titulo_banca = models.CharField(
        max_length=10, choices=Titulo.choices, blank=True, default=""
    )
    # Quem deu o título e quando. Vazio junto com o título vazio, preenchido
    # junto com ele — e é o BANCO quem exige as duas coisas ao mesmo tempo
    # (`titulo_de_banca_tem_autor_e_data`). Título sem autor é exatamente o que
    # o piloto de papel já não aceita: a decisão do professor tem nome e data.
    titulo_dado_por = id_da_plataforma()
    titulo_dado_em = models.DateTimeField(null=True, blank=True)

    disponibilidade = models.CharField(
        max_length=12,
        choices=Disponibilidade.choices,
        default=Disponibilidade.DISPONIVEL,
    )
    # Quando a pessoa ativou a fila pela PRIMEIRA vez. É o desempate da ordem, e
    # só o abandono o altera (plano §6.2; [INV-ENC-J4], guarda no degrau 2.3).
    data_entrada_fila = models.DateTimeField(null=True, blank=True)
    entregas_aprovadas = models.PositiveIntegerField(default=0)
    silencios_consecutivos = models.PositiveSmallIntegerField(default=0)

    modo_da_pausa = models.CharField(
        max_length=24, choices=ModoDaPausa.choices, blank=True, default=""
    )
    # Quando a pausa vence sozinha; nulo quando só a pessoa (ou o plantão)
    # religa. É o campo `ate` de `aluno.pausado.v1`.
    pausa_ate = models.DateTimeField(null=True, blank=True)

    # As datas dos abandonos, em texto ISO. Lista e não contador porque as duas
    # regras que as usam são de JANELA: segundo abandono em 90 dias pausa por 30
    # (plano §6.6), e o nível avançado exige nenhum abandono nos últimos 90 dias
    # (§6.1). Um contador não sabe responder "nos últimos 90 dias".
    abandonos = models.JSONField(default=list, blank=True)

    # Id opaco da conta de recebimento na célula `pagamentos`. Vazio significa
    # "sem conta verificada", e é o estado em que [INV-ENC-D17] manda o repasse
    # ficar bloqueado com o plantão avisado, sem o aluno perder o valor (lei
    # §3.1). Esta célula NUNCA guarda dado bancário: só o id.
    conta_repasse_id = id_da_plataforma()
    portfolio_publicado_em = models.DateTimeField(null=True, blank=True)

    cerimonias_pendentes = models.JSONField(default=list, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil profissional"
        verbose_name_plural = "perfis profissionais"
        indexes = [
            # A consulta do motor de oferta, na ordem em que ele ordena
            # (plano §6.2 e §7.4). Nasce com a tabela porque índice que chega
            # depois chega quando a fila já está lenta.
            models.Index(
                fields=[
                    "site_id",
                    "disponibilidade",
                    "entregas_aprovadas",
                    "data_entrada_fila",
                ],
                name="enc_fila_ordem_do_motor",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id"], name="um_perfil_por_pessoa_por_site"
            ),
            # O par referenciável pela chave estrangeira composta da `Oferta` e
            # da `Encomenda`. Parece redundante (o `id` já é único) — e é essa
            # aparência que faz alguém apagá-lo um dia, derrubando a guarda de
            # site sem que nada pareça errado (`armadilhas/274`).
            models.UniqueConstraint(
                fields=["id", "site_id"], name="uniq_perfil_id_com_site"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    disponibilidade__in=["disponivel", "pausado", "trabalhando"]
                ),
                name="disponibilidade_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(titulo_banca="")
                | models.Q(titulo_banca__in=["nivel_1", "nivel_2", "nivel_3"]),
                name="titulo_de_banca_no_vocabulario_fechado",
            ),
            # Título sem autor e sem data seria um título que ninguém deu.
            models.CheckConstraint(
                condition=(
                    models.Q(titulo_banca="", titulo_dado_por="", titulo_dado_em=None)
                    | (
                        ~models.Q(titulo_banca="")
                        & ~models.Q(titulo_dado_por="")
                        & models.Q(titulo_dado_em__isnull=False)
                    )
                ),
                name="titulo_de_banca_tem_autor_e_data",
            ),
            # Pausa só existe em perfil pausado. Sem isto, um perfil
            # "disponível" com `pausa_ate` no futuro seria lido de dois jeitos
            # por dois pedaços de código, e o segundo a ler é o que erra.
            models.CheckConstraint(
                condition=models.Q(disponibilidade="pausado")
                | models.Q(modo_da_pausa="", pausa_ate=None),
                name="pausa_so_existe_em_perfil_pausado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}@{self.site_id} {self.disponibilidade}"

    def pode_ir_para(self, disponibilidade: str) -> bool:
        """A máquina de disponibilidade responde sozinha, sem tocar o banco."""
        return disponibilidade in self.TRANSICOES.get(self.disponibilidade, frozenset())

    def mudar_disponibilidade(
        self, para: str, *, modo_da_pausa: str = "", pausa_ate=None
    ):
        """Muda a disponibilidade, ou recusa com `TransicaoProibida`.

        Não existe `mudar_disponibilidade(mesma coisa)`: repetir o estado atual é
        recusado, porque o chamador que "reafirma" um estado quase sempre está
        perdendo uma condição de corrida, e devolver sucesso ali é o falso-verde
        do padrão 1 da `RETROSPECTIVA-FASE-D`.
        """
        if not self.pode_ir_para(para):
            raise TransicaoProibida(
                f"perfil {self.pk}: {self.disponibilidade} nao vai para {para}. "
                f"As transicoes permitidas sao {sorted(self.TRANSICOES[self.disponibilidade])}."
            )
        self.disponibilidade = para
        if para == self.Disponibilidade.PAUSADO:
            self.modo_da_pausa = modo_da_pausa
            self.pausa_ate = pausa_ate
        else:
            self.modo_da_pausa = ""
            self.pausa_ate = None
        self.save(
            update_fields=[
                "disponibilidade",
                "modo_da_pausa",
                "pausa_ate",
                "atualizado_em",
            ]
        )
        return self


# ---------------------------------------------------------------------------
# 3. A ENCOMENDA — e a máquina de estado da §7.2, que o banco faz valer
# ---------------------------------------------------------------------------


class Encomenda(models.Model):
    """Um pedido, do pagamento à conclusão. A máquina de estado é a §7.2 do plano.

    **O `status` só muda por `mudar_status()`, e o PostgreSQL recusa o resto.**
    Uma máquina de estado que vive só em Python é uma promessa: `queryset.update()`
    não passa por `save()` (`armadilhas/023`), e uma migração de dados, uma tela
    de administração futura ou um `psql` de madrugada passam por fora dela sem
    ninguém saber. O gatilho `encomendas_transicao_permitida` compara
    `OLD.status` com `NEW.status` contra a mesma tabela de transições, e nega
    dizendo o nome dos dois estados.

    **Dinheiro é inteiro em centavos**, nunca `float` nem `Decimal`
    (`contracts/README.md`, item 7). E estar aqui não é cobrar: `preco_cents` e
    `taxa_cents` são exigidos pelos eventos `encomenda.paga.v1` e
    `encomenda.aprovada.v1`, que ESTA célula emite. Quem cobra, retém, repassa e
    reembolsa é a `pagamentos` (lei §9, critério de morte 3).
    """

    class Origem(models.TextChoices):
        FILA = "fila", "Pela fila"
        DIRETO = "direto", "Pedido direto ao aluno"
        ESCOLA = "escola", "Aberta pelo plantão, a escola é a cliente"

    class Cartao(models.TextChoices):
        ITEM_SIMPLES = "item_simples", "Item simples"
        VESTIVEL_OU_VEICULO = "vestivel_ou_veiculo", "Vestível ou veículo"
        PERSONAGEM = "personagem", "Personagem"

    class Nivel(models.TextChoices):
        INICIANTE = "iniciante", "Iniciante"
        INTERMEDIARIO = "intermediario", "Intermediário"
        AVANCADO = "avancado", "Avançado"

    class Confirmacao(models.TextChoices):
        WEBHOOK = "webhook", "Confirmado pelo webhook da célula de pagamentos"
        PLANTAO = "plantao", "Declarado pago pelo plantão (a escola é a cliente)"

    class Status(models.TextChoices):
        AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
        NA_FILA = "na_fila", "Na fila"
        OFERECIDA = "oferecida", "Oferecida a um aluno"
        ABERTA = "aberta", "Chamada aberta"
        EM_PRODUCAO = "em_producao", "Em produção"
        ENTREGUE = "entregue", "Entregue"
        EM_REVISAO = "em_revisao", "Em revisão"
        AGUARDANDO_CLIENTE = "aguardando_cliente", "Aguardando o cliente"
        EM_CORRECAO = "em_correcao", "Em correção"
        PARA_RECLASSIFICAR = "para_reclassificar", "Para o plantão reclassificar"
        ABANDONADA = "abandonada", "Abandonada"
        EM_MEDIACAO = "em_mediacao", "Em mediação"
        APROVADA = "aprovada", "Aprovada"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    # O CARTÃO DECIDE O NÍVEL, sempre. "O cliente nunca escolhe nível de
    # modelador" (plano §5.1), e é o critério de morte 1 da lei §9 se um dia
    # escolher. Deixar isto como tabela, e não como coluna livre, é o que impede
    # uma tela futura de oferecer a escolha por acidente.
    NIVEL_DO_CARTAO: dict[str, str] = {
        Cartao.ITEM_SIMPLES: Nivel.INICIANTE,
        Cartao.VESTIVEL_OU_VEICULO: Nivel.INTERMEDIARIO,
        Cartao.PERSONAGEM: Nivel.AVANCADO,
    }

    ESTADOS_ATIVOS = ESTADOS_ATIVOS_DA_ENCOMENDA
    TRANSICOES = TRANSICOES_DA_ENCOMENDA

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = id_do_site()

    origem = models.CharField(max_length=8, choices=Origem.choices)
    cliente_id = id_da_plataforma()
    cartao = models.CharField(max_length=20, choices=Cartao.choices)
    nivel = models.CharField(max_length=14, choices=Nivel.choices)
    # As respostas do briefing blindado (plano §5.2). Json e não colunas porque
    # a letra miúda de cada cartão é diferente e muda sem migração. **Sem campo
    # de contato**: [INV-ENC-S1] e [INV-ENC-S3] são exatamente sobre isso, e o
    # guarda deles nasce na Fase 3.
    briefing = models.JSONField(default=dict, blank=True)

    preco_cents = models.PositiveIntegerField(default=0)
    taxa_cents = models.PositiveIntegerField(default=0)

    # Preenchidos no aceite: o prazo de produção pelo cartão, e o prometido ao
    # cliente = produção + o dia de revisão (plano §5.1). Os dois são
    # parâmetro, e por isso não há número nenhum aqui.
    prazo_producao_ate = models.DateTimeField(null=True, blank=True)
    prazo_prometido_ate = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AGUARDANDO_PAGAMENTO
    )
    aluno = models.ForeignKey(
        PerfilProfissional,
        related_name="encomendas",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    # A caixa marcada por padrão no checkout (plano §5.6). Sem ela a peça não
    # sai pela porta de peças aprovadas ([INV-ENC-S4], Fase 6), e o default é
    # `False` porque autorização que nasce ligada não é autorização.
    autorizacao_portfolio = models.BooleanField(default=False)

    pagamento_id = id_da_plataforma()
    # A CONFIRMAÇÃO REGISTRADA COM AUTOR, que é o que [INV-ENC-D13] mede — e não
    # o webhook. Até a Fase 3 a única origem é `escola`, e quem declara "pago
    # pela escola" é o plantão, com nome e data (lei §3.4).
    confirmacao_de_pagamento = models.CharField(
        max_length=8, choices=Confirmacao.choices, blank=True, default=""
    )
    pagamento_confirmado_em = models.DateTimeField(null=True, blank=True)
    pagamento_confirmado_por = id_da_plataforma()

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # A varredura do motor: as encomendas na fila, da mais antiga para a
            # mais nova (plano §7.4).
            models.Index(
                fields=["site_id", "status", "criada_em"], name="enc_varredura_do_motor"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["id", "site_id"], name="uniq_encomenda_id_com_site"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ESTADOS_DE_ENCOMENDA),
                name="status_de_encomenda_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(origem__in=["fila", "direto", "escola"]),
                name="origem_no_vocabulario_fechado",
            ),
            # O cartão decide o nível. Escrito como as três combinações
            # possíveis, porque `CheckConstraint` não chama função Python: é a
            # tabela `NIVEL_DO_CARTAO` no idioma do banco.
            models.CheckConstraint(
                condition=(
                    models.Q(cartao="item_simples", nivel="iniciante")
                    | models.Q(cartao="vestivel_ou_veiculo", nivel="intermediario")
                    | models.Q(cartao="personagem", nivel="avancado")
                ),
                name="o_cartao_decide_o_nivel",
            ),
            # "`plantao` só existe para `origem = escola`" — o contrato de
            # `encomenda.paga.v1` diz isso com todas as letras. No banco, é o que
            # impede alguém de declarar paga, à mão, uma encomenda de cliente de
            # verdade sem o dinheiro ter entrado.
            models.CheckConstraint(
                condition=~models.Q(confirmacao_de_pagamento="plantao")
                | models.Q(origem="escola"),
                name="confirmacao_pelo_plantao_so_para_a_escola",
            ),
            # Confirmação REGISTRADA COM AUTOR: quem confirmou e quando. O
            # webhook não tem pessoa atrás, e por isso ele preenche a data e
            # deixa o autor vazio; o plantão preenche os dois.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        confirmacao_de_pagamento="",
                        pagamento_confirmado_em=None,
                        pagamento_confirmado_por="",
                    )
                    | models.Q(
                        confirmacao_de_pagamento="webhook",
                        pagamento_confirmado_em__isnull=False,
                    )
                    | (
                        models.Q(
                            confirmacao_de_pagamento="plantao",
                            pagamento_confirmado_em__isnull=False,
                        )
                        & ~models.Q(pagamento_confirmado_por="")
                    )
                ),
                name="confirmacao_de_pagamento_tem_autor_e_data",
            ),
            # O prazo prometido é o de produção MAIS o dia de revisão: nunca
            # antes. Prometer ao cliente uma data anterior à do trabalho é o
            # atraso que ninguém consegue explicar depois.
            models.CheckConstraint(
                condition=models.Q(prazo_prometido_ate__isnull=True)
                | models.Q(prazo_producao_ate__isnull=True)
                | models.Q(prazo_prometido_ate__gte=models.F("prazo_producao_ate")),
                name="prazo_prometido_nunca_antes_do_de_producao",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.id} {self.cartao} {self.status}"

    def pode_ir_para(self, status: str) -> bool:
        return status in self.TRANSICOES.get(self.status, frozenset())

    @transaction.atomic
    def mudar_status(self, para: str, *, ator_id: str = "", motivo: str = ""):
        """O único caminho educado para mudar o estado, e ele deixa rastro.

        `ator_id` vazio significa "foi o relógio ou o motor", exatamente como o
        `ator_id: null` dos eventos desta célula: reavaliação periódica não tem
        pessoa atrás. A linha de histórico e o novo status entram na MESMA
        transação, porque estado sem rastro é o que faz uma mediação virar a
        palavra de um contra a do outro.
        """
        if not self.pode_ir_para(para):
            raise TransicaoProibida(
                f"encomenda {self.pk}: {self.status} nao vai para {para}. "
                f"As transicoes permitidas sao {sorted(self.TRANSICOES[self.status])}."
            )
        de = self.status
        self.status = para
        self.save(update_fields=["status", "atualizada_em"])
        MudancaDeStatus.objects.create(
            encomenda=self,
            site_id=self.site_id,
            de=de,
            para=para,
            ator_id=ator_id,
            motivo=motivo,
        )
        return self


class MudancaDeStatus(models.Model):
    """O histórico de status da encomenda, com autor. Append-only NO BANCO.

    O plano §7.1 pede "histórico de status com autor" numa linha; a razão de ele
    ser append-only por gatilho, e não por disciplina, é a mesma da auditoria da
    célula `admin` (`armadilhas/079`): histórico que pode ser editado não é
    histórico. Quando uma mediação precisar responder "quem mandou esta
    encomenda de volta para a fila, e quando", esta tabela é a resposta, e ela
    não pode ter sido reescrita por um `update()` no meio do caminho.

    `ator_id` vazio é o relógio ou o motor, casando com o `ator_id: null` dos
    eventos: a máquina age sem pessoa atrás, e fingir uma pessoa ali seria
    inventar autoria.
    """

    encomenda = models.ForeignKey(
        Encomenda, related_name="historico", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    # Vazio só na linha de nascimento, se um dia alguém quiser registrá-la.
    de = models.CharField(max_length=20, blank=True, default="")
    para = models.CharField(max_length=20)
    ator_id = id_da_plataforma()
    motivo = models.CharField(max_length=200, blank=True, default="")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["em", "id"]
        verbose_name = "mudança de status"
        verbose_name_plural = "mudanças de status"
        indexes = [
            models.Index(fields=["encomenda", "em"], name="enc_historico_por_data")
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(para=""), name="mudanca_de_status_diz_para_onde"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.encomenda_id}: {self.de or '(nascimento)'} -> {self.para}"


# ---------------------------------------------------------------------------
# 4. A OFERTA — registro de primeira classe: é o histórico e a auditoria de justiça
# ---------------------------------------------------------------------------


class Oferta(models.Model):
    """Uma encomenda oferecida a um aluno, com relógio.

    Não é linha de trabalho: é REGISTRO DE PRIMEIRA CLASSE (plano §7.1). É por
    ela que se audita se a fila foi justa, é dela que saem os três usos do
    "passar com motivo" (métricas, reclassificação por dois `nao_me_sinto_pronto`
    na mesma encomenda, aviso ao professor por três em 30 dias), e é ela que faz
    [INV-ENC-J1] e [INV-ENC-J2] serem verificáveis de fora.

    **As duas travas de uma oferta pendente já são do BANCO**, por índice único
    parcial. Os invariantes J1 e J2 e os guardas deles nascem com o motor, no
    degrau 2.3 — o que nasce aqui é o mecanismo que os torna impossíveis de
    violar, inclusive por dois processos do motor rodando ao mesmo tempo, que é
    a corrida que nenhum `if` em Python resolve.
    """

    class Resultado(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITA = "aceita", "Aceita"
        PASSOU = "passou", "O aluno passou"
        EXPIROU = "expirou", "O relógio expirou"
        CANCELADA = "cancelada", "Cancelada"

    class MotivoDoPasse(models.TextChoices):
        SEM_TEMPO = "sem_tempo", "Sem tempo agora"
        VALOR_BAIXO = "valor_baixo", "Valor baixo"
        NAO_CURTO = "nao_curto", "Não curto esse tipo"
        NAO_ME_SINTO_PRONTO = "nao_me_sinto_pronto", "Ainda não me sinto pronto"

    TRANSICOES: dict[str, frozenset[str]] = {
        Resultado.PENDENTE: frozenset(
            {
                Resultado.ACEITA,
                Resultado.PASSOU,
                Resultado.EXPIROU,
                Resultado.CANCELADA,
            }
        ),
        Resultado.ACEITA: frozenset(),
        Resultado.PASSOU: frozenset(),
        Resultado.EXPIROU: frozenset(),
        Resultado.CANCELADA: frozenset(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = id_do_site()
    encomenda = models.ForeignKey(
        Encomenda, related_name="ofertas", on_delete=models.PROTECT
    )
    aluno = models.ForeignKey(
        PerfilProfissional, related_name="ofertas", on_delete=models.PROTECT
    )

    oferecida_em = models.DateTimeField(auto_now_add=True)
    # Calculado com a janela de horas úteis: o relógio corre só das 8h às 22h de
    # São Paulo e congela fora dela ([INV-ENC-J8], degrau 2.4). A conta é do
    # relógio; a tabela só guarda o instante que ela devolveu.
    expira_em = models.DateTimeField()
    # Qual rodada de ofertas desta encomenda (campo `rodada` de
    # `encomenda.oferecida.v1`): abandono e reclassificação abrem rodada nova.
    rodada = models.PositiveSmallIntegerField(default=1)

    resultado = models.CharField(
        max_length=10, choices=Resultado.choices, default=Resultado.PENDENTE
    )
    motivo_passe = models.CharField(
        max_length=20, choices=MotivoDoPasse.choices, blank=True, default=""
    )
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-oferecida_em"]
        indexes = [
            # A varredura do tique: as ofertas pendentes já vencidas.
            models.Index(
                fields=["resultado", "expira_em"], name="enc_ofertas_a_expirar"
            ),
        ]
        constraints = [
            # [INV-ENC-J1], no banco: uma encomenda nunca tem duas ofertas
            # pendentes. Índice único PARCIAL — as ofertas já respondidas se
            # acumulam de propósito, porque são o histórico.
            models.UniqueConstraint(
                fields=["encomenda"],
                condition=models.Q(resultado="pendente"),
                name="uma_oferta_pendente_por_encomenda",
            ),
            # [INV-ENC-J2], no banco: um aluno nunca tem duas ofertas pendentes.
            models.UniqueConstraint(
                fields=["aluno"],
                condition=models.Q(resultado="pendente"),
                name="uma_oferta_pendente_por_aluno",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    resultado__in=[
                        "pendente",
                        "aceita",
                        "passou",
                        "expirou",
                        "cancelada",
                    ]
                ),
                name="resultado_de_oferta_no_vocabulario_fechado",
            ),
            # Motivo só existe em oferta passada, e oferta passada sempre tem
            # motivo: o "passar" da tela abre quatro botões, e um passe sem
            # motivo não alimentaria nenhum dos três usos do plano §6.11.
            models.CheckConstraint(
                condition=(models.Q(resultado="passou") & ~models.Q(motivo_passe=""))
                | (~models.Q(resultado="passou") & models.Q(motivo_passe="")),
                name="motivo_de_passe_so_em_oferta_passada",
            ),
            # Pendente é a única sem data de resposta. Sem esta trava, uma oferta
            # "aceita" sem `respondida_em` faria a auditoria de justiça responder
            # "não sei quando" para o gesto mais importante da fila.
            models.CheckConstraint(
                condition=(
                    models.Q(resultado="pendente", respondida_em=None)
                    | (
                        ~models.Q(resultado="pendente")
                        & models.Q(respondida_em__isnull=False)
                    )
                ),
                name="oferta_respondida_tem_data",
            ),
            models.CheckConstraint(
                condition=models.Q(expira_em__gt=models.F("oferecida_em")),
                name="oferta_expira_depois_de_oferecida",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.encomenda_id} -> {self.aluno_id} ({self.resultado})"

    def pode_ir_para(self, resultado: str) -> bool:
        return resultado in self.TRANSICOES.get(self.resultado, frozenset())

    def responder(self, resultado: str, *, motivo_passe: str = "", em):
        """Fecha a oferta, ou recusa com `TransicaoProibida`.

        Oferta fechada é PEDRA: aceita não vira passada, expirada não vira
        aceita. É o que permite auditar a fila meses depois sem perguntar a
        ninguém o que aconteceu.
        """
        if not self.pode_ir_para(resultado):
            raise TransicaoProibida(
                f"oferta {self.pk}: {self.resultado} nao vai para {resultado}. "
                f"As transicoes permitidas sao {sorted(self.TRANSICOES[self.resultado])}."
            )
        self.resultado = resultado
        self.motivo_passe = motivo_passe
        self.respondida_em = em
        self.save(update_fields=["resultado", "motivo_passe", "respondida_em"])
        return self


# ---------------------------------------------------------------------------
# 5. OS PARÂMETROS — dado, com histórico por linha nova, nunca UPDATE
# ---------------------------------------------------------------------------

# O VOCABULÁRIO FECHADO das chaves, com o tipo de cada uma (lei §6; os tipos são
# os do `Parametro` do contrato em papel). É a lista que um humano lê inteira em
# trinta segundos, e é o que impede a tabela de virar um saco de configuração:
# chave nova é diff visível aqui, e o banco recusa qualquer outra.
#
# **Os VALORES não moram neste arquivo**, e a ausência é a lei §3.8 em ação:
# eles nascem em `management/commands/semear_parametros.py`, entram no banco e
# mudam por linha nova, sem PR. Se um dia um número da lei §6 voltar a viver em
# código, isso é o critério de morte 5 da lei §9 — pare e reabra a decisão.
# Guarda: `tests/test_parametros_sao_dado.py`.
CHAVES_DE_PARAMETRO: dict[str, tuple[str, str]] = {
    "relogio_da_oferta": ("horas", "Horas úteis que o aluno tem para responder"),
    "janela_inicio": ("hora_do_dia", "Hora em que o relógio da oferta volta a correr"),
    "janela_fim": ("hora_do_dia", "Hora em que o relógio da oferta congela"),
    "silencios_para_pausa": ("inteiro", "Silêncios seguidos que pausam o aluno"),
    "horas_para_virar_aberta": ("horas", "Horas na fila até a chamada aberta"),
    "encomendas_simultaneas_por_aluno": (
        "inteiro",
        "Encomendas da fila que um aluno faz ao mesmo tempo",
    ),
    "prazo_producao.simples": ("dias", "Prazo de produção do cartão item simples"),
    "prazo_producao.vestivel_veiculo": (
        "dias",
        "Prazo de produção do cartão vestível ou veículo",
    ),
    "prazo_producao.personagem": ("dias", "Prazo de produção do cartão personagem"),
    "dias_de_revisao_no_prazo_prometido": (
        "dias",
        "Dias somados ao prazo prometido ao cliente",
    ),
    "extensoes_por_encomenda": ("inteiro", "Extensões de prazo por encomenda"),
    "extensao_horas": ("horas", "Duração de cada extensão"),
    "extensao_pedida_ate_horas_antes": (
        "horas",
        "Antecedência mínima para pedir a extensão",
    ),
    "sla_do_revisor": ("horas", "Prazo do revisor antes de escalar ao plantão"),
    "amostragem_de_revisao": (
        "inteiro",
        "Uma em cada N entregas é revisada depois da primeira",
    ),
    "aprovacao_tacita": ("horas", "Silêncio do cliente que aprova a entrega"),
    "correcoes_incluidas": ("inteiro", "Correções que o cliente pede sem custo"),
    "prazo_da_correcao": ("horas", "Prazo do aluno para entregar a correção"),
    "passes_nao_pronto_para_reclassificar": (
        "inteiro",
        "Passes por falta de preparo, na mesma encomenda, que a mandam ao plantão",
    ),
    "passes_nao_pronto_para_aviso": (
        "inteiro",
        "Passes por falta de preparo, do mesmo aluno, que avisam o professor",
    ),
    "janela_dos_passes": (
        "dias",
        "Janela em que os passes por falta de preparo contam",
    ),
    "repasse_apos_aprovacao": ("enum", "Quando o repasse sai depois da aprovação"),
    "meta_aprovacao_cliente_novo": (
        "horas",
        "Meta do plantão para aprovar um cliente novo",
    ),
    "entregas_para_nivel_intermediario": (
        "inteiro",
        "Entregas aprovadas exigidas no nível intermediário",
    ),
    "entregas_para_nivel_avancado": (
        "inteiro",
        "Entregas aprovadas exigidas no nível avançado",
    ),
    "janela_sem_abandono": ("dias", "Janela sem abandono exigida no nível avançado"),
    "pausa_por_segundo_abandono": (
        "dias",
        "Pausa depois do segundo abandono na janela",
    ),
}

# O tamanho mínimo do motivo, do `MudancaDeParametro` do contrato em papel. Não é
# número de negócio (não está na lei §6): é a régua de "escreveu por quê", e ela
# existe porque um histórico com motivo "ajuste" não responde nada seis meses
# depois.
TAMANHO_MINIMO_DO_MOTIVO = 15


class Parametro(models.Model):
    """Uma LINHA de histórico de um parâmetro. Mudar é acrescentar, nunca editar.

    Lei §3.8, e a mesma regra que a gamificação já tem ("a economia é dado, nunca
    código"). O motor lê o valor vigente **em `agora`** (`vigente_em`), e é isso
    que faz um parâmetro mudado às 15h não reescrever uma oferta feita às 14h.

    **`UPDATE` e `DELETE` são recusados pelo PostgreSQL**, por gatilho. Sem o
    gatilho, "nunca UPDATE" seria uma frase num documento: a tela do Admin
    (`/admin/encomendas/parametros/`, degrau 2.7 em diante) grava por esta
    tabela, e o caminho mais curto para quem a escrever é `objects.update()`. Com
    o gatilho, esse caminho não existe — nem pela tela, nem por migração de
    dados, nem por `psql`.

    `valor` é SEMPRE texto: a chave diz o tipo (`CHAVES_DE_PARAMETRO`) e a célula
    valida. É o que o contrato em papel já promete ao Admin, e é o que permite
    `08:00` e `proximo_dia_util` conviverem com `3` na mesma coluna sem uma
    tabela por tipo.
    """

    site_id = id_do_site()
    chave = models.CharField(max_length=60)
    valor = models.CharField(max_length=60)
    # Desde quando esta linha vale. Não é `auto_now_add`: o mantenedor pode
    # marcar uma mudança para valer a partir de um instante escolhido, e a
    # leitura por `agora` depende disso ser um dado, não o relógio do INSERT.
    desde = models.DateTimeField()
    motivo = models.TextField()
    # Id da plataforma de quem mudou. Vazio só na semente, que não tem pessoa
    # atrás: quem semeia é a instalação da célula.
    quem = id_da_plataforma()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["site_id", "chave", "-desde"]
        verbose_name = "parâmetro"
        verbose_name_plural = "parâmetros"
        indexes = [
            models.Index(
                fields=["site_id", "chave", "-desde"], name="enc_parametro_vigente"
            ),
        ]
        constraints = [
            # Duas linhas da mesma chave valendo do mesmo instante seriam duas
            # respostas para "quanto vale agora", e a escolhida dependeria da
            # ordem do índice. O banco recusa a pergunta ambígua.
            models.UniqueConstraint(
                fields=["site_id", "chave", "desde"],
                name="uma_linha_por_chave_por_momento",
            ),
            models.CheckConstraint(
                condition=models.Q(chave__in=sorted(CHAVES_DE_PARAMETRO)),
                name="chave_de_parametro_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=~models.Q(valor=""), name="parametro_tem_valor"
            ),
            models.CheckConstraint(
                condition=models.Q(motivo__length__gte=TAMANHO_MINIMO_DO_MOTIVO),
                name="mudanca_de_parametro_tem_motivo_escrito",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.chave}={self.valor} desde {self.desde:%d/%m/%Y}"

    @property
    def tipo(self) -> str:
        """O tipo declarado da chave. Uma fonte só, o catálogo."""
        return CHAVES_DE_PARAMETRO[self.chave][0]

    @classmethod
    def vigente_em(cls, chave: str, agora, *, site_id: str):
        """A linha que vale NO INSTANTE `agora`, ou `None` se ainda não vale nenhuma.

        A regra inteira da lei §3.8 cabe nesta consulta, e é de propósito que ela
        mora aqui e não no motor: duas expressões da mesma conta divergem no
        primeiro dia em que alguém mexer numa delas, e aqui divergir significa
        uma oferta feita às 14h ser julgada pelo valor das 15h.

        Devolver `None` em vez de um padrão embutido é deliberado: um padrão em
        código seria exatamente a constante mágica que a lei proíbe, e ele
        esconderia uma semeadura que não rodou.
        """
        return (
            cls.objects.filter(site_id=site_id, chave=chave, desde__lte=agora)
            .order_by("-desde")
            .first()
        )
