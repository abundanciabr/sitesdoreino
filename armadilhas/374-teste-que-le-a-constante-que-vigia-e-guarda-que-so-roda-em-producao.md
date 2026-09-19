---
schema_version: 2
armadilha: 374
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir um `assert x in CONSTANTE` legítimo de um que lê a mesma constante que deveria vigiar, nem sabe que um `if dado is None, return` está pulando o teste inteiro em todo ambiente menos produção. As duas se pegam com UMA coisa só, e ela já é lei da casa (`armadilhas/195`): mutar o código e exigir que o vermelho caia na asserção certa. O que este arquivo acrescenta são as duas formas em que a mutação passa mesmo com o teste escrito
sinal:
  - 'assert .*\bin (mapa_do_site|robos)\.[A-Z_]{4,}'
gatilho:
  - services/admin/tests/test_mapa_do_site.py
  - services/admin/tests/test_robos_no_admin.py
licao: teste de tela que lê um artefato materializado no BUILD (`fila_embutida/`, `painel_embutido/`) pula o corpo inteiro pelo ramo do "ausente" em toda máquina que não seja produção, e teste que assere contra a própria constante do módulo passa mesmo quando ela é adulterada. Monte o artefato de mentira em `tmp_path` e escreva os valores esperados por extenso.
---

# Duas formas de teste verde que sobrevivem à mutação: ler a constante que vigia, e nunca entrar no próprio corpo

**Data:** 06/09/2026 · **Onde:** `services/admin/tests/test_mapa_do_site.py`, na seção "em obra" do mapa em árvore (PR #1225) · **Custo medido:** duas rodadas de mutação até o guarda ficar vermelho de verdade; teria virado guarda morto em produção se a mutação não fosse rito.

## Sintoma

Um guarda novo, escrito para provar que a tela não conta como "em obra" uma
tarefa já concluída:

```python
for lugar in obra["lugares"]:
    for tarefa in lugar["tarefas"]:
        assert tarefa["estado"] in mapa_do_site.EM_ABERTO
```

A mutação aplicada foi a mais direta possível, exatamente o defeito que o
guarda existe para pegar:

```python
-EM_ABERTO = ("bloqueada", "reivindicada", "em execução", "na fila")
+EM_ABERTO = ("bloqueada", "reivindicada", "em execução", "na fila", "concluída")
```

E o teste ficou **verde**:

```
=== MUTACAO: tarefa terminada contada como em obra ===
1 passed, 24 deselected in 3.00s
```

## Causa

São **duas** causas empilhadas, e as duas produzem o mesmo verde. Descobrir a
primeira e parar por aí deixa a segunda de pé.

**1. O teste lia a mesma constante que deveria vigiar.** `EM_ABERTO` é o dado
sob julgamento; assere-lo contra si mesmo é uma tautologia. Adulterada a
constante, a asserção continua verdadeira por construção. Isto é primo direto
do `armadilhas/195`, mas na forma em que a mutação *não* denuncia nada.

**2. O corpo do teste nunca rodava.** A seção lê `fila_embutida/estados.json`,
que **o deploy materializa dentro da imagem** — em nenhum checkout, e portanto
em nenhuma rodada do CI, essa pasta existe. O teste tinha a saída honesta para
esse caso:

```python
obra = resposta.context["obra"]
if obra is None:
    assert "não veio nesta versão do site" in html
    return          # <- o CI SEMPRE sai por aqui
```

O que parecia um guarda com dois ramos era um guarda com um ramo só, e o ramo
que rodava era o do artefato ausente. O caminho real — o que produção executa —
não era medido em lugar nenhum. Falso-verde do padrão 1 da
`RETROSPECTIVA-FASE-D`, na forma mais educada que existe: um teste que passa
porque desistiu.

A célula `admin` serve TRÊS coisas assim (`painel_embutido/`, `fila_embutida/`,
`documentos/`), então a forma se repete: a tela lê algo que só o build produz.

## Solução

**Monte o artefato de mentira, e escreva o esperado por extenso.**

```python
def _fila_de_mentira(tmp_path, monkeypatch):
    pasta = tmp_path / "fila_embutida"
    pasta.mkdir(parents=True)
    (pasta / "estados.json").write_text(json.dumps({
        "TAR-001": {"estado": "concluída", "titulo": "Coisa que já ficou pronta", "toca": ["forum"]},
        "TAR-002": {"estado": "na fila",   "titulo": "Coisa que ainda vai ser feita", "toca": ["forum"]},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
```

Duas exigências, e nenhuma delas é opcional:

- **O dado de mentira precisa conter o caso que deve ser recusado.** Sem a
  tarefa `"concluída"` ali dentro, o guarda passa mesmo com a regra adulterada:
  não há o que recusar.
- **Os valores esperados se escrevem no teste, nunca se importam do módulo.**

```python
assert obra["total"] == 2, "a tarefa já concluída entrou na conta do que falta"
assert "Coisa que já ficou pronta" not in html
assert tarefa["estado"] not in ("concluída", "cancelada")
```

Com as duas, a mesma mutação cai onde tem de cair:

```
=== MUTACAO: concluida contada como em obra ===
tests\test_mapa_do_site.py:451: AssertionError
FAILED tests/test_mapa_do_site.py::test_o_que_esta_em_obra_vem_da_fila_e_nao_de_uma_lista_daqui
```

E o ramo do artefato ausente vira o teste dele mesmo, separado, medindo a outra
promessa (a tela DIZ que não leu a fila, nunca "nada em obra"):

```python
def test_fila_ausente_nao_vira_nada_em_obra(monkeypatch):
    monkeypatch.setattr(mapa_do_site, "diretorio_da_fila", lambda: None)
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert "A fila de trabalho não veio nesta versão do site." in html
```

## A régua que pega as duas antes do commit

Antes de dar um guarda por escrito, duas perguntas de dois segundos:

1. **"O valor que eu asserto veio de onde?"** Se veio de um `import` do módulo
   sob teste, ele não é expectativa: é o próprio réu depondo.
2. **"Em que ramo o CI entra?"** Rode o teste sozinho e faça o ramo feliz
   estourar de propósito (`assert False` dentro dele). Se continuar verde, o CI
   nunca passou por ali.
