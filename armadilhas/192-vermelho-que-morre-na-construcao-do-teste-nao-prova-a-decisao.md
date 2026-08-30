---
schema_version: 2
armadilha: 192
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: quem lê a saída do vermelho é o agente, não um portão — nenhum teste sabe distinguir "reprovou na asserção" de "reprovou montando o objeto" sem ler a intenção de quem escreveu a prova; mecanizar exigiria um coletor que classifica exceções de setup, e ele erraria justamente nos casos mistos
---

# O vermelho da prova morreu na CONSTRUÇÃO do teste, não na asserção — e não prova nada sobre a decisão

**Sintoma.** Você segue o protocolo vermelho→verde à risca: desfaz só o conserto,
mantém os testes novos, roda a suíte, e ela fica vermelha. Você cola a contagem
no PR e segue em frente. Mas o vermelho diz isto:

```
E   TypeError: Fatos.__init__() got an unexpected keyword argument 'event'
FAILED ci/tests/test_x.py::test_o_caso_novo_REPETE
FAILED ci/tests/test_x.py::test_o_caso_novo_PARA
17 failed, 19 passed
```

Nenhuma linha de asserção rodou. O que você provou é que **o teste não consegue
ser MONTADO sem o conserto** — não que o código antigo decidia diferente. Se
você tivesse escrito a decisão errada dentro do conserto, este vermelho seria
exatamente igual, e a contagem no PR seria igualmente convincente.

**Causa.** O conserto acrescentou campos ao objeto que o teste constrói (aqui,
`event`, `head_sha`, `sha_publicado`… ao `dataclass Fatos`). O construtor
estoura antes de qualquer `assert`. A mesma coisa acontece com assinatura nova
de função, `import` de símbolo que ainda não existe, e fixture que só o conserto
cria. É a irmã simétrica da `armadilhas/155` (sabotagem que "passa" porque não
aplicou) e da `132` (guarda que nasceu verde sem encenar falha): **vermelho que
não prova nada é tão perigoso quanto verde que não prova nada** — e este
enganou porque a suíte, no agregado, ficou honestamente vermelha.

**Solução: uma segunda medida, no vocabulário do código ANTIGO.** A régua é
"reprovou na ASSERÇÃO?". Se não reprovou, colha o comportamento antigo direto,
usando só os campos que ele conhecia:

```bash
python -c "
import sys; sys.path.insert(0,'ci')
import rerun_de_deploy as v
d = v.decidir(v.Fatos(run='1', status='completed', conclusion='cancelled'))
print('SEM O CONSERTO -> acao=%r codigo=%d' % (d.acao, d.codigo))
print('motivo:', d.motivo)
"
# SEM O CONSERTO -> acao='nada' codigo=1
# motivo: ... 'cancelled', não 'failure' — cancelamento tem causa própria ...
```

Essa saída crua é o que vai no PR ao lado da contagem: ela é falsificável, e é a
única que prova que a DECISÃO mudou. Duas frases, e a evidência para de ser um
número.

**A regra que fica.** Antes de aceitar um vermelho como prova, pergunte *em que
linha ele morreu*. Morreu na asserção que você escreveu ⇒ a prova é boa. Morreu
no `TypeError`, no `ImportError`, no `fixture 'x' not found` ⇒ é prova de que o
teste é NOVO, não de que o código era ERRADO — e falta a segunda medida.

**Origem.** 30/08/2026, TAR-017 (a vacina do deploy aprendendo o `cancelled` de
push, `armadilhas/188`). Os 17 vermelhos eram reais e o conserto estava certo —
mas o primeiro par de saídas que eu ia colar no PR não provava nenhuma das duas
coisas.
