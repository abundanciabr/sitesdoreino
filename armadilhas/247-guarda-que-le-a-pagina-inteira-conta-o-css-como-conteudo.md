---
schema_version: 2
armadilha: 247
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: um portão que proibisse `content.decode()` cru em teste reprovaria os guardas que medem o HTML de propósito; a cura é o hábito, e ela está escrita nos dois testes que caíram
sinal:
  - `is contained here:` seguido de linhas de CSS
---

# Um guarda que lê a página inteira conta o CSS embutido como conteúdo da tela

**Sintoma:** você acrescentou uma regra de estilo e dois testes que não têm
relação nenhuma com a sua mudança ficam vermelhos, apontando para o meio da
folha de estilo:

```
assert "200" not in pagina
E  '200' is contained here:
E     .endereco-do-doc input[type=text] { flex: 1; min-width: 200px; }

assert "Apagar" not in html.split(...)[0]
E  'Apagar' is contained here:
E     /* Apagar de vez fica separado do resto por uma linha, e vermelho: [...] */
```

**Causa.** Na célula `admin`, o CSS mora EMBUTIDO no `<head>` de
`admin/base.html`, e por um bom motivo (`armadilhas/083` e `/102`: célula sob
`SCRIPT_NAME` precisa de rota própria de estático, e a tag `static` monta o
prefixo errado). Só que vários guardas desta área perguntam *"tal coisa aparece
na tela?"* usando `resposta.content.decode()` cru — e aí **a folha de estilo é
parte da resposta**. Um `min-width: 200px` vira o número 200 na página; um
comentário de CSS que explica um botão de apagar vira a palavra "Apagar".

O falso vermelho aparece para quem mexeu no ESTILO, num teste sobre outro
assunto inteiramente. Quem cai nele não tem pista nenhuma de por onde começar.

**Solução.** Pode a folha antes de medir. É uma linha, e ela mora ao lado do
guarda que precisa dela:

```python
RE_ESTILO = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)

def texto(resposta) -> str:
    return RE_ESTILO.sub("", resposta.content.decode())
```

**O que NÃO fazer: afastar o valor no CSS.** Trocar `200px` por `210px` deixa o
teste verde hoje e transforma o guarda numa armadilha para a próxima pessoa,
que terá de escolher medidas de layout que não colidam com números de negócio.
Guarda que obriga isso é guarda que vai ser desligado — e é o terceiro estrago
do `ci/tests/test_travessao.py`: **ficar chato**.

Vale para toda asserção de "não aparece na tela". As de "aparece" não sofrem: um
texto que só existe dentro do CSS não é um falso verde plausível.

**Contexto:** caiu DUAS vezes no mesmo dia, 31/08/2026, na mesma tarefa (o
editor de documentos do painel do admin), em dois arquivos de teste diferentes
— `test_caixa_no_admin.py` e `test_gestao_na_tela.py`. As duas correções estão
lá, com o comentário explicando por quê.
