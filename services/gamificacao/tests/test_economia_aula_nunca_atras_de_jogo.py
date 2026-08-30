"""INVARIANTE 3 DA ECONOMIA — aula nunca fica atrás de jogo.

Lei: `docs/decisoes/DECISAO-gamificacao.md` §3.3. A frase inteira: *"Conteúdo
educacional jamais trancado por XP, nível ou Cristal."*

**Este teste nunca se flexibiliza** (§10.5 do plano).

POR QUE ESTE É O INVARIANTE QUE PROTEGE O PRODUTO INTEIRO
----------------------------------------------------------
A família pagou por um curso. No dia em que uma aula estiver atrás de "chegue ao
nível 4", a escola terá vendido uma coisa e entregado outra, e a gamificação
terá deixado de ser andaime para virar pedágio. A hierarquia da lei
(*Realidade > Criação > Maestria > Comunidade > XP*) diz que o XP é o último de
todos; trancar aula com XP é invertê-la por completo.

COMO O TESTE GARANTE ISSO NUM PR QUE AINDA NÃO TEM TELA NEM MOTOR
-------------------------------------------------------------------
Pela forma dos dados, que é a única coisa que já existe — e é a mais duradoura:

**Esta célula não sabe o que é uma aula.** Não há campo, não há modelo e não há
chave estrangeira que nomeie conteúdo educacional. Quem não consegue nomear uma
aula não consegue trancá-la, e nenhum motor futuro consegue trancá-la sem antes
acrescentar aqui um campo que a CI recusa.

E a direção importa: a `RegraDePontuacao` VAI ler `aula.concluida.v1` um dia (a
tomada já está semeada, desligada). Ler que a aula terminou é o oposto de
decidir se ela pode começar. Por isso o teste mede NOME DE CAMPO e NOME DE
MODELO, nunca o valor de um `evento_gatilho`.
"""

from django.apps import apps

from apps.gamificacao.models import NivelDefinicao

# O conteúdo que a escola vende. Nenhuma coluna desta célula pode nomeá-lo.
CONTEUDO_EDUCACIONAL = (
    "aula",
    "curso",
    "modulo",
    "licao",
    "conteudo",
    "material",
    "apostila",
    "videoaula",
    "ementa",
    "capitulo",
    "matricula",
)

# Os verbos de PORTEIRO. Sozinhos eles são inocentes (`liberado_em` é a data em
# que a quarentena do XP acaba), e por isso a régua é combinatória: verbo de
# porteiro MAIS um substantivo de conteúdo ou de economia.
VERBOS_DE_PORTEIRO = (
    "desbloque",
    "libera",
    "destrava",
    "tranca",
    "trava",
    "bloque",
    "requer",
    "exige",
    "cadeado",
    "permite",
    "autoriza",
    "acesso",
)

MOEDAS_DO_JOGO = ("xp", "nivel", "cristal", "cristais", "ponto", "liga", "medalha")

# Modelos cujo NOME já é um portão. Um `Requisito` ou um `Desbloqueio` nesta
# célula é a coisa proibida, mesmo que os campos dele pareçam inofensivos.
NOMES_DE_PORTAO = (
    "requisito",
    "prerequisito",
    "desbloqueio",
    "liberacao",
    "tranca",
    "bloqueio",
    "cadeado",
    "permissao",
    "autorizacao",
    "matricula",
    "pedagio",
)

# A FORMA FECHADA de um degrau da escada. Um nível dá um TÍTULO, e só. É aqui
# que "no nível 4 você desbloqueia o módulo avançado" morre, porque não existe
# coluna onde escrever o que o nível libera.
FORMA_DO_NIVEL = {
    "id",
    "nivel",
    "site_id",
    "xp_necessario",
    "titulo",
    "titulo_feminino",
    "ativa",
    "versao",
}


def _modelos():
    return list(apps.get_app_config("gamificacao").get_models())


def _campos_concretos(modelo):
    return [f for f in modelo._meta.get_fields() if getattr(f, "concrete", False)]


