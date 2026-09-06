"""A aba "Os robôs" (29/08/2026) — o quadro da fila, calculado, nunca digitado.

O que estes guardas protegem:

1. **A tela serve o que o build materializou** (`fila_embutida/estados.json`)
   — ela não recalcula estado nenhum: recalcular seria a segunda definição de
   "em que pé está", e as duas divergiriam.
2. **Fila ausente se DECLARA** (500 + explicação), nunca vira quadro vazio —
   "não há trabalho" seria mentira, a mesma lei do painel ausente.
3. **O CSP continua estrito**: a ilha de script entra por hash (nunca
   `'unsafe-inline'`), e `connect-src` abre SÓ para `api.github.com` — sem
   isso o bloco "ao vivo" morreria em silêncio no navegador.
4. **Nada daqui sai para a internet no servidor**: `respx.mock` estoura em
   qualquer chamada não registrada — quem pergunta ao GitHub é o NAVEGADOR
   do dono, nunca esta célula.
"""

import json
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import robos

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def fila_de_mentira(tmp_path, monkeypatch, com_esperas=True, com_eventos=True):
    """Uma fila embutida como o deploy a deixaria — estados JÁ materializados."""
    pasta = tmp_path / "fila_embutida"
    (pasta / "esperas").mkdir(parents=True)
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-001": {
                    "estado": "concluída",
                    "motivo": "https://github.com/x/y/pull/516",
                    "quem": "sessao-semeadura",
                    "titulo": "Semear a fila",
                    "toca": ["fila"],
                },
                "TAR-002": {
                    "estado": "reivindicada",
                    "motivo": "",
                    "quem": "sessao-aba",
                    "titulo": "Construir a aba",
                    "toca": ["admin"],
                },
                # As DUAS paradas, que é o que a tela precisa saber separar: uma
                # só o dono destrava, a outra se destrava sozinha quando a de
                # cima terminar. Antes de 06/09/2026 as duas eram o mesmo cartão
                # âmbar no mesmo bloco (em produção, 27 deles, 6 do dono).
                "TAR-003": {
                    "estado": "bloqueada",
                    "espera": "mantenedor",
                    "motivo": "aguardando despacho do mantenedor",
                    "quem": None,
                    "titulo": "Backup antes de migração",
                    "toca": ["infra"],
                },
                "TAR-004": {
                    "estado": "bloqueada",
                    "espera": "fila",
                    "motivo": "esperando TAR-002",
                    "quem": None,
                    "titulo": "A segunda metade da aba",
                    "toca": ["admin"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pasta / "regua.json").write_text(
        json.dumps(
            {
                "medido_em": "2026-08-29",
                "esperas": {
                    "checks": {
                        "rotulo": "os testes de um PR",
                        "p50_s": 90,
                        "p90_s": 180,
                        "amostra": 62,
                    },
                    "pouso": {
                        "rotulo": "o pouso pela pista",
                        "p50_s": 420,
                        "p90_s": 900,
                        "amostra": 5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    if com_esperas:
        (pasta / "esperas" / "resumo-20260829-120000.json").write_text(
            json.dumps(
                {
                    "gerado_em": "2026-08-29T12:00:00+00:00",
                    "total": 10,
                    "verdes": 9,
                    "por_classe": {},
                    "estouros": [
                        {
                            "quando_utc": "2026-08-29T03:00:00+00:00",
                            "alvo": "sonda:docker",
                            "dizendo": "o Docker acordar",
                            "teto_s": 300,
                            "decorrido_s": 300,
                            "desfecho": "estourou",
                            "detalhe": "morreu no teto",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    if com_eventos:
        # `deploy-celula.yml` copia `fila/.` inteira, então `eventos/` chega à
        # imagem junto com os estados. É daqui que saem as datas e o ritmo.
        (pasta / "eventos").mkdir()
        for nome, tarefa, evento in (
            ("20260901-100000-TAR-001-reivindicada", "TAR-001", "reivindicada"),
            ("20260901-110000-TAR-004-concluida", "TAR-004", "concluida"),
            ("20260902-100000-TAR-001-concluida", "TAR-001", "concluida"),
            ("20260902-110000-TAR-005-concluida", "TAR-005", "concluida"),
        ):
            (pasta / "eventos" / f"{nome}.json").write_text(
                json.dumps(
                    {
                        "arquivo": nome,
                        "tarefa": tarefa,
                        "evento": evento,
                        "quando": f"{nome[:4]}-{nome[4:6]}-{nome[6:8]}T12:00:00+00:00",
                        "quem": "sessao-de-mentira",
                    }
                ),
                encoding="utf-8",
            )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta


def texto(resposta) -> str:
    return resposta.content.decode()


# A folha de estilo desta aba mora DENTRO do corpo da resposta, então toda
# asserção de "isto NÃO está na tela" precisa podá-la antes de medir — senão um
# nome de classe ou um comentário de CSS vira falso vermelho num teste que não
# tem nada a ver com estilo (`armadilhas/247`).
RE_ESTILO = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)


def texto_sem_estilo(resposta) -> str:
    return RE_ESTILO.sub("", resposta.content.decode())


@respx.mock
def test_o_quadro_mostra_o_que_o_build_materializou(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "TAR-002" in pagina and "Construir a aba" in pagina
    assert "sessao-aba" in pagina
    # A bloqueada carrega o MOTIVO — é a coluna que pede gente, não máquina.
    assert "aguardando despacho do mantenedor" in pagina
    # A concluída aparece com a prova por perto.
    assert "pull/516" in pagina


@respx.mock
def test_o_de_agora_vem_antes_do_retrato(tmp_path, monkeypatch):
    """A ordem da página é POR URGÊNCIA, e isso é o conserto de 03/09/2026.

    Até esta data a tela era um kanban de colunas lado a lado, e a coluna das
    concluídas (76 cartões em produção) empurrava o bloco ao vivo — a única
    coisa realmente de agora — para dezenas de rolares abaixo da dobra. O
    mantenedor abriu a tela e disse que não conseguia acompanhá-la.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    ao_vivo = pagina.find("Agora, neste minuto")
    e_dele = pagina.find("Esperando uma decisão sua")
    corrente = pagina.find("Esperando outra tarefa terminar")
    ja_terminaram = pagina.find("Já terminaram")

    assert ao_vivo != -1 and e_dele != -1 and corrente != -1 and ja_terminaram != -1
    assert ao_vivo < e_dele, "o que é de agora ficou abaixo do retrato do deploy"
    # O que só ele destrava vem antes do que se destrava sozinho: em 06/09/2026
    # os dois eram o MESMO bloco, e ele teria de abrir 27 cartões para achar 6.
    assert e_dele < corrente, "a corrente da fila passou na frente do que é dele"
    assert corrente < ja_terminaram, "a história antiga passou na frente do resto"


@respx.mock
def test_a_historia_nasce_fechada_e_o_que_pede_gente_nasce_aberto(
    tmp_path, monkeypatch
):
    """Concluídas e canceladas são história: elas entram num `details` FECHADO.

    Em produção são 76 cartões que não pedem nada de ninguém. Abertos, eles
    são a página inteira; fechados, são uma linha com um número do lado.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    # A história fica ATRÁS de um clique: o rótulo dela é o próprio `summary`.
    assert "<summary>Já terminaram" in pagina, "a história voltou a nascer aberta"
    assert "<details open" not in pagina
    # E o que só ELE destrava NUNCA fica atrás de um clique.
    assert "<h2>Esperando uma decisão sua" in pagina
    # A corrente da fila, ao contrário, nasce fechada: ninguém precisa dela hoje.
    assert "<summary>Esperando outra tarefa terminar" in pagina


@respx.mock
def test_a_tela_fala_portugues_e_nao_o_vocabulario_da_fila(tmp_path, monkeypatch):
    """Os estados da fila são contrato; o mantenedor é leigo.

    "reivindicada", "em execução" e "toca" são o vocabulário de `ci/fila.py` e
    continuam intactos NO DADO. O que chega à tela é a tradução — a mesma lei
    do painel do dono, que não tem sigla.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Um robô pegou, e está com ela agora" in pagina
    # `infra` é nome de pasta; o que ele lê é o lugar.
    assert "onde: a fábrica (ferramenta dos robôs)" in pagina
    assert "reivindicada" not in pagina
    assert "toca:" not in pagina
    assert "mexe em:" not in pagina


@respx.mock
def test_o_endereco_da_prova_vira_link_clicavel(tmp_path, monkeypatch):
    """A prova de uma concluída é um endereço, e endereço em texto cru obriga o
    mantenedor a selecionar e copiar à mão."""
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert 'href="https://github.com/x/y/pull/516"' in pagina


@respx.mock
def test_as_esperas_mostram_o_que_estourou_e_a_regua(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "o Docker acordar" in pagina
    assert "os testes de um PR" in pagina
    # Régua honesta: medida com poucos casos se DECLARA, em português.
    assert "poucas vezes ainda" in pagina
    # E o tempo sai em tempo, não em número com um "s" colado.
    assert "15 minutos" in pagina and "900s" not in pagina


@respx.mock
def test_sem_resumo_de_esperas_a_pagina_diz_isso(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch, com_esperas=False)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "ainda não foi exportado" in pagina


@respx.mock
def test_fila_ausente_se_declara_nunca_finge_vazio(tmp_path, monkeypatch):
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "nao-existe",))
    resposta = _dentro().get(reverse("caixa_robos"))

    assert resposta.status_code == 500
    assert "não veio nesta imagem" in texto(resposta)


@respx.mock
def test_o_csp_tem_hash_da_ilha_e_connect_src_do_github(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    resposta = _dentro().get(reverse("caixa_robos"))

    csp = resposta["Content-Security-Policy"]
    assert "connect-src 'self' https://api.github.com" in csp
    assert "'sha256-" in csp
    # A linha de script NUNCA afrouxa — mesma lei do painel.
    assert "script-src 'self' 'sha256-" in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]


# ─────────────────────────────────────────────────────────────────────────────
# A PASSADA DE COMPREENSÃO (03/09/2026)
#
# Depois de a tela ficar legível, o mantenedor disse: "vamos continuar aqui no
# claude code mesmo, como está agora, eu só preciso de uma página melhor para
# ENTENDER isso". Não era uma tela para agir — era uma tela para compreender.
# Os guardas abaixo prendem as quatro coisas que mudaram por causa dessa frase.
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_a_pagina_diz_o_que_ela_e_e_que_nao_ha_nada_a_fazer(tmp_path, monkeypatch):
    """A tela nunca dizia o que era: caía direto nos números.

    Quem não sabe o que é uma "fila de trabalho" começava a leitura no escuro.

    A segunda frase tirava peso das costas dele — "você não precisa fazer nada
    aqui" — e em 06/09/2026 ela virou mentira: seis tarefas em produção estavam
    paradas esperando uma autorização ou uma prova que só ele podia dar. A frase
    passou a depender do dado. O que continua verdade em todo caso é o resto
    dela: a tela não age, e o pedido continua sendo feito na conversa.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Cada cartão desta página é um pedaço de trabalho no seu site" in pagina
    # A fila de mentira tem UMA parada que só ele destrava (TAR-003).
    assert "1 dela não anda sem você" in pagina
    assert "fale comigo na conversa" in pagina

    # A tela é de OLHAR: nenhum formulário, nenhum botão que escreva. Ele
    # decidiu isso com todas as letras em 03/09/2026 — "vamos continuar aqui no
    # claude code mesmo" —, e a frase acima só continua verdadeira enquanto
    # nada aqui agir.
    #
    # A medição é do CORPO DESTA PÁGINA, e não da resposta inteira: a moldura
    # do Admin (a faixa, o menu, o rodapé) é compartilhada por 22 telas, e um
    # formulário que nascesse lá — uma busca no menu, um botão de sair —
    # deixaria ESTE guarda vermelho num PR que não tem nada a ver com a aba dos
    # robôs. Guarda que fica chato é guarda que alguém desliga (`armadilhas/247`).
    corpo = pagina.split('class="envolucro largo"')[-1].split("rodape-do-admin")[0]
    assert "<form" not in corpo


def test_o_lugar_tecnico_vira_um_lugar_que_ele_reconhece():
    assert robos.onde_isso_mexe(["funil"]) == ["as páginas que vendem"]
    assert robos.onde_isso_mexe(["gamificacao"]) == ["os pontos e as medalhas"]
    # As sete pastas de oficina viram UM lugar só, sem repetir: distinguir `ci`
    # de `.github` na tela dele seria precisão que não muda decisão nenhuma.
    assert robos.onde_isso_mexe(["ci", ".github", "infra"]) == [
        "a fábrica (ferramenta dos robôs)"
    ]
    # `services/funil` e `funil` são o mesmo lugar para quem lê.
    assert robos.onde_isso_mexe(["services/funil", "funil"]) == [
        "as páginas que vendem"
    ]


def test_lugar_desconhecido_aparece_cru_em_vez_de_sumir():
    """FALHA ABERTO, e este é o guarda que impede a tradução de virar mentira.

    Célula nova nasce a cada duas semanas aqui. Se o dicionário ESCONDESSE o que
    não conhece, o dono veria uma tarefa sem lugar nenhum e nunca perguntaria —
    a tela mentiria por omissão. Nome estranho ele pergunta; ausência, não.
    """
    assert robos.onde_isso_mexe(["celula-que-ainda-nao-existe"]) == [
        "celula-que-ainda-nao-existe"
    ]
    assert robos.onde_isso_mexe(None) == []


# ─────────────────────────────────────────────────────────────────────────────
# AS DUAS PARADAS — o conserto de 06/09/2026
#
# Ele perguntou como se atualizava esta lista, e a resposta foi que ela já se
# atualiza sozinha. O problema real era outro: as 27 paradas do dia estavam
# todas no mesmo bloco âmbar de urgência, e SEIS delas esperavam uma decisão
# dele. Achar essas seis custava abrir e ler 27 cartões.
#
# A cura não foi escrever melhor: foi o evento `bloqueada` passar a declarar
# quem destrava (`ci/fila.py`, QUEM_DESTRAVA). Estes guardam o que a tela faz
# com essa declaração.
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_as_duas_paradas_nao_moram_no_mesmo_bloco(tmp_path, monkeypatch):
    """A que só ele destrava e a que espera outra tarefa são coisas diferentes."""
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    dele = pagina.find("Esperando uma decisão sua")
    corrente = pagina.find("Esperando outra tarefa terminar")
    assert dele != -1 and corrente != -1 and dele < corrente

    # E cada cartão está do lado certo: o do dono no bloco dele, a corrente no
    # outro. Medido pelo título, que é o que ele lê.
    assert pagina.find("Backup antes de migração") < corrente
    assert pagina.find("A segunda metade da aba") > corrente


@respx.mock
def test_parada_sem_dizer_quem_destrava_aparece_no_bloco_dele(tmp_path, monkeypatch):
    """Falha para o lado de MOSTRAR, nunca de esconder.

    Um `espera` que a tela não reconhece — dado de um build antigo, campo que um
    dia mude de nome — vai para o bloco do mantenedor. Um cartão a mais ali
    custa uma leitura; um cartão que some da única tela que responde "em que pé
    está" custa uma tarefa esquecida, e ninguém ficaria sabendo.
    """
    pasta = fila_de_mentira(tmp_path, monkeypatch)
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-009": {
                    "estado": "bloqueada",
                    "motivo": "de um build anterior a 06/09/2026",
                    "quem": None,
                    "titulo": "A parada sem dono declarado",
                    "toca": ["admin"],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "A parada sem dono declarado" in pagina, "a tarefa sumiu da tela"
    assert pagina.find("Esperando uma decisão sua") < pagina.find(
        "A parada sem dono declarado"
    )


@respx.mock
def test_sem_nada_esperando_ele_a_pagina_diz_isso(tmp_path, monkeypatch):
    """O aviso some inteiro quando não há nada dele.

    Aviso que fica na tela com o número zero ensina o olho a ignorar o aviso, e
    aí ele deixa de ver no dia em que houver alguma coisa.
    """
    pasta = fila_de_mentira(tmp_path, monkeypatch)
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-004": {
                    "estado": "bloqueada",
                    "espera": "fila",
                    "motivo": "esperando TAR-002",
                    "quem": None,
                    "titulo": "A segunda metade da aba",
                    "toca": ["admin"],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Nada aqui depende de você agora" in pagina
    assert "não anda sem você" not in pagina
    assert "Esperando uma decisão sua" not in pagina


def test_o_grupo_certo_para_cada_parada():
    """A regra de casamento, sem passar por HTTP: as duas paradas e o desconhecido."""
    dele = {"estado": "bloqueada", "espera": "mantenedor"}
    corrente = {"estado": "bloqueada", "espera": "fila"}
    sem_dono = {"estado": "bloqueada"}
    grupo_dele = {"estado": "bloqueada", "espera": "mantenedor"}
    grupo_corrente = {"estado": "bloqueada", "espera": "fila"}
    grupo_terminadas = {"estado": "concluída"}

    assert robos.e_deste_grupo(dele, grupo_dele)
    assert not robos.e_deste_grupo(dele, grupo_corrente)
    assert robos.e_deste_grupo(corrente, grupo_corrente)
    assert not robos.e_deste_grupo(corrente, grupo_dele)
    # O desconhecido cai com ele, e em lugar nenhum além disso.
    assert robos.e_deste_grupo(sem_dono, grupo_dele)
    assert not robos.e_deste_grupo(sem_dono, grupo_corrente)
    # Estado diferente nunca casa, com ou sem `espera`.
    assert not robos.e_deste_grupo(dele, grupo_terminadas)
    assert robos.e_deste_grupo({"estado": "concluída"}, grupo_terminadas)


def test_o_tempo_sai_em_tempo_e_nao_em_numero_com_s_colado():
    assert robos.em_portugues(40) == "40 segundos"
    assert robos.em_portugues(90) == "1 minuto e meio"
    assert robos.em_portugues(180) == "3 minutos"
    assert robos.em_portugues(900) == "15 minutos"
    assert robos.em_portugues(7200) == "2 horas"
    # Medida ausente se DECLARA — nunca vira "0 segundos", que seria um fato
    # inventado com cara de medição.
    assert robos.em_portugues(None) == "não medido"


def test_o_ritmo_e_contado_dos_eventos_da_fila(tmp_path, monkeypatch):
    """ "Isto está andando?" é a pergunta que 101 cartões não respondem.

    A resposta sai dos eventos que a fila JÁ escreveu — nada é recalculado nem
    inventado. A média é sobre os dias em que houve conclusão, nunca sobre o
    calendário inteiro, que fabricaria zeros para dias que ninguém mediu.
    """
    pasta = fila_de_mentira(tmp_path, monkeypatch)
    conta = robos.andamento(pasta)

    assert conta["terminadas"] == 3
    assert conta["quantos_dias"] == 2
    assert conta["por_dia"] == "1,5"  # vírgula: a tela é em português
    assert conta["ultima_mexida"]["TAR-001"] == "2026-09-02"


@respx.mock
def test_sem_a_pasta_de_eventos_a_tela_fica_mais_pobre_e_nao_quebra(
    tmp_path, monkeypatch
):
    """Data ausente é uma tela mais pobre; página 500 é uma tela que não existe."""
    pasta = fila_de_mentira(tmp_path, monkeypatch, com_eventos=False)
    conta = robos.andamento(pasta)

    assert conta["ultima_mexida"] == {} and conta["terminadas"] == 0
    assert _dentro().get(reverse("caixa_robos")).status_code == 200
