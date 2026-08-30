---
schema_version: 2
armadilha: 217
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  motivo: a restrição vive no banco (CheckConstraint em Topico e em Mensagem) e a suíte da célula mede que a semeadura não cria nenhuma Pessoa
sinal:
  - `got unexpected keyword arguments: 'publicado_pela_escola'`
  - `null value in column "autor_id" .* violates not-null constraint`
---

# Encher um espaço vazio sem inventar usuário: o modelo precisa saber que a INSTITUIÇÃO fala

**Sintoma.** Chega a tarefa de semear uma superfície social que nasceu deserta:
um fórum sem tópicos, um mural sem posts, uma comunidade sem a primeira
conversa. A regra é clara ("nada pode fingir ser de um usuário real"), você vai
escrever o seed, e descobre que o modelo não tem como cumpri-la:

```
django.db.utils.IntegrityError: null value in column "autor_id" of relation
"forum_topico" violates not-null constraint
```

Ou, se você tentar declarar a autoria institucional antes de criar o campo:

```
TypeError: Mensagem() got unexpected keyword arguments: 'publicado_pela_escola'
```

**Causa.** Toda modelagem de conteúdo social nasce com `autor` obrigatório
apontando para a tabela de pessoas, porque no momento do desenho só existia um
tipo de autor: gente. A instituição dona do produto não é uma linha dessa
tabela, e nunca deveria ser. Quando o seed chega, a saída de menor esforço é
óbvia e é a errada: **criar um usuário para a marca**. Ele passa a existir no
banco, ganha e-mail, aparece nas contagens de "quantas pessoas participam",
recebe notificação, e a primeira tela que listar participantes vai mostrar a
escola como se fosse um aluno. Ninguém volta para desfazer isso.

A tentação tem irmã mais grave: inventar VÁRIOS usuários, com nomes de gente,
para o salão parecer cheio. Num produto cujo público é criança, isso não é só
desonesto, é o tipo de coisa que ninguém consegue explicar depois.

**Solução: a ausência de pessoa não basta, a declaração precisa ser explícita.**
Três peças, e a ordem importa:

1. `autor` passa a aceitar nulo, E nasce ao lado um booleano explícito
   (`publicado_pela_escola`, `publicado_pela_equipe`, o nome do seu domínio).
2. Uma `CheckConstraint` no BANCO recusa as duas mentiras possíveis:

```python
models.CheckConstraint(
    condition=(
        models.Q(autor__isnull=False, publicado_pela_escola=False)
        | models.Q(autor__isnull=True, publicado_pela_escola=True)
    ),
    name="mensagem_de_pessoa_ou_da_escola",
)
```

3. A assinatura que a tela mostra sai de UMA função no modelo, nunca de um
   `|default:` espalhado por template.

**Por que o booleano não é redundante com `autor IS NULL`.** Parece campo
derivável, e a tentação de cortá-lo é forte. Ele existe para tornar a
declaração DELIBERADA: sem ele, a leitura seria "sem autor, logo é da
instituição", e qualquer caminho de código que esquecesse de preencher o autor
publicaria em nome da marca por acidente. Com ele, o esquecimento é recusado
pelo banco, que é o lado seguro do erro. Fail-closed não é "o silêncio fecha a
porta", é "o silêncio não decide nada".

**A armadilha de tela que vem junto, e que passa despercebida.** O template
quase sempre já tem um valor de reserva para quem não pôs nome de exibição:

```django
{{ mensagem.autor.nome_exibido|default:"alguém" }}
```

Com autor nulo, esse `default` cobre o buraco em silêncio, a página não quebra,
e a mensagem da instituição aparece assinada por **alguém**. É o avatar genérico
que sugere uma pessoa, escrito em palavra. O teste que pega isso mede o HTML e
recusa a string do reserva, não só confere que o nome da marca aparece em algum
lugar da página (ele costuma estar no cabeçalho, e a asserção fica verde à toa).

**A porta de máquina quebra junto.** Qualquer API que lia `autor.nome_exibido`
direto vira `AttributeError` num `None`, ou seja, HTTP 500 numa superfície que
ninguém abre no navegador e por isso ninguém vê falhar. Troque pela mesma
assinatura do modelo, no mesmo PR.

**E o conteúdo em si não é seu para publicar.** Quem sabe o que os usuários
realmente perguntam é o dono do produto. Entregue a capacidade e a lista
proposta num PR, e deixe a publicação num passo deliberado e separado
(`workflow_dispatch`), que só roda depois da aprovação. Um seed que subisse
junto do deploy publicaria em nome da instituição sem ela ter lido uma linha.

**Onde isto aconteceu:** célula `forum`, TAR-020, 30/08/2026 (PR 620). Ver
`services/forum/apps/forum/models.py` (`_fala_de_pessoa_ou_da_escola`) e
`services/forum/tests/test_semear_duvidas.py`.