def test_esta_celula_nao_sabe_o_que_e_uma_aula():
    """Nenhuma coluna nomeia conteúdo educacional. Nem para ler, nem para trancar.

    Guardar `aula_id` aqui seria inofensivo por uma tarde e perigoso para
    sempre: no dia seguinte alguém acrescentaria `nivel_minimo`, e a tranca
    estaria montada sem que uma linha de decisão tivesse sido escrita.
    """
    achados = []
    for modelo in _modelos():
        for campo in _campos_concretos(modelo):
            nome = campo.name.lower()
            for palavra in CONTEUDO_EDUCACIONAL:
                if palavra in nome:
                    achados.append(f"{modelo.__name__}.{campo.name} (por {palavra!r})")

    assert achados == [], (
        "INVARIANTE 3 QUEBRADO: esta célula passou a nomear conteúdo "
        "educacional.\n  " + "\n  ".join(achados) + "\n\n"
        "A lei §3.3 é literal: conteúdo educacional jamais trancado por XP, "
        "nível ou Cristal. A gamificação LÊ que a aula terminou (pelo evento); "
        "ela nunca guarda a aula, e nunca decide se alguém pode assisti-la."
    )


def test_nenhum_campo_desta_celula_e_um_portao():
    """Verbo de porteiro somado a moeda do jogo ou a conteúdo. A régua é dupla.

    Dupla de propósito: `liberado_em` (quando a quarentena do XP acaba) é
    legítimo e precisa continuar passando, enquanto `libera_aula` e
    `exige_nivel` precisam parar. Uma régua de verbo sozinho reprovaria o
    primeiro e ensinaria a próxima sessão a afrouxar o guarda.
    """
    achados = []
    for modelo in _modelos():
        for campo in _campos_concretos(modelo):
            nome = campo.name.lower()
            verbo = next((v for v in VERBOS_DE_PORTEIRO if v in nome), None)
            if not verbo:
                continue
            alvo = next(
                (s for s in CONTEUDO_EDUCACIONAL + MOEDAS_DO_JOGO if s in nome), None
            )
            if alvo:
                achados.append(f"{modelo.__name__}.{campo.name} ({verbo!r} + {alvo!r})")

    assert achados == [], (
        "INVARIANTE 3 QUEBRADO: nasceu um portão nesta célula.\n  "
        + "\n  ".join(achados)
        + "\n\nSe a intenção é premiar quem chegou longe, o prêmio é um TÍTULO "
        "ou um cosmético. Nunca uma porta fechada na frente de quem pagou pelo "
        "curso."
    )


def test_nenhum_modelo_desta_celula_tem_nome_de_portao():
    """A terceira porta: a tranca chegando como TABELA nova, e não como coluna."""
    achados = [
        modelo.__name__
        for modelo in _modelos()
        if any(palavra in modelo.__name__.lower() for palavra in NOMES_DE_PORTAO)
    ]

    assert achados == [], (
        "INVARIANTE 3 QUEBRADO: nasceu uma tabela de tranca nesta célula: "
        f"{achados}. Quem decide quem entra em quê é a `identidade` (reconhecer) "
        "e a `alunos` (matrícula), nunca a gamificação."
    )


def test_um_nivel_da_um_titulo_e_mais_nada():
    """A forma fechada do degrau, que é onde a tentação bate primeiro.

    Todo sistema de níveis do mundo tem um campo de "o que este nível
    desbloqueia". Este não tem, e a asserção de conjunto exato é o que impede
    que ele ganhe um sem alguém escrever por quê.
    """
    forma = {campo.name for campo in _campos_concretos(NivelDefinicao)}

    assert forma == FORMA_DO_NIVEL, (
        "a forma do `NivelDefinicao` mudou.\n"
        f"  sobrou:  {sorted(forma - FORMA_DO_NIVEL)}\n"
        f"  faltou:  {sorted(FORMA_DO_NIVEL - forma)}\n\n"
        "Um nível dá um TÍTULO. Se o campo novo é legítimo, atualize "
        "`FORMA_DO_NIVEL` no MESMO PR e diga no corpo dele por que ele não é "
        "uma tranca."
    )
