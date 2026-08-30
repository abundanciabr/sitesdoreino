---
schema_version: 2
armadilha: 235
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: só quem escreveu o guarda sabe QUAL defesa ele pretendia medir; nenhum portão consegue distinguir "verde porque a defesa funciona" de "verde porque a defesa vizinha cobriu" sem ler a intenção — mecanizar exigiria anotar cada teste com a linha de código que ele vigia, e a anotação apodreceria antes do teste
---

# O guarda de vazamento ficou verde com a defesa REMOVIDA — porque outra defesa, em série, cobriu por ela

**Sintoma.** Você escreve o guarda que interessa, monta um cenário com dente de
verdade (dado real para vazar, não uma fixture vazia), roda a sabotagem
prescrita pelo protocolo vermelho→verde — apaga a linha de defesa — e o teste
fica **VERDE**. Nenhum erro, nenhuma pista. O instinto é achar que a sabotagem
não aplicou (`armadilhas/155`); ela aplicou.

O caso medido, na porta de máquina da `gamificacao`:

```python
# o guarda
def test_perfil_de_OUTRO_site_nao_aparece():
    montar_o_cenario()                       # pessoa no site A, nível 7
    PerfilJogador.objects.create(pessoa=outra, site_id="outro-site", nivel=3)
    assert list(corpo(pedir(...))) == [ID_OPACO], "vazou perfil de outro site"

# a sabotagem: some o filtro de site da consulta de perfis
perfis = PerfilJogadorModel.objects.filter(pessoa_id__in=pedidos)   # site_id= apagado
```

Resultado: **1 passed**. O perfil do outro site foi lido, sim — e sumiu do mapa
um passo adiante, porque a busca do TÍTULO (`NivelDefinicao`, também filtrada
por site) não achou o nível 3 no site A, e a porta omite quem não tem título.
A segunda defesa engoliu a primeira, e o verde não era sobre a linha apagada.

**Causa.** Duas defesas **em série** no mesmo caminho, com o mesmo efeito
observável na saída. O teste mede a SAÍDA — e a saída não distingue "foi
barrado no filtro A" de "foi barrado no filtro B". O cenário tinha dente contra
o VAZAMENTO (havia o que vazar), mas não tinha dente contra a DEFESA MEDIDA: a
linha do outro site foi montada com um valor (`nivel=3`) que a defesa vizinha
já rejeitava sozinha.

É prima da `armadilhas/195` pelo outro lado da moeda. Lá o vermelho não provava
nada porque morreu antes da asserção; aqui o **verde** não prova nada porque a
asserção nunca dependeu da linha em questão. As duas têm a mesma raiz: a
evidência foi lida no agregado ("passou"/"falhou") em vez de na pergunta ("o quê,
exatamente, decidiu isto?").

**Solução: monte o cenário no vocabulário da defesa que você quer medir, e faça
a defesa vizinha ser INERTE nele.** Aqui, dar ao intruso o MESMO nível do
cenário — o nível que tem título neste site — desarma o filtro de título e
deixa só o de site respondendo:

```python
    # NÍVEL 7 de propósito, o mesmo do cenário: com um nível sem definição
    # neste site, ele sumiria pelo filtro de TÍTULO e o teste ficaria verde
    # mesmo com o filtro de SITE removido.
    PerfilJogador.objects.create(pessoa=outra, site_id="outro-site", nivel=7)
```

Com essa linha, a mesma sabotagem passa a dizer o que precisava dizer:

```
E       AssertionError: vazou perfil de outro site
E       assert ['p_ana_opaco...e_outra_loja'] == ['p_ana_opaco']
E         Left contains one more item: 'p_de_outra_loja'
```

**A regra que fica.** Sabotagem que dá VERDE é achado, não alívio — e o primeiro
palpite não é "a sabotagem não aplicou", é **"o que mais, nesse caminho, produz
a mesma saída?"**. Ache a defesa vizinha e neutralize-a NO CENÁRIO (nunca no
código: as duas defesas são boas, e defesa em profundidade é desenho, não
duplicação). Cheiro de que você está nesse caso: a sua asserção olha a
PRESENÇA/AUSÊNCIA de um item, e o item precisa atravessar mais de um `filter()`
para aparecer.

**Origem:** 30/08/2026, TAR-044 (a porta de máquina da gamificação, PR #656),
ao provar por sabotagem os guardas de `tests/test_porta_de_maquina.py`. O guarda
teria entrado no repositório verde, honesto na aparência e cego na única linha
que ele existia para vigiar.
