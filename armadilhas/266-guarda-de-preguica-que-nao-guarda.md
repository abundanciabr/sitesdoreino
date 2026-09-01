# O teste que prova "esta property não toca a rede" passa VERDE com a preguiça arrancada do código

**Sintoma.** Você escreveu uma property preguiçosa no molde do sino
(`Ator.avisos_nao_lidos`, `services/funil/apps/core/middleware.py`) e o guarda
que protege o desenho dela:

```python
def test_a_property_nao_toca_a_rede_para_quem_nao_foi_reconhecido(rede):
    ator = AtorDaRequisicao("", "site-qualquer")
    assert ator.progresso is None
    assert _chamadas_de_progresso(rede) == []
```

Aí você arranca do código exatamente a linha que o teste existe para proteger:

```python
    @property
    def progresso(self):
-       if not self:
-           return None
        if not self._progresso_resolvido:
```

e roda a suíte. **Ela fica verde.** Os dois `assert` passam, o teste não acusa
nada, e o desenho que o despacho chamou de invariante está desfeito sem que
nenhum portão pisque.

**Causa.** O guarda mede uma consequência que tem **duas** causas suficientes, e
só uma delas é a que ele quer medir. `_chamadas_de_progresso(rede) == []` fica
verdadeiro se:

1. a property desistiu antes da rede, porque ninguém foi reconhecido — o que se
   quer provar; **ou**
2. o **cliente** desistiu antes da rede, porque `GAMIFICACAO_API_URL` e
   `GAMIFICACAO_API_TOKEN` não estão no ambiente do teste.

E a convenção desta célula garante a segunda: `NOTIFICACOES`, `ALUNOS` e
`GAMIFICACAO` **não** entram na fixture `ambiente` de `tests/conftest.py`, de
propósito, para que a suíte inteira exercite o fail-open por omissão
(`armadilhas/097`). O teste, sem pedir `gamificacao_configurada`, roda num
mundo em que o cliente **nunca** ia à rede de qualquer jeito. Ele mede o
fail-open de config e se declara medindo a preguiça.

O template não salva: `{% if request.ator %}` já impede o visitante anônimo de
ler a property, então nem o teste de HTTP pega a mutação. O único lugar em que
a linha arrancada aparece é uma leitura DIRETA da property com o par LIGADO.

**Isto é `RETROSPECTIVA-FASE-D` §1 e §2 na mesma linha:** ausência de evidência
tratada como evidência de sucesso (§1), dentro do próprio teste escrito para dar
mecanismo a uma garantia (§2).

**Solução — ligue o par NO teste da preguiça, e registre a rota.** Duas
mudanças, e as duas importam:

```python
@pytest.mark.parametrize(
    "cookie",
    [
        pytest.param("", id="sem-cookie-nenhum"),
        pytest.param(COOKIE, id="cookie-que-a-identidade-nao-reconhece"),
    ],
)
def test_a_property_nao_toca_a_rede_para_quem_nao_foi_reconhecido(
    rede, gamificacao_configurada, cookie          # ← o par LIGADO
):
    rede.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))
    ator = AtorDaRequisicao(cookie, "site-qualquer")
    assert ator.progresso is None
    assert _chamadas_de_progresso(rede) == []
```

- **`gamificacao_configurada`** tira a segunda causa suficiente do caminho: com
  o par ligado, a única razão para a rede não ser tocada é a preguiça.
- **A rota registrada no `respx`** faz a mutação reprovar pelo motivo CERTO. Sem
  ela, a chamada indevida vira `AllMockedAssertionError` (`armadilhas/054`), que
  também é vermelho, mas diz "faltou um mock" em vez de "a preguiça foi
  desfeita" — e a próxima pessoa registra o mock que falta e apaga o guarda sem
  perceber.
- **Os dois cookies** cobrem os dois jeitos de não ser reconhecido: sem cookie
  nenhum, e com um cookie que a identidade não reconhece (o de idioma, o de
  analytics, um do Cloudflare). Só o segundo passa pela consulta de sessão.

**A régua que generaliza, e é o que vale levar:** um teste do tipo *"X não
aconteceu"* só vale se o mundo do teste tiver **exatamente uma** razão para X
não acontecer. Antes de confiar num `assert alguma_coisa == []`, pergunte
quantos caminhos independentes produzem essa lista vazia. Se houver dois, o
teste é decorativo — e a única forma de descobrir isso é **quebrar o código de
propósito e ver se o guarda acusa**.

**E há uma armadilha DENTRO da prova de mutação, que caiu no mesmo dia.** Ao
mutar por script, `texto.replace(velho, novo, 1)` troca a PRIMEIRA ocorrência do
arquivo, que pode não ser a sua: a linha

```python
if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
```

existe duas vezes em `apps/core/clients.py` (no cliente do sino e no da
gamificação), e a mutação "não pegou" porque tinha ido parar no cliente errado.
A conclusão apressada seria "meu guarda é fraco". Confira com `grep -n` que a
mutação caiu na linha que você queria antes de acreditar no verde.

**Origem.** 01/09/2026, TAR-096 (o quadrinho de progresso na home, PR #827,
degrau 20 do `PLANO-CELULA-GAMIFICACAO`). O despacho pedia nominalmente um
guarda para a preguiça, dizendo que "sem ele o desenho é desfeito de boa-fé pelo
próximo agente". O guarda foi escrito, passou verde, e a prova de mutação
mostrou que ele passaria verde igual com a preguiça já desfeita. As cinco
mutações do PR: quatro reprovaram de primeira, esta foi a que não reprovou.
