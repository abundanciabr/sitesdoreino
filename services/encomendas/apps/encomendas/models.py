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
# Os 19 estados, na ordem da linha principal — eram 15 até 04/09/2026, quando o
# mantenedor liberou a negociação e o mural aberto e quatro entraram:
# `no_mural`, `reservada`, `em_negociacao` e `acordada`
# (`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md`). `Encomenda.Status` repete os
# mesmos valores porque é ele quem dá o RÓTULO que a tela mostra; que as duas
# listas nunca divirjam é o que
# `tests/test_maquinas_de_estado.py::test_os_estados_do_textchoices_sao_os_da_maquina`
# faz valer.
#
# A ORDEM DESTA LISTA MUDOU, e a mudança é a notícia: `aguardando_pagamento`
# saiu da primeira posição e foi para o meio. Ele era o estado inicial porque o
# preço vinha da tabela e já se conhecia antes de qualquer aluno ver o pedido;
# com a negociação, o valor só existe depois do acordo, e não se cobra um valor
# que ainda não foi combinado.
ESTADOS_DE_ENCOMENDA = [
    "na_fila",
    "no_mural",
    "oferecida",
    "reservada",
    "aberta",
    "em_negociacao",
    "acordada",
    "aguardando_pagamento",
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
        "no_mural",
        "oferecida",
        "reservada",
        "aberta",
        "em_negociacao",
        "acordada",
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
    # A ENCOMENDA NASCE NUMA PISTA, NÃO NO CAIXA. Até 04/09/2026 o estado
    # inicial era `aguardando_pagamento`, e tinha de ser: o preço vinha da
    # tabela, então já se conhecia antes de qualquer aluno ver o pedido. Com a
    # negociação que o mantenedor liberou, o valor só existe DEPOIS do acordo —
    # e não se cobra um valor que ainda não foi combinado
    # (`PLANO-AREA-DE-NEGOCIACAO.md` §5). O caixa não sumiu; ele mudou de
    # lugar, e agora fica entre `acordada` e `em_producao`.
    "na_fila": {"oferecida", "aberta", "para_reclassificar", "cancelada"},
    # A segunda pista. Quem chega aqui é projeto de nível Intermediário ou
    # Avançado, porque a elegibilidade da lei já exige 1 e 5 entregas para eles
    # — e projeto Iniciante que a fila não colocou em 24h, pela chamada aberta.
    # `para_reclassificar` é o destino do projeto que passou 24h sem NENHUM
    # elegível disponível: nos primeiros meses ninguém terá entrega aprovada, e
    # sem esta seta ele ficaria parado para sempre, sem ninguém saber.
    "no_mural": {"reservada", "para_reclassificar", "cancelada"},
    # Aceitar uma oferta deixou de ser começar a produzir: é começar a
    # NEGOCIAR. O aluno aceita, propõe valor e prazo, e só o acordo leva à
    # produção.
    "oferecida": {"na_fila", "em_negociacao", "aberta", "para_reclassificar"},
    # O aluno pegou no Mural e tem relógio. Vencido sem proposta, volta ao
    # Mural para o próximo — e nunca para quem já o teve.
    "reservada": {"em_negociacao", "no_mural", "para_reclassificar"},
    # Chamada aberta: o primeiro que aceitar leva, e leva PARA A NEGOCIAÇÃO.
    "aberta": {"em_negociacao", "para_reclassificar"},
    # As três saídas da negociação, e a diferença entre elas é quem ficou
    # calado (`PLANO-AREA-DE-NEGOCIACAO.md` §4.2):
    #   acordada             -> os dois fecharam;
    #   na_fila / no_mural   -> o ALUNO calou ou desistiu: volta à pista dele,
    #                           e ele não perde o lugar na fila;
    #   para_reclassificar   -> o CLIENTE calou, ou as rodadas se esgotaram.
    #                           Vai ao plantão, NUNCA ao próximo aluno: mandar
    #                           ao próximo faria cada aluno da fila gastar a
    #                           própria vez num cliente fantasma, um depois do
    #                           outro, e nenhum saberia por quê.
    "em_negociacao": {"acordada", "na_fila", "no_mural", "para_reclassificar"},
    # O acordo congelou valor, prazo, entregáveis e correções. Agora sim, o
    # caixa.
    "acordada": {"aguardando_pagamento", "cancelada"},
    # E daqui só se sai para a produção: o prazo do acordo começa a contar na
    # confirmação do pagamento, não no acordo, senão a demora de quem confirma
    # viraria atraso do aluno ([INV-ENC-N8]).
    "aguardando_pagamento": {"em_producao", "cancelada"},
    "em_producao": {"entregue", "abandonada"},
    # A auditoria automática reprovou: volta ao aluno antes de humano nenhum ver.
    "entregue": {"em_revisao", "em_producao"},
    # O revisor devolveu com notas.
    "em_revisao": {"aguardando_cliente", "em_producao"},
    "aguardando_cliente": {"aprovada", "em_correcao"},
    "em_correcao": {"entregue"},
    # O plantão devolve à pista de origem, e por isso as duas setas.
    "para_reclassificar": {"na_fila", "no_mural", "cancelada"},
    "abandonada": {"na_fila", "no_mural"},
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

# Os dois estados do Mural reservável, que são a prateleira e a mão que pegou.
# O projeto pinga entre eles enquanto procura aluno (está `no_mural`, alguém
# pega e ele fica `reservada`, o relógio vence e ele volta a `no_mural`),
# exatamente como pinga entre `na_fila` e `oferecida` na outra pista.
#
# **`aberta` NÃO está aqui, e a ausência é o desenho inteiro do [INV-ENC-M2].**
# O projeto Iniciante nasce na fila e chega ao Mural pela chamada aberta, em que
# o primeiro elegível que aceitar leva, sem reserva, sem vez e sem relógio de
# três horas. Se `aberta` entrasse nesta lista, um único aluno poderia trancar
# por três horas um projeto que a fila já não conseguiu colocar em vinte e
# quatro, e quem pagaria a conta é o cliente.
ESTADOS_DO_MURAL_RESERVAVEL = frozenset({"no_mural", "reservada"})


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

    class Pista(models.TextChoices):
        FILA = "fila", "Na fila (a plataforma escolhe o aluno)"
        MURAL = "mural", "No Mural (o aluno pega)"

    class Confirmacao(models.TextChoices):
        WEBHOOK = "webhook", "Confirmado pelo webhook da célula de pagamentos"
        PLANTAO = "plantao", "Declarado pago pelo plantão (a escola é a cliente)"

    class Status(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        NO_MURAL = "no_mural", "No Mural"
        OFERECIDA = "oferecida", "Oferecida a um aluno"
        RESERVADA = "reservada", "Pega por um aluno no Mural"
        ABERTA = "aberta", "Chamada aberta"
        EM_NEGOCIACAO = "em_negociacao", "Em negociação"
        ACORDADA = "acordada", "Acordo fechado"
        AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
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
    # POR ONDE ESTA ENCOMENDA CHEGA AO ALUNO. O nível decide a pista
    # (`PLANO-AREA-DE-NEGOCIACAO.md` §3.1): Iniciante nasce na fila, porque é
    # ela que garante o primeiro trabalho de quem nunca entregou; Intermediário
    # e Avançado nascem no Mural, porque a elegibilidade da lei já exige 1 e 5
    # entregas aprovadas para eles. É coluna, e não conta derivada do nível,
    # porque a chamada aberta MOVE um projeto Iniciante para o Mural sem mudar
    # o nível dele — e quem pergunta "onde este projeto está sendo mostrado?"
    # precisa de uma resposta, não de uma regra para reexecutar.
    pista = models.CharField(max_length=6, choices=Pista.choices, default=Pista.FILA)
    cliente_id = id_da_plataforma()
    cartao = models.CharField(max_length=20, choices=Cartao.choices)
    nivel = models.CharField(max_length=14, choices=Nivel.choices)
    # As respostas do briefing blindado (plano §5.2). Json e não colunas porque
    # a letra miúda de cada cartão é diferente e muda sem migração. **Sem campo
    # de contato**: [INV-ENC-S1] e [INV-ENC-S3] são exatamente sobre isso, e o
    # guarda deles nasce na Fase 3.
    briefing = models.JSONField(default=dict, blank=True)

    # O PREÇO DE REFERÊNCIA, e ele deixou de ser o preço final em 04/09/2026.
    # Com a negociação, a tabela vira régua e não lei: ela dá ao cliente uma
    # ideia de custo, ao aluno um chão para ancorar a proposta, e ao plantão uma
    # medida para enxergar proposta muito fora da curva
    # (`PLANO-AREA-DE-NEGOCIACAO.md` §4.4). O valor que vale é
    # `acordo_valor_cents`, e são DUAS colunas de propósito: uma coluna com dois
    # significados dependendo do estado é a forma mais barata de um relatório
    # somar referência com acordo e ninguém perceber.
    preco_cents = models.PositiveIntegerField(default=0)
    taxa_cents = models.PositiveIntegerField(default=0)

    # ── O ACORDO, que congela o combinado ────────────────────────────────────
    # Todos nascem NULOS e só o fechamento do acordo os preenche. Depois disso
    # não mudam: mexer neles pede mediação com autor e motivo registrados
    # ([INV-ENC-N3]). É este bloco que torna a disputa julgável — sem ele, uma
    # reclamação de "não é o que eu pedi" é palavra contra palavra.
    #
    # As tabelas `Proposta` e `Acordo` (as rodadas, as contrapropostas, o
    # histórico da conversa) NÃO nascem aqui: são a TAR-134. O que mora nesta
    # tabela é só o RESULTADO congelado, porque é dele que a produção, o prazo e
    # a mediação dependem.
    acordo_valor_cents = models.PositiveIntegerField(null=True, blank=True)
    acordo_prazo_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    acordo_entregaveis = models.JSONField(default=list, blank=True)
    acordo_correcoes_inclusas = models.PositiveSmallIntegerField(null=True, blank=True)
    acordado_em = models.DateTimeField(null=True, blank=True)

    # Preenchidos no aceite: o prazo de produção pelo cartão, e o prometido ao
    # cliente = produção + o dia de revisão (plano §5.1). Os dois são
    # parâmetro, e por isso não há número nenhum aqui.
    prazo_producao_ate = models.DateTimeField(null=True, blank=True)
    prazo_prometido_ate = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NA_FILA
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
            # [INV-ENC-M2] NO BANCO: projeto Iniciante nunca senta no Mural
            # reservável. Ele nasce na fila, porque é ela que garante o primeiro
            # trabalho de quem nunca entregou, e a única porta dele para o Mural
            # é a chamada aberta, que é o estado `aberta`
            # (`PLANO-AREA-DE-NEGOCIACAO.md` §3.1).
            #
            # A máquina de estado já ajuda: `na_fila` não tem seta para
            # `no_mural`, e o gatilho do PostgreSQL recusa a transição. Mas
            # gatilho de transição não vê INSERT, e é por isso que esta linha
            # existe: sem ela, uma tela futura, uma migração de dados ou um
            # `psql` de madrugada criariam um Iniciante já `no_mural`, pulando a
            # fila inteira sem violar transição nenhuma.
            models.CheckConstraint(
                condition=~models.Q(nivel="iniciante")
                | ~models.Q(status__in=sorted(ESTADOS_DO_MURAL_RESERVAVEL)),
                name="iniciante_nunca_no_mural_reservavel",
            ),
            # A coluna `pista` não pode mentir sobre onde o projeto está sendo
            # mostrado. Um projeto `no_mural` com `pista=fila` seria lido de dois
            # jeitos por dois pedaços de código (a tela do aluno e a varredura do
            # plantão), e o segundo a ler é o que erra.
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(ESTADOS_DO_MURAL_RESERVAVEL))
                | models.Q(pista="mural"),
                name="no_mural_so_na_pista_do_mural",
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
            # [INV-ENC-N6], a metade que vale ANTES da primeira proposta: um
            # aluno nunca tem dois projetos em negociação ao mesmo tempo,
            # somando as duas pistas. A trava gêmea da `Proposta`
            # (`uma_proposta_viva_por_aluno`) só existe depois que alguém
            # propõe; entre o aceite e a primeira proposta é esta linha que
            # segura, e sem ela o aluno acumularia negociações que não pode
            # cumprir. Índice PARCIAL, porque as encomendas que já saíram da
            # negociação são o histórico dele.
            models.UniqueConstraint(
                fields=["aluno"],
                condition=models.Q(status="em_negociacao"),
                name="uma_negociacao_viva_por_aluno",
            ),
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
# 5. A RESERVA DO MURAL — a vez de quem pegou, e a prova de que não é leilão
# ---------------------------------------------------------------------------


class ReservaDoMural(models.Model):
    """Um aluno pegou um projeto no Mural e ganhou a vez, com relógio.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.2. É a gêmea da `Oferta` na outra
    pista, e a diferença entre as duas é quem escolheu: na fila, a plataforma
    oferece ao próximo da vez; no Mural, o aluno pega. O resto é igual, e de
    propósito, porque as duas respondem à mesma pergunta de auditoria ("quem
    teve este projeto, quando, e o que aconteceu").

    O MURAL NÃO É LEILÃO, E QUEM FAZ ISSO VALER É O BANCO
    ------------------------------------------------------
    *"Nunca existem duas propostas vivas para o mesmo projeto"* (§3.2). A trava
    é um índice único PARCIAL sobre `encomenda`, e ela é parcial porque as
    reservas mortas se acumulam de propósito: são elas a memória de quem já
    teve o projeto. Nenhum `if` em Python resolveria a corrida de dois alunos
    tocando "Pegar" no mesmo segundo, que é justamente o segundo em que um
    Mural de verdade é disputado.

    E A SEGUNDA TRAVA É A QUE SURPREENDE
    -------------------------------------
    `Unique(encomenda, aluno)`, sem condição nenhuma: **ninguém pega duas vezes
    o mesmo projeto**, nem depois de a reserva vencer. É a mesma forma do
    [INV-ENC-J6] na outra pista, e sem ela o projeto giraria sem sair do lugar
    (o mesmo aluno pega, deixa vencer, pega de novo). A regra também é lida
    pelo caminho educado, em `mural.vaga_de`, para o aluno receber uma frase em
    vez de um `IntegrityError`; o índice é o que sobra quando alguém esquece.

    O RELÓGIO PARA NA PRIMEIRA PROPOSTA, E ESSE É O ESTADO `negociando`
    -------------------------------------------------------------------
    As 3 horas úteis são para o aluno olhar o briefing e propor, e só até isso
    (§3.2). Assim que ele propõe, o relógio da reserva PARA e quem manda passam
    a ser os relógios da negociação, que duram 24 horas úteis por rodada. Sem
    essa passagem de bastão os dois números do §9 se contradiziam: a reserva
    venceria no meio da primeira rodada, e o projeto voltaria ao Mural com uma
    proposta de pé.

    **Quem escreve `negociando` é a TAR-134**, no mesmo gesto que cria a
    primeira `Proposta`. O estado nasce aqui porque a trava de "uma reserva
    viva" precisa saber, desde já, que uma reserva em negociação continua VIVA
    (o projeto não voltou ao Mural) — e um estado que chegasse depois faria o
    índice parcial mudar de significado num PR que ninguém ia ler duas vezes.
    """

    class Resultado(models.TextChoices):
        PENDENTE = "pendente", "A vez está de pé, e o relógio corre"
        NEGOCIANDO = "negociando", "A primeira proposta chegou, e o relógio parou"
        EXPIROU = "expirou", "O relógio venceu sem proposta"

    # Reserva fechada é PEDRA, como a oferta: `negociando` não volta a
    # `pendente` (o relógio não ressuscita) e `expirou` não vira nada. É o que
    # permite auditar o Mural meses depois sem perguntar a ninguém.
    TRANSICOES: dict[str, frozenset[str]] = {
        Resultado.PENDENTE: frozenset({Resultado.NEGOCIANDO, Resultado.EXPIROU}),
        Resultado.NEGOCIANDO: frozenset(),
        Resultado.EXPIROU: frozenset(),
    }

    # As duas em que o projeto NÃO está de volta na prateleira. É esta lista que
    # o índice único parcial usa, e é ela que define "reserva viva".
    VIVAS = (Resultado.PENDENTE, Resultado.NEGOCIANDO)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = id_do_site()
    encomenda = models.ForeignKey(
        Encomenda, related_name="reservas_do_mural", on_delete=models.PROTECT
    )
    aluno = models.ForeignKey(
        PerfilProfissional, related_name="reservas_do_mural", on_delete=models.PROTECT
    )

    pegada_em = models.DateTimeField(auto_now_add=True)
    # Calculado com a MESMA janela de horas úteis da oferta ([INV-ENC-J8]): o
    # relógio corre das 8h às 22h de São Paulo e congela fora dela. A conta é do
    # `relogio.calcular_expiracao_da_reserva`; a tabela só guarda o instante que
    # ela devolveu.
    expira_em = models.DateTimeField()

    resultado = models.CharField(
        max_length=10, choices=Resultado.choices, default=Resultado.PENDENTE
    )
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "reserva do mural"
        verbose_name_plural = "reservas do mural"
        ordering = ["-pegada_em"]
        indexes = [
            # A varredura do tique: as reservas pendentes já vencidas.
            models.Index(
                fields=["resultado", "expira_em"], name="enc_reservas_a_expirar"
            ),
        ]
        constraints = [
            # [INV-ENC-M3], primeira metade: o Mural não é leilão. Índice único
            # PARCIAL, porque as reservas mortas se acumulam de propósito.
            models.UniqueConstraint(
                fields=["encomenda"],
                condition=models.Q(resultado__in=["pendente", "negociando"]),
                name="uma_reserva_viva_por_encomenda",
            ),
            # [INV-ENC-M3], segunda metade: o projeto que voltou ao Mural não
            # volta para quem já o teve. Sem condição: vale para sempre.
            models.UniqueConstraint(
                fields=["encomenda", "aluno"],
                name="ninguem_pega_o_mesmo_projeto_duas_vezes",
            ),
            models.CheckConstraint(
                condition=models.Q(resultado__in=["pendente", "negociando", "expirou"]),
                name="resultado_de_reserva_no_vocabulario_fechado",
            ),
            # Pendente é a única sem data de resposta, como na `Oferta`. Sem esta
            # trava, uma reserva "expirou" sem `respondida_em` faria a auditoria
            # do Mural responder "não sei quando" para o gesto que decide de
            # quem era a vez.
            models.CheckConstraint(
                condition=(
                    models.Q(resultado="pendente", respondida_em=None)
                    | (
                        ~models.Q(resultado="pendente")
                        & models.Q(respondida_em__isnull=False)
                    )
                ),
                name="reserva_respondida_tem_data",
            ),
            models.CheckConstraint(
                condition=models.Q(expira_em__gt=models.F("pegada_em")),
                name="reserva_expira_depois_de_pegada",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.encomenda_id} <- {self.aluno_id} ({self.resultado})"

    def pode_ir_para(self, resultado: str) -> bool:
        return resultado in self.TRANSICOES.get(self.resultado, frozenset())

    def responder(self, resultado: str, *, em):
        """Fecha a reserva, ou recusa com `TransicaoProibida`."""
        if not self.pode_ir_para(resultado):
            raise TransicaoProibida(
                f"reserva {self.pk}: {self.resultado} nao vai para {resultado}. "
                f"As transicoes permitidas sao {sorted(self.TRANSICOES[self.resultado])}."
            )
        self.resultado = resultado
        self.respondida_em = em
        self.save(update_fields=["resultado", "respondida_em"])
        return self


# ---------------------------------------------------------------------------
# 6. A PROPOSTA — o formulário que vai e volta, e nunca uma caixa de mensagem
# ---------------------------------------------------------------------------


class Proposta(models.Model):
    """Uma rodada da negociação: valor, prazo, entregáveis, correções e o porquê.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.1 (os seis campos), §4.2 (as
    rodadas e a validade) e §8 (os invariantes N1 a N8). Este é o degrau 2.12 da
    escada (TAR-134).

    NEGOCIAR NÃO É CONVERSAR, E ESSA FRASE É O DESENHO INTEIRO
    -----------------------------------------------------------
    O [INV-ENC-S1] continua valendo e não foi revogado: *não existe texto livre
    trocado entre cliente e aluno fora dos campos estruturados, e todos são
    visíveis ao plantão.* A saída não foi enfraquecer o invariante, e sim
    perceber que negociar é TROCAR PROPOSTAS. Por isso esta tabela tem seis
    campos de negócio e nenhum a mais: não há caixa de mensagem, não há anexo,
    não há resposta fora deles. `justificativa` é o único campo de texto, ele é
    curto por parâmetro (`limite_da_justificativa`) e o plantão o lê inteiro.

    Um campo de texto novo aqui é o [INV-ENC-N1] caindo, e o guarda daquele
    invariante mede a LISTA de campos desta classe justamente para que ele caia
    vermelho em vez de cair em produção.

    A CONTRAPROPOSTA TEM A MESMA FORMA, E POR ISSO É A MESMA TABELA
    ---------------------------------------------------------------
    `de_quem` diz quem preencheu o formulário. Duas tabelas (uma de proposta e
    uma de contraproposta) seriam a mesma coisa escrita duas vezes, e a segunda
    envelheceria em silêncio no primeiro campo novo. Quem propõe PRIMEIRO é
    sempre o aluno, de propósito (§4.2): quem põe preço em trabalho é quem vai
    fazê-lo, e isso evita a âncora baixa, que é o jeito clássico de o comprador
    definir o preço antes de o profissional falar.

    AS RODADAS SÃO CONTADAS PELO BANCO, E NÃO POR UM `if`
    -----------------------------------------------------
    `uma_rodada_por_lado_por_projeto` é o [INV-ENC-N2] em índice: o mesmo lado
    não escreve duas vezes a mesma rodada, nem por corrida, nem por uma tela
    futura com dois cliques. O TETO (o parâmetro `rodadas_de_negociacao`) é lido
    em `negociacao.propor`, porque ele muda sem PR e um `CHECK` com número
    dentro seria a constante mágica que a lei §3.8 proíbe.

    E AS DUAS TRAVAS DE "UMA SÓ VIVA"
    ----------------------------------
    `uma_proposta_viva_por_encomenda` é a metade do [INV-ENC-M3] que continua
    valendo aqui: nunca existem duas propostas de pé para o mesmo projeto.
    `uma_proposta_viva_por_aluno` é a segunda metade do [INV-ENC-N6], e ela vale
    somando as duas pistas porque a coluna `aluno` não sabe de onde o projeto
    veio. As duas são PARCIAIS: as propostas mortas se acumulam de propósito,
    porque são elas o histórico da negociação que a mediação vai ler.
    """

    class DeQuem(models.TextChoices):
        ALUNO = "aluno", "O aluno, que vai fazer o trabalho"
        CLIENTE = "cliente", "O cliente, que pediu o trabalho"

    class Resultado(models.TextChoices):
        PENDENTE = "pendente", "De pé, esperando o outro lado"
        ACEITA = "aceita", "O outro lado aceitou, e nasceu o Acordo"
        SUPERADA = "superada", "O outro lado respondeu com uma contraproposta"
        RECUSADA = "recusada", "Recusada sem contraproposta: as rodadas acabaram"
        EXPIROU = "expirou", "A validade venceu sem resposta"
        RETIRADA = "retirada", "Quem propôs desistiu antes da resposta"

    # Proposta fechada é PEDRA, como a oferta e a reserva: nada volta a
    # `pendente`. É o que permite a mediação de daqui a seis meses reconstruir a
    # negociação inteira sem perguntar a ninguém.
    TRANSICOES: dict[str, frozenset[str]] = {
        Resultado.PENDENTE: frozenset(
            {
                Resultado.ACEITA,
                Resultado.SUPERADA,
                Resultado.RECUSADA,
                Resultado.EXPIROU,
                Resultado.RETIRADA,
            }
        ),
        Resultado.ACEITA: frozenset(),
        Resultado.SUPERADA: frozenset(),
        Resultado.RECUSADA: frozenset(),
        Resultado.EXPIROU: frozenset(),
        Resultado.RETIRADA: frozenset(),
    }

    # A única em que a proposta ainda está de pé. É esta lista que os dois
    # índices parciais usam, e é ela que define "negociação viva".
    VIVAS = (Resultado.PENDENTE,)

    # OS SEIS CAMPOS DA §4.1, E NENHUM A MAIS. A lista mora aqui, e não dentro
    # do guarda, porque é ela que a tela do plantão (Fase 7) desenha: uma
    # segunda lista no teste seria a segunda régua que diverge no primeiro campo
    # novo.
    CAMPOS_DO_FORMULARIO = (
        "valor_cents",
        "prazo_dias",
        "entregaveis",
        "correcoes_inclusas",
        "justificativa",
        "valida_ate",
    )

    # Os quatro que o Acordo CONGELA na encomenda ([INV-ENC-N3]). São quatro e
    # não seis: a justificativa é o porquê da rodada, e não o combinado, e a
    # validade morre no instante em que alguém aceita.
    CAMPOS_QUE_O_ACORDO_CONGELA = (
        "valor_cents",
        "prazo_dias",
        "entregaveis",
        "correcoes_inclusas",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = id_do_site()
    encomenda = models.ForeignKey(
        Encomenda, related_name="propostas", on_delete=models.PROTECT
    )
    # O ALUNO DA NEGOCIAÇÃO, mesmo na proposta preenchida pelo cliente. A coluna
    # é denormalizada de propósito: sem ela, "uma negociação viva por aluno"
    # ([INV-ENC-N6]) precisaria atravessar a chave estrangeira até a encomenda,
    # e `UniqueConstraint` não atravessa relação nenhuma (`armadilhas/274`).
    aluno = models.ForeignKey(
        PerfilProfissional, related_name="propostas", on_delete=models.PROTECT
    )

    de_quem = models.CharField(max_length=7, choices=DeQuem.choices)
    # A rodada DESTE LADO, contada a partir de 1. O aluno e o cliente têm
    # contadores próprios porque o parâmetro da lei é "3 por lado" (§4.2).
    rodada = models.PositiveSmallIntegerField(default=1)

    # CENTAVOS, INTEIRO, NUNCA `float`. Dinheiro em ponto flutuante é a soma que
    # fecha errado no relatório do fim do mês, e o erro só aparece quando já há
    # dinheiro de gente de verdade dentro.
    valor_cents = models.PositiveIntegerField()
    prazo_dias = models.PositiveSmallIntegerField()
    # A lista fechada que veio do briefing. `JSONField` pela mesma razão do
    # `briefing`: a letra miúda de cada cartão é diferente e muda sem migração.
    entregaveis = models.JSONField(default=list, blank=True)
    correcoes_inclusas = models.PositiveSmallIntegerField()
    # O ÚNICO CAMPO DE TEXTO DA NEGOCIAÇÃO, e ele é curto por parâmetro. O
    # limite não é `max_length` porque `limite_da_justificativa` muda sem PR
    # (lei §3.8): quem o faz valer é `negociacao.propor`, que recusa com razão
    # nomeada antes de gravar.
    justificativa = models.TextField(blank=True, default="")
    # Quando esta proposta vence, em horas ÚTEIS, no mesmo relógio da oferta e
    # da reserva. A conta é de `relogio.calcular_validade_da_proposta`.
    valida_ate = models.DateTimeField()

    criada_em = models.DateTimeField(auto_now_add=True)
    resultado = models.CharField(
        max_length=8, choices=Resultado.choices, default=Resultado.PENDENTE
    )
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "proposta"
        verbose_name_plural = "propostas"
        ordering = ["encomenda", "criada_em"]
        indexes = [
            # A varredura do tique: as propostas de pé já vencidas.
            models.Index(
                fields=["resultado", "valida_ate"], name="enc_propostas_a_expirar"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["id", "site_id"], name="uniq_proposta_id_com_site"
            ),
            # [INV-ENC-M3] na negociação: nunca duas propostas vivas para o
            # mesmo projeto. Parcial, porque as mortas são o histórico.
            models.UniqueConstraint(
                fields=["encomenda"],
                condition=models.Q(resultado="pendente"),
                name="uma_proposta_viva_por_encomenda",
            ),
            # [INV-ENC-N6]: um aluno nunca tem duas negociações vivas, somando
            # as duas pistas. A coluna `aluno` não sabe de que pista o projeto
            # veio, e é isso que faz esta linha valer nas duas.
            models.UniqueConstraint(
                fields=["aluno"],
                condition=models.Q(resultado="pendente"),
                name="uma_proposta_viva_por_aluno",
            ),
            # [INV-ENC-N2] no banco: o mesmo lado não escreve duas vezes a mesma
            # rodada. O TETO é parâmetro e mora em `negociacao.propor`; o que o
            # banco garante é que a contagem não pule nem repita.
            models.UniqueConstraint(
                fields=["encomenda", "de_quem", "rodada"],
                name="uma_rodada_por_lado_por_projeto",
            ),
            models.CheckConstraint(
                condition=models.Q(de_quem__in=["aluno", "cliente"]),
                name="lado_da_proposta_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    resultado__in=[
                        "pendente",
                        "aceita",
                        "superada",
                        "recusada",
                        "expirou",
                        "retirada",
                    ]
                ),
                name="resultado_de_proposta_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=models.Q(rodada__gte=1), name="rodada_comeca_em_um"
            ),
            # Proposta de valor zero não é proposta: é o formulário enviado em
            # branco, e ele viraria um acordo de trabalho de graça.
            models.CheckConstraint(
                condition=models.Q(valor_cents__gt=0), name="proposta_tem_valor"
            ),
            models.CheckConstraint(
                condition=models.Q(prazo_dias__gte=1), name="proposta_tem_prazo"
            ),
            # Pendente é a única sem data de resposta, como na `Oferta` e na
            # `ReservaDoMural`. Sem esta trava, uma proposta "expirou" sem data
            # faria a mediação responder "não sei quando".
            models.CheckConstraint(
                condition=(
                    models.Q(resultado="pendente", respondida_em=None)
                    | (
                        ~models.Q(resultado="pendente")
                        & models.Q(respondida_em__isnull=False)
                    )
                ),
                name="proposta_respondida_tem_data",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.encomenda_id} {self.de_quem} r{self.rodada} ({self.resultado})"

    def pode_ir_para(self, resultado: str) -> bool:
        return resultado in self.TRANSICOES.get(self.resultado, frozenset())

    def responder(self, resultado: str, *, em):
        """Fecha a proposta, ou recusa com `TransicaoProibida`."""
        if not self.pode_ir_para(resultado):
            raise TransicaoProibida(
                f"proposta {self.pk}: {self.resultado} nao vai para {resultado}. "
                f"As transicoes permitidas sao {sorted(self.TRANSICOES[self.resultado])}."
            )
        self.resultado = resultado
        self.respondida_em = em
        self.save(update_fields=["resultado", "respondida_em"])
        return self

    @property
    def o_outro_lado(self) -> str:
        """Quem tem de responder a esta proposta. Uma definição só, e não um `if` por chamada."""
        return (
            self.DeQuem.CLIENTE
            if self.de_quem == self.DeQuem.ALUNO
            else self.DeQuem.ALUNO
        )


# ---------------------------------------------------------------------------
# 7. O ACORDO — o instante em que o combinado virou pedra, e quem o assinou
# ---------------------------------------------------------------------------


class Acordo(models.Model):
    """A aceitação de uma proposta: quem aceitou, quando, e qual formulário virou lei.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.3 e §7 (o registro de quem
    decidiu). É o documento que torna a disputa JULGÁVEL: sem ele, "não é o que
    eu pedi" é palavra contra palavra; com ele, o plantão compara a entrega com
    um formulário que os dois lados aceitaram.

    **ESTA TABELA NÃO GUARDA VALOR, PRAZO, ENTREGÁVEIS NEM CORREÇÕES**, e a
    ausência é a lei da casa: nenhum fato mora em dois lugares. Os quatro
    números do combinado moram na `Proposta` aceita (o formulário) e,
    congelados, nas colunas `acordo_*` da `Encomenda`, de onde a produção, o
    prazo e a mediação os leem. Uma terceira cópia aqui seria a que diverge no
    primeiro dia de mediação. O que esta tabela acrescenta é o que não existe em
    lugar nenhum: **o ATO**, com autor e data.

    O autor é obrigatório, e é o §7 em coluna. Enquanto a única origem for
    `escola`, quem abre o projeto, quem aceita a proposta do aluno e quem media
    a disputa é a mesma equipe; isso não impede o piloto de rodar, e o que faz a
    diferença ficar visível depois é justamente o registro de quem decidiu.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = id_do_site()
    encomenda = models.OneToOneField(
        Encomenda, related_name="acordo", on_delete=models.PROTECT
    )
    proposta = models.OneToOneField(
        Proposta, related_name="acordo", on_delete=models.PROTECT
    )
    aluno = models.ForeignKey(
        PerfilProfissional, related_name="acordos", on_delete=models.PROTECT
    )

    # Quem ACEITOU, e por isso o lado oposto ao da proposta aceita.
    de_quem = models.CharField(max_length=7, choices=Proposta.DeQuem.choices)
    aceito_por = id_da_plataforma()
    aceito_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "acordo"
        verbose_name_plural = "acordos"
        ordering = ["-aceito_em"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(de_quem__in=["aluno", "cliente"]),
                name="lado_do_acordo_no_vocabulario_fechado",
            ),
            # O §7 em uma linha: aceitação sem autor não é aceitação. Vazio aqui
            # faria a auditoria do piloto responder "alguém aceitou" para a
            # pergunta que ela existe para responder.
            models.CheckConstraint(
                condition=~models.Q(aceito_por=""), name="acordo_tem_quem_aceitou"
            ),
        ]

    def __str__(self) -> str:
        return f"acordo de {self.encomenda_id} por {self.aceito_por}"


# ---------------------------------------------------------------------------
# 8. OS PARÂMETROS — dado, com histórico por linha nova, nunca UPDATE
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
    # A 28ª chave, e a primeira que não vem da lei §6: ela vem do §9 do
    # `PLANO-AREA-DE-NEGOCIACAO.md`, a emenda que o mantenedor aprovou em
    # 04/09/2026. Mesmo relógio de horas úteis do `relogio_da_oferta`, medido
    # pela MESMA janela: a reserva do Mural também não corre enquanto o aluno
    # dorme.
    #
    # As outras chaves do §9 daquele plano (as rodadas, a validade da proposta,
    # o piso por nível e o limite da justificativa) NÃO entram aqui: são da
    # negociação, que é a TAR-134. Chave que ninguém lê é configuração morta, e
    # o vocabulário desta tabela é fechado justamente para isso não acontecer.
    #
    # E `entregas_para_ver_o_mural`, que o §9 também lista, não entra NUNCA: a
    # revisão de 04/09/2026 do próprio plano (§3.1) trocou "só quem já entregou
    # vê o Mural" por "o Mural mostra o que o aluno é ELEGÍVEL a pegar", e a
    # elegibilidade já carrega as entregas por nível. Semear aquela chave seria
    # criar uma SEGUNDA régua de elegibilidade ao lado da do motor, e duas
    # réguas divergem no primeiro parâmetro que mudar.
    "relogio_da_reserva_no_mural": (
        "horas",
        "Horas úteis que o aluno tem para propor depois de pegar no Mural",
    ),
    # AS SEIS CHAVES DA NEGOCIAÇÃO (§9 do `PLANO-AREA-DE-NEGOCIACAO.md`,
    # degrau 2.12). Entram aqui porque agora existe quem as leia: sem leitor,
    # chave é configuração morta, e é para isso que este vocabulário é fechado.
    "rodadas_de_negociacao": ("inteiro", "Rodadas de proposta que cada lado tem"),
    "validade_da_proposta": ("horas", "Horas úteis que uma proposta fica de pé"),
    "limite_da_justificativa": (
        "inteiro",
        "Caracteres da justificativa de uma proposta",
    ),
    # O PISO POR NÍVEL NASCE SEM NÚMERO, E A AUSÊNCIA É DECISÃO (§7 e §9). Ele
    # sai do piloto de papel, que é onde os primeiros preços reais vão
    # aparecer; chutar um agora seria inventar um número para depois
    # defendê-lo. A chave existe desde já porque o vocabulário é fechado no
    # banco: sem esta linha, o mantenedor não conseguiria gravar o piso nem
    # quando o tivesse. Enquanto não houver linha, `negociacao.aviso_de_piso`
    # não avisa nada, e NUNCA bloqueia — bloquear seria decidir pelo aluno.
    # A JANELA DA ESTIMATIVA DE ESPERA (degrau 2.7). Quantos dias de historico a
    # conta de `apps/encomendas/espera.py` olha para medir o ritmo de encomendas
    # do nivel de uma pessoa. Ela e parametro, e nao numero em codigo, pela mesma
    # razao que todas as outras: a lei 3.8 nao abre excecao para "so um numero
    # pequeno", e o guarda de constante magica de
    # `tests/test_parametros_sao_dado.py` mede isso a cada PR.
    #
    # Janela curta demais devolve `null` na primeira semana morna; longa demais
    # promete o ritmo do mes passado para a fila de hoje. Trinta dias e o mesmo
    # tamanho que a `janela_dos_passes` ja usa, e o mantenedor muda por tela.
    "janela_do_ritmo_da_espera": (
        "dias",
        "Dias de historico que a estimativa de espera olha",
    ),
    "piso_por_nivel.iniciante": ("centavos", "Piso sugerido do nível iniciante"),
    "piso_por_nivel.intermediario": (
        "centavos",
        "Piso sugerido do nível intermediário",
    ),
    "piso_por_nivel.avancado": ("centavos", "Piso sugerido do nível avançado"),
}

# O tamanho mínimo do motivo, do `MudancaDeParametro` do contrato em papel. Não é
# número de negócio (não está na lei §6): é a régua de "escreveu por quê", e ela
# existe porque um histórico com motivo "ajuste" não responde nada seis meses
# depois.
TAMANHO_MINIMO_DO_MOTIVO = 15


class ParametroAusente(RuntimeError):
    """Falta no banco um parâmetro da lei §6 que alguém precisa ler.

    É erro, e não valor padrão, porque padrão em código seria a constante mágica
    que a lei §3.8 proíbe (critério de morte 5) e esconderia uma semeadura que
    não rodou. Conserto: `python manage.py semear_parametros --site <id>`.

    Mora AQUI, ao lado da tabela, e não no motor: desde o degrau 2.4 quem lê
    parâmetro são três módulos (`motor.py`, `relogio.py` e `tique.py`), e uma
    exceção por módulo faria quem chama precisar capturar três nomes para o
    mesmo fato. `motor.ParametroAusente` continua resolvendo, pelo import.
    """


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

    @classmethod
    def inteiro_vigente(cls, chave: str, agora, *, site_id: str) -> int:
        """O valor INTEIRO que vale em `agora`, ou a recusa fail-closed.

        Uma definição só para "leia este número da lei §6, e recuse se ele não
        estiver no banco". Três módulos precisam disso (`relogio.py` conta horas,
        `gestos.py` conta silêncios e passes), e uma cópia por módulo divergiria
        no primeiro dia em que uma delas ganhasse um cuidado a mais — inclusive
        na mensagem de conserto, que é a parte que alguém vai ler às três da
        manhã.

        Devolver um padrão embutido em vez de levantar seria a constante mágica
        que a lei §3.8 proíbe, e ainda esconderia uma semeadura que não rodou.
        """
        linha = cls.vigente_em(chave, agora, site_id=site_id)
        if linha is None:
            raise ParametroAusente(
                f"site {site_id!r}: sem valor vigente em {agora.isoformat()} para "
                f"{chave}. Rode `python manage.py semear_parametros --site {site_id}` "
                "ou confira a data de `desde` das linhas."
            )
        return int(linha.valor)
