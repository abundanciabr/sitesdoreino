---
schema_version: 2
armadilha: 289
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/admin/tests/test_perpetuo.py
sinal:
  - `cita(r)? (um )?endere[çc]o de outra c[ée]lula`
  - `link (morto|quebrado) (no|na) (painel|tela|admin)`
---

# Tela que CITA endereço de outra célula apodrece sem alarme: a muralha do mapa só cobre quem CRIA rota

**Sintoma.** Você constrói uma tela do painel que aponta para páginas de outras
células (um mapa, uma capa, um índice, um passo a passo). No dia da entrega tudo
abre. Semanas depois, o mantenedor clica num daqueles links e cai num **404** —
e conclui que o site quebrou. Nenhum teste ficou vermelho, nenhuma muralha
reprovou, nenhum PR foi devolvido. O endereço mudou numa célula que você nunca
tocou.

**Causa.** A `ci/mapa_do_site.py` é forte, e é fácil confundir o alcance dela.
Ela confere **nos dois sentidos** o par *(rota no `urls.py`, entrada no
`painel/mapa-do-site.json`)*: rota sem entrada reprova, entrada sem rota
reprova. Quem **renomeia** uma rota é obrigado, pela muralha, a corrigir o mapa
no mesmo PR.

O que ela **não** vê é a terceira ponta: **quem CITA aquele endereço em outro
lugar**. Uma constante em Python, um `href` cravado num template, uma linha de
documento. Para a muralha, esse texto é só texto. O renomeador arruma o mapa,
passa verde, e a citação fica apontando para o endereço velho.

É o padrão 2 da `RETROSPECTIVA-FASE-D` na forma mais sutil dele: existe
mecanismo, ele é bom, e o buraco está exatamente onde ninguém olha porque "o
mapa já é conferido".

**Solução.** Se a sua tela cita endereços de fora, **cite o mapa e não o
endereço**: guarde no código só a chave (o endereço) e busque nome, explicação e
link em `painel/mapa-do-site.json`, em tempo de execução. Aí escreva o guarda
que fecha o triângulo:

```python
def test_toda_porta_existe_no_mapa_do_site():
    mapa = {e["endereco"]: e for e in json.loads(arquivo.read_text("utf-8"))["enderecos"]}
    orfas = [x for x in ENDERECOS_QUE_EU_CITO if x not in mapa]
    assert not orfas, f"endereços citados que o mapa não tem: {orfas}"
```

E, na tela, **endereço órfão não some**: ele vira um aviso visível, com o
endereço legível. Sumir em silêncio é a pior forma de perder um fato, e um
cartão que fica vazio se lê como *"esta parte não existe"*.

Com isso, renomear uma rota alheia passa a reprovar o PR de quem renomeou, com
uma mensagem que diz onde consertar. Sem isso, o alarme é o mantenedor clicando.

**Onde isto já vale:** `services/admin/apps/core/perpetuo.py` (a área do
lançamento perpétuo, 02/09/2026) é a primeira tela desenhada assim. A
`mapa_do_site.py` não precisa do guarda porque ela **é** o mapa: não cita, serve.

**Parente próxima:** `armadilhas/197` (o endereço público de uma célula sob
prefixo não é "prefixo + rota"), que é o erro de COMPOR o endereço; esta é o
erro de GUARDAR o endereço composto por outro. E `armadilhas/081`, que é a mesma
família dentro do teste: `reverse()` numa suíte de célula devolve o caminho
interno (`/perpetuo/`), nunca o público (`/admin/perpetuo/`) — comparar um com o
mapa dá vermelho na hora, e foi assim que a primeira versão deste guarda nasceu
quebrada.

**Origem:** 02/09/2026, ao construir `/admin/perpetuo/` a pedido do mantenedor.
