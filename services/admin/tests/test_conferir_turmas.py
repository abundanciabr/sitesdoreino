"""O cruzamento da lista de turmas com a escola — as quatro caixas.

A régua destes testes: **as quatro caixas somam a fila e somam a lista**.
Ninguém aparece duas vezes, ninguém some. Um número sumido de uma conferência é
o pior desfecho possível aqui — o mantenedor liberaria uma turma achando que
liberou todo mundo.
"""

from apps.core.turmas import conferir


def na_fila(id_, whatsapp, nome="Fulano"):
    return {
        "id": id_,
        "whatsapp": whatsapp,
        "nome_completo": nome,
        "email": f"{id_}@x.com",
    }


class TestOCasoNormal:
    def test_quem_esta_na_lista_e_na_fila_fica_pronto_para_liberar(self):
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[na_fila("1", "+55 (11) 99999-8888", "Maria")],
            alunos=[],
        )
        assert [p["pessoa"]["nome_completo"] for p in r["prontos"]] == ["Maria"]
        assert r["sozinhos"] == []
        assert r["sem_par"] == []

    def test_quem_esta_na_fila_e_nao_na_lista_fica_marcado(self):
        r = conferir(
            numeros=[], fila=[na_fila("1", "11 99999-8888", "João")], alunos=[]
        )
        assert r["prontos"] == []
        assert [s["pessoa"]["nome_completo"] for s in r["sozinhos"]] == ["João"]
        assert r["sozinhos"][0]["talvez_o_numero"] is None

    def test_numero_da_lista_sem_ninguem_no_site_fica_marcado(self):
        r = conferir(numeros=["11 99999-8888"], fila=[], alunos=[])
        assert r["sem_par"] == ["11 99999-8888"]
        assert r["prontos"] == []


class TestQuemJaEAluno:
    """A caixa que faz a mesma lista poder ser colada de novo amanhã."""

    def test_nao_vira_nao_achei_no_site(self):
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[],
            alunos=[na_fila("9", "11 99999-8888", "Já Liberada")],
        )
        assert r["sem_par"] == [], "ele sairia procurando por quem já está dentro"
        assert [j["pessoa"]["nome_completo"] for j in r["ja_dentro"]] == ["Já Liberada"]

    def test_e_nao_entra_na_lista_de_liberar(self):
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[],
            alunos=[na_fila("9", "11 99999-8888")],
        )
        assert r["prontos"] == [], "liberar quem já é aluno é um 409 disfarçado"


class TestASugestao:
    """Nunca libera sozinha, e nunca esconde ninguém."""

    def test_mesmo_final_ddd_diferente_vira_sugestao_e_nao_liberacao(self):
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[na_fila("1", "21 99999-8888", "Talvez Ela")],
            alunos=[],
        )
        assert r["prontos"] == [], "isto liberaria a pessoa errada"
        assert r["sozinhos"][0]["talvez_o_numero"] == "11 99999-8888"
        assert r["sem_par"] == [], "o número já aparece ao lado dela"

    def test_sufixo_que_serve_para_duas_pessoas_nao_sugere_nada(self):
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[na_fila("1", "21 99999-8888"), na_fila("2", "31 99999-8888")],
            alunos=[],
        )
        assert all(s["talvez_o_numero"] is None for s in r["sozinhos"])
        assert r["sem_par"] == ["11 99999-8888"]

    def test_o_exato_ganha_do_palpite(self):
        # Dois números; um casa exato com a Ana, o outro só "parece" a Ana.
        r = conferir(
            numeros=["21 99999-8888", "11 99999-8888"],
            fila=[na_fila("1", "21 99999-8888", "Ana")],
            alunos=[],
        )
        assert [p["pessoa"]["nome_completo"] for p in r["prontos"]] == ["Ana"]
        assert r["sozinhos"] == []
        assert r["sem_par"] == ["11 99999-8888"], "o outro número não pode sumir"

    def test_dois_numeros_sugerindo_a_mesma_pessoa_nao_somem(self):
        r = conferir(
            numeros=["11 99999-8888", "31 99999-8888"],
            fila=[na_fila("1", "21 99999-8888", "Uma So")],
            alunos=[],
        )
        assert len(r["sozinhos"]) == 1
        assert r["sozinhos"][0]["talvez_o_numero"] == "11 99999-8888"
        assert r["sem_par"] == ["31 99999-8888"], "o segundo volta a ser 'não achei'"


class TestNinguemSomeENinguemDuplica:
    """A régua da tela: os cabeçalhos têm de fechar a conta."""

    def test_as_caixas_somam_a_fila_e_somam_a_lista(self):
        numeros = ["11 99999-1111", "11 99999-2222", "11 99999-3333", "11 99999-4444"]
        fila = [na_fila("1", "11 99999-1111"), na_fila("2", "11 98888-7777")]
        alunos = [na_fila("9", "11 99999-2222")]
        r = conferir(numeros, fila, alunos)

        pessoas = [p["pessoa"]["id"] for p in r["prontos"]]
        pessoas += [s["pessoa"]["id"] for s in r["sozinhos"]]
        assert sorted(pessoas) == ["1", "2"], "a fila inteira, uma vez cada"

        da_lista = [p["numero"] for p in r["prontos"]]
        da_lista += [j["numero"] for j in r["ja_dentro"]]
        da_lista += r["sem_par"]
        da_lista += [
            s["talvez_o_numero"] for s in r["sozinhos"] if s["talvez_o_numero"]
        ]
        assert sorted(da_lista) == sorted(numeros), "a lista inteira, uma vez cada"


class TestOsCasosQueQuebramCruzamento:
    def test_ficha_sem_whatsapp_nao_casa_com_ficha_sem_whatsapp(self):
        r = conferir(numeros=[""], fila=[na_fila("1", "")], alunos=[])
        assert r["prontos"] == [], "dois campos vazios não são a mesma pessoa"
        assert len(r["sozinhos"]) == 1

    def test_duas_fichas_da_mesma_pessoa_a_mais_antiga_ganha(self):
        # Quem saiu e voltou tem duas linhas (DECISAO-a-ficha-nao-se-apaga), e a
        # fila chega ordenada por data.
        r = conferir(
            numeros=["11 99999-8888"],
            fila=[na_fila("velha", "11 99999-8888"), na_fila("nova", "11 99999-8888")],
            alunos=[],
        )
        assert [p["pessoa"]["id"] for p in r["prontos"]] == ["velha"]

    def test_lista_ausente_nao_vira_escola_vazia(self):
        # `None` é "não consegui perguntar". Quem chama trata ANTES; aqui o que
        # se fixa é que não explode e não inventa gente.
        r = conferir(numeros=["11 99999-8888"], fila=None, alunos=None)
        assert r["prontos"] == []
        assert r["total_na_fila"] == 0

    def test_lista_vazia_nao_marca_ninguem_por_engano(self):
        r = conferir(numeros=[], fila=[], alunos=[])
        assert r == {
            "prontos": [],
            "sozinhos": [],
            "ja_dentro": [],
            "sem_par": [],
            "total_colado": 0,
            "total_na_fila": 0,
        }
