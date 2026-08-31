---
schema_version: 2
armadilha: 254
degrau: 5
confianca: alta
custo_por_queda: medio
estado: guardada
guarda:
  tipo: muralha
  motivo: RESOLVIDA no mesmo dia (TAR-087, PR do dia). `ci/travessao.py` passou a enxergar os RÓTULOS de todo `TextChoices` (automático, sem marca) e qualquer arquivo que se declare com o comentário `ci:texto-publicado` (inteiro). Roda em todo PR pela `ci/muralha-do-travessao.sh`, fail-closed. Guardas em `ci/tests/test_travessao.py` seção 9 — inclusive os NEGATIVOS, que impedem a superfície de crescer para todo `.py` e afogar o portão em ruído
---

# O rótulo de um `TextChoices` é texto publicado, e mora onde nenhum portão de texto olha

**Sintoma.** Duplo, e os dois lados são silenciosos.

1. O aluno lê no site uma palavra que ninguém escreveu para ele ler: "Em
   análise", "Pendente", "Rascunho". Nenhuma tela explica o que ela quer dizer,
   e a página não tem defeito nenhum. Descobre-se quando uma PESSOA olha o site
   e pergunta o que aquilo significa.
2. Um travessão publicado passa por um repositório que tem portão contra
   travessão, e o portão fica verde. `ci/travessao.py --listar` não acha nada,
   porque o arquivo nem está na varredura.

**Causa.** `class Status(models.TextChoices)` tem DOIS campos por linha, e o
segundo é interface:

```python
EM_ANALISE = "em_analise", "Em análise"
#            ^ contrato       ^ texto que o aluno lê na tela
```

O primeiro é código: viaja em contrato congelado (`contracts/eventos/…`), em
migration e em banco, e trocá-lo é um Rito. O segundo sai em
`{{ objeto.get_status_display }}`, no selo, na linha do tempo e no aviso do
sininho — é cópia do site, escrita uma vez num arquivo de MODELO e nunca mais
revisada como texto.

E `models.py` não está na superfície de nenhum portão de texto: a de
`ci/travessao.py` é `templates/` + `traducoes/` + `documentos/` +
`management/commands/`. A escolha é deliberada e está declarada lá (varrer `.py`
inteiro mediria docstring e log, e medir a coisa errada com precisão é como um
portão morre) — mas o efeito é que a cópia do site tem um cômodo sem porta.

Os dois sintomas têm a mesma raiz: **o rótulo é tratado como nome de constante,
não como frase que alguém vai ler.** Ninguém o revisa, ninguém o explica,
nenhuma régua de texto o alcança.

**Solução, em duas metades.**

1. **Toda situação que vira selo na tela precisa de uma frase que a explique, e
   a frase mora numa fonte só.** Um dicionário ao lado da lista de etapas
   (`EXPLICACAO_DAS_ETAPAS` em `apps/core/participacao.py`), lido por TODAS as
   telas que desenham aquele caminho. Dois guardas seguram isto:

   ```python
   # 1. situação nova no model nasce com frase, ou fica vermelho aqui
   sem_texto = {s.value for s in Modelo.Status} - set(EXPLICACAO_DAS_ETAPAS)
   assert not sem_texto

   # 2. e a frase não é copiada num template, onde envelheceria sozinha
   for arquivo in TEMPLATES.glob("*.html"):
       for texto in EXPLICACAO_DAS_ETAPAS.values():
           assert texto not in arquivo.read_text(encoding="utf-8")
   ```

   O segundo é o que não é óbvio: no HTML renderizado, o texto vindo do Python e
   o copiado à mão são indistinguíveis, e é isso que torna a cópia perigosa. Só
   lendo o DISCO dá para medir a diferença.

2. **A régua de texto do repositório se reimplanta na célula, enquanto o portão
   não alcançar o arquivo.** Um teste da célula que percorre os rótulos de
   `Modelo.Status` e as constantes de cópia e aplica a mesma lista de riscas do
   `CLAUDE.md`. É barato, e é a diferença entre um limite conhecido e um buraco.

**A varredura das telas se DERIVA, nunca se lista.** Quem explica o caminho não
é "a página X e a página Y": é toda tela que desenha etapa. O guarda acha as
telas pela marca no template (`in linha_do_tempo`, `in faixa`) e exige a legenda
em cada uma, com um `assert len(achadas) >= 2` para não passar verde varrendo
nada. Lista escrita à mão envelhece na primeira tela nova, que é a Classe 8 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` e o mesmo remédio da `armadilhas/242`.

**Origem.** 31/08/2026, Caixa de Sugestões. O mantenedor abriu a linha do tempo
de uma ideia, viu "Em análise" e perguntou se aquilo não deveria se chamar "Em
votação", para incentivar os alunos a votar. A pergunta destapou o buraco de
verdade: a Caixa desenhava quatro etapas em DUAS telas, havia uma semana, e
nenhuma das duas dizia o que elas significam. Ele decidiu manter o nome e
mandar a Caixa explicar (registro `20260831-107`, PR [#782](https://github.com/abundanciabr/sitesdoreino/pull/782)).

A segunda metade veio de graça na mesma tarefa: as explicações novas foram
escritas em `apps/core/participacao.py`, e ao conferir a lei do travessão ficou
claro que nem elas nem os rótulos antigos jamais estiveram sob o portão. O
`ci/travessao.py` já previa isto por escrito ("se um dia a cópia do site passar
a morar em `.py`, é aqui que a superfície cresce") — este é o dia.

---

## ATUALIZAÇÃO 31/08/2026, no mesmo dia: o portão do repositório passou a cobrir isto

A entrada nasceu com `guarda: teste` porque o conserto definitivo dependia de
mandato — `ci/` é caminho CODEOWNERS. O mantenedor deu o mandato no mesmo dia, e
a segunda metade da solução deixou de ser "reimplante a régua na célula":

* **quem declara `Choices` com rótulo escrito entra sozinho**, e só o RÓTULO é
  medido (`_so_os_rotulos_de_choices`). Sem marca, sem lista, sem lembrar;
* **quem se declara** com o comentário `ci:texto-publicado` entra INTEIRO, pela
  peneira dos comandos de gestão;
* `migrations/` fica fora das duas.

**O que a mudança pescou na primeira execução, e nenhum humano tinha visto:**
três rótulos do fórum (`"Pública — qualquer um lê"` e irmãos, em
`services/forum/apps/forum/models.py`) e **três frases da Caixa que o aluno lê
quando erra** — a validação `"Conte qual é o problema — é o que os outros
votam."` e o aviso de limite `"Espere a janela virar — enquanto isso…"`, ambas
em `apps/core/participacao.py`. Estavam publicadas havia dias.

Duas notas que economizam uma rodada a quem repetir isto:

* **Rótulo de `TextChoices` NÃO precisa de migração de dados.** O banco guarda o
  VALOR; o rótulo é montado ao desenhar a tela. É a diferença entre esta classe
  e a do semeador (`armadilhas` do §"texto gravado no banco"), onde corrigir o
  código não corrige a linha já criada.
* **A frase `"Conte qual é o problema — é o que os outros votam."` é o exemplo
  vivo do erro que a lei do `CLAUDE.md` descreve:** depois da risca vem `é`,
  continuação direta, e dois-pontos QUEBRA a frase. A troca certa foi ponto
  final: `"Conte qual é o problema. É o que os outros votam."`
