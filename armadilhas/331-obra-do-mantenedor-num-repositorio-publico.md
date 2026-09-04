# 331 — Obra não lançada do mantenedor guardada no repositório PÚBLICO

**Data:** 04/09/2026 · **Onde:** qualquer célula que guarde texto dele ·
**Custo evitado:** o livro dele legível por qualquer pessoa antes do lançamento

## Sintoma

Ele manda um texto ("guarde isto para o projeto online do livro") e o caminho
mais curto é o que esta casa já usa para os documentos do site: escrever o `.md`
numa pasta-semente e deixar uma migração despejá-lo no banco. Tudo verde: o
teste passa, a muralha passa, o deploy sobe, a tela mostra o texto.

E o capítulo do livro dele passa a estar em
`github.com/abundanciabr/sitesdoreino`, aberto, para sempre — inclusive no
histórico, depois de qualquer remoção.

## Causa

**O repositório deste projeto é público de propósito**
(`project_plano_robos_sem_colisao`, decisão dele), e o padrão de semeadura da
casa foi desenhado para texto que JÁ era público: `documentos/` guarda a página
"Como funciona a entrada", que existe para o mundo ler. O padrão é bom, e é o
CONTEÚDO que muda de natureza sem que nada no mecanismo avise.

Nenhum portão pega isto. O guarda de segredos procura credencial, não obra; o
travessão mede pontuação; o orçamento conta arquivos. Uma migração com o
capítulo dentro é um arquivo `.py` bem-comportado.

## Solução

**Conteúdo não lançado do mantenedor entra pela TELA, nunca por arquivo.** A
tabela nasce vazia, e a migração não semeia nada — e isso se escreve na
migração, para o próximo agente não "consertar" a ausência:

```python
# NAO HA SEMEADURA AQUI, e a ausencia e a decisao. Este repositorio e PUBLICO e
# o livro nao esta lancado: o unico caminho do texto para dentro do sistema e a
# tela, colado por ele.
```

Três perguntas antes de guardar texto dele em arquivo:

1. **Isto já é público?** Página do site, documento em `/docs/`, texto de
   interface: pode ir para o repositório. Livro, curso não lançado, lista de
   alunos, roteiro: não vai.
2. **Ele pode querer publicar isto DEPOIS?** Então o lugar é o banco, e a
   publicação é uma decisão futura com tela própria.
3. **A tela vai devolver o arquivo?** Se o texto só existe no banco, o botão de
   baixar deixa de ser conveniência e vira a cópia de segurança dele. O banco da
   VPS só é copiado ANTES de cada atualização do sistema
   (`infra/deploy-celula-na-vps.sh`), e não todo dia.

## O parente que confunde

`armadilhas/253` diz que corrigir um semeador NÃO corrige o que já foi semeado.
É o mesmo mecanismo visto do outro lado: lá o problema é o arquivo não alcançar
o banco; aqui é o texto não dever nem chegar ao arquivo.

**Quem faz valer:** ninguém, e a lacuna está dita na cara. Não há forma mecânica
barata de uma máquina saber se um `.md` é obra não lançada ou página de site.
O que existe é o desenho: a Biblioteca do Livro (`services/admin/apps/core/livro.py`)
não tem semeadura e não tem rota pública, e `tests/test_livro.py::test_o_livro_nao_tem_nenhuma_rota_publica`
reprova o PR que abrir uma.
