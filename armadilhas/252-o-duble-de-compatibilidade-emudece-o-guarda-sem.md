---
schema_version: 2
armadilha: 252
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: `um portao que decidisse se uma assercao SIGNIFICA alguma coisa teria de entender a intencao do teste, e reprovaria guarda honesto. A distancia entre "o parametro chega ao codigo" e "o parametro importa" nao e mecanica. A cura e de METODO e mora na RETROSPECTIVA-FASE-D §1: todo guarda tem de ser visto vermelho, e num guarda parametrizado o que se sabota e o VALOR, nao o codigo.`
sinal:
  - `alunos_diz\(.*status`
  - `Compat[íi]vel com o que os testes j[áa] escreviam`
---

# O dublê "de compatibilidade" emudece o guarda sem deixar vermelho, e o teste segue verde parametrizando lixo

**Sintoma.** Um arquivo `test_inv_*.py` está **verde** e a regra que ele promete
guardar **não está guardada**. Nada falha, nada avisa, e a lei do projeto, o
livro do painel e os documentos continuam citando aquele arquivo como *"a prova
viva"* da decisão. Só se descobre por acaso, quando alguém vai mudar a regra e
percebe que o guarda não reage.

O caso concreto, medido em 31/08/2026 (`services/sugestoes`):

```python
# tests/test_inv_matricula_reembolsada_entra.py
SITUACOES = ["ativa", "reembolsada", "cancelada", "expirada", "qualquer-nova"]

@pytest.mark.parametrize("situacao", SITUACOES)
def test_toda_situacao_de_matricula_entra(rede, db, matricula, situacao):
    rede.alunos_diz(PESSOA, [{**matricula, "status": situacao}])
    ...
```

Trocando a lista inteira por um valor impossível, o arquivo **continua verde**:

```bash
SITUACOES = ["ISTO-NAO-E-UM-STATUS-DE-VERDADE"]   # → 2 passed
```

**Causa.** O dublê da dependência virou um **atalho de compatibilidade** quando o
contrato dela mudou de forma, e o atalho **descarta exatamente a variável que o
teste parametriza**:

```python
def alunos_diz(self, email: str, matriculas: list[dict]):
    """Compatível com o que os testes já escreviam: lista não-vazia = aluno."""
    return self.alunos_situacao(email, "aluno" if matriculas else "cadastrado")
```

A célula `alunos` migrou de *"tem matrícula?"* (`GET /alunos/{email}/matriculas`)
para *"em que situação está?"* (`GET /alunos/{email}/situacao`) em 28/08/2026. O
dublê foi mantido para não reescrever dezenas de testes, e a decisão foi
razoável: quase todos só queriam dizer *"esta pessoa é aluna"*. Mas os testes
que passavam um **status específico** perderam o único dado que os tornava
testes, e passaram a afirmar *"um aluno entra"* — verdadeiro, e sem relação com
o que o nome do arquivo promete.

**Por que nunca aparece.** Guarda vazio é **verde**, e verde parece saúde. O
inverso do falso-verde da `armadilhas/040` (portão que passa por não conseguir
medir): aqui o teste **mede perfeitamente**, só que outra coisa. Nenhuma
contagem de cobertura acusa — as linhas são executadas. A catraca de testes não
acusa — o arquivo existe e tem `def test_`. O guarda-dos-guardas não acusa — ele
verifica que o arquivo tem teste de verdade e não tem `skip`, não que a asserção
significa alguma coisa.

No caso medido, a regra ficou **três dias** desprotegida enquanto quatro
documentos afirmavam o contrário. O que realmente segurava a regra era
`STATUS_QUE_VALEM`, em outra célula.

**Solução.**

1. **Antes de confiar num guarda que você não escreveu hoje, sabote o VALOR que
   ele parametriza** — não o código sob teste. Troque o parâmetro por um valor
   impossível e exija vermelho:

   ```bash
   # se isto continua verde, o parâmetro não é um parâmetro
   SITUACOES = ["ISTO-NAO-E-UM-STATUS-DE-VERDADE"]
   ```

2. **Guarda de regra específica não usa dublê genérico.** Escreva um dublê que
   fale a língua de hoje e nomeie o caso (`alunos_diz_reembolsado()`,
   `alunos_diz_pausado()`), em vez de espremer o caso dentro do atalho antigo.

3. **Ao migrar o contrato de uma dependência, liste os testes que passam um
   VALOR para o dublê** (e não só os que o chamam). Esses são os que emudecem.
   Os outros continuam corretos.

4. Se o guarda ficou obsoleto de verdade, **apague e substitua** com a etiqueta
   `remove-teste`, em vez de remendar — um guarda remendado carrega a premissa
   antiga no nome e nas docstrings, e a próxima pessoa acredita nelas.

**A regra em uma frase:** quando o contrato de uma dependência muda de forma, os
guardas escritos contra a forma velha **não quebram, emudecem** — e emudecer não
tem cor no CI.

**Origem.** 31/08/2026, ao reverter a decisão de 24/08 sobre reembolso
(`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`). O mantenedor achou o texto
errado publicado no site; ao ir desfazer a trava que "protegia" a regra antiga,
a trava não reagiu. Registro: `painel/registros/20260831-087-a-tela-que-explica-o-reembolso-e-um-guarda-vazio.js`.
Substituto: `services/sugestoes/tests/test_inv_reembolso_nao_entra.py` (INV-SUG09).
