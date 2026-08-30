"""Publica no fórum as dúvidas mais frequentes da escola, já respondidas.

POR QUE O FÓRUM NÃO PODE ABRIR VAZIO
------------------------------------
Decisão do mantenedor em 30/08/2026 (registro `20260830-021`, tarefa TAR-020):
antes de a escrita abrir para os alunos, o fórum é semeado com as dúvidas reais
da escola. O motivo é medido no mundo, e não é opinião de produto: fórum que
abre deserto morre nos primeiros 90 dias. Quem chega numa página que diz
"nenhuma conversa por aqui ainda" não abre a primeira conversa, fecha a aba.

EM NOME DA ESCOLA, E ISSO NÃO SE NEGOCIA
----------------------------------------
A regra dura, escolhida por ele com todas as letras: as mensagens semeadas são
publicadas EM NOME DA ESCOLA. Nenhuma finge ser de aluno, nem com nome
inventado, nem com conta de mentira, nem com rótulo genérico que sugira uma
pessoa. Este comando **nunca cria uma `Pessoa`**, e a suíte mede isso
(`tests/test_semear_duvidas.py`).

Por isso a capacidade nasceu junto: até a TAR-020 o modelo exigia autor pessoa
em todo tópico e em toda mensagem, de modo que a única forma de a escola falar
seria inventar alguém. Hoje `autor` pode ser nulo desde que
`publicado_pela_escola` seja verdadeiro, e o BANCO recusa qualquer outra
combinação (`_fala_de_pessoa_ou_da_escola`, em `apps/forum/models.py`).

**A honestidade do formato importa tanto quanto a da autoria.** A primeira
mensagem de cada tópico não encena um aluno perguntando: ela diz, na voz da
escola, que aquela é uma pergunta que chega com frequência. A segunda mensagem
é a resposta, marcada como resposta aceita. O aluno que chega vê a dúvida dele
já resolvida e, de quebra, aprende como um tópico resolvido se parece.

POR QUE UM COMANDO, E NÃO UMA MIGRAÇÃO DE DADOS
-----------------------------------------------
A mesma razão do `semear_areas`, e ela já foi paga com juros: como migração,
uma tentativa em 30/08/2026 quebrou 20 testes, a maioria com `UniqueViolation`
no slug. Migração de dados entra no banco de TODO teste, e todo teste que
afirma "o fórum vazio faz X" deixaria de poder existir. Semear é CONTEÚDO, não
esquema.

E há a razão de dono: a partir do momento em que estes tópicos existem, eles são
do mantenedor. Uma migração os recriaria em todo ambiente novo, inclusive os que
ele tivesse apagado de propósito.

IDEMPOTENTE, E QUE NÃO PISA EM EDIÇÃO HUMANA
--------------------------------------------
A chave é a dupla (área, título). Tópico que já existe não é tocado: nem o
título, nem o texto, nem a resposta aceita. Se ele reescrever uma resposta com
as palavras dele, rodar de novo não desfaz.

O TEXTO SAI SEM TRAVESSÃO
-------------------------
Decisão dele em 30/08/2026: texto publicado não leva travessão. Este arquivo
está DENTRO da superfície pública de `ci/travessao.py` (a pasta `commands/`
inteira entra), então o portão do repositório o varre a cada PR. A troca é uma
reescrita da frase, nunca um caractere trocado.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.forum.models import Area, Mensagem, Topico

# ===========================================================================
# O CONTEÚDO — a parte que é do mantenedor, e que ele revisa antes de ir ao ar
# ===========================================================================
# Cada item vira um tópico com duas mensagens: a apresentação da dúvida e a
# resposta. As duas são da escola.
#
# `area` é o slug de uma área criada por `semear_areas`. Se ela não existir, o
# comando PARA sem escrever nada: publicar conteúdo não é criar área.
DUVIDAS = [
    {
        "area": "avisos",
        "fixado": True,
        "titulo": "Como o fórum da escola funciona",
        "pergunta": (
            "Este é o primeiro tópico do fórum, e ele responde a pergunta que "
            "todo mundo faz ao chegar: o que dá para fazer aqui?\n\n"
            "O fórum é o lugar de perguntar, de responder e de mostrar o que "
            "você está construindo. Ele abre já com as dúvidas que mais chegam "
            "para a escola, todas respondidas, porque uma página vazia não "
            "ajuda ninguém a começar."
        ),
        "resposta": (
            "São quatro áreas, e cada uma tem uma função.\n\n"
            "Avisos da escola é esta aqui. Quem publica é a equipe, e é a única "
            "página que qualquer pessoa lê sem entrar.\n\n"
            "Dúvidas gerais é onde você pergunta. Travou no Blender, a textura "
            "esticou, o Roblox recusou o item? É ali.\n\n"
            "Mostre seu trabalho é onde você posta o que está fazendo. Modelo "
            "pela metade também conta.\n\n"
            "Sala dos alunos é a conversa de turma, para quem está matriculado.\n\n"
            "Quando uma resposta resolve a dúvida, o professor a marca como "
            "resposta aceita. Assim quem chegar depois encontra o caminho "
            "pronto, sem precisar perguntar de novo."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Preciso de um computador potente para começar no Blender?",
        "pergunta": (
            "Esta é a primeira pergunta de quase todo aluno novo, muitas vezes "
            "antes mesmo da matrícula. Ela merece uma resposta com números, e "
            'não um "depende".'
        ),
        "resposta": (
            "Não precisa. O Blender roda em computador simples, e os modelos "
            "que vendem no Roblox são leves de propósito: um cabelo, um "
            "acessório ou uma roupa têm poucos milhares de polígonos, porque o "
            "Roblox impõe limites baixos para o jogo rodar em celular.\n\n"
            "O que costuma travar não é a máquina, é o arquivo que foi ficando "
            "pesado sem necessidade. Se o seu computador abre um navegador com "
            "várias abas sem engasgar, ele abre o Blender.\n\n"
            "Duas coisas ajudam mais que trocar de computador: salvar versões "
            "do arquivo enquanto você trabalha, e fechar o Roblox Studio "
            "enquanto não estiver exportando."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Quanto tempo leva até eu conseguir o primeiro cliente?",
        "pergunta": (
            "Esta chega sempre, e ela merece uma resposta honesta em vez de "
            "uma promessa."
        ),
        "resposta": (
            "Não existe prazo garantido, e quem promete um está vendendo, não "
            "ensinando. O que existe é uma ordem que funciona.\n\n"
            "Primeiro vem saber fazer, e isso se mede em modelos prontos, não "
            "em aulas assistidas. Depois vem o portfólio, que é esse conjunto "
            "de modelos apresentado de um jeito que alguém entenda em dez "
            "segundos. Só então vem procurar cliente, porque antes do "
            "portfólio não há o que mostrar.\n\n"
            "Quem trata as tarefas do curso como trabalho de verdade, e não "
            "como exercício para conferir, chega ao portfólio bem mais rápido. "
            "É por isso que a escola insiste que você poste aqui o que está "
            "fazendo: material postado vira portfólio, e material guardado na "
            "pasta não vira nada."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "O Roblox recusou meu acessório na loja UGC. O que costuma ser?",
        "pergunta": (
            "A recusa chega sem explicação detalhada, e o aluno costuma achar "
            "que fez algo grave. Quase nunca é o caso."
        ),
        "resposta": (
            "Na maioria das vezes é uma regra técnica, e não uma opinião sobre "
            "o seu trabalho. Os motivos que mais aparecem são estes.\n\n"
            "O item passou do limite de polígonos ou do tamanho de textura "
            "permitido para a categoria. Cada tipo de acessório tem o seu teto, "
            "e ele é baixo.\n\n"
            "O modelo saiu com a escala errada e não encaixa no corpo padrão. "
            "Vale sempre testar dentro do Roblox Studio antes de enviar.\n\n"
            "A textura ficou transparente onde não deveria, ou com a costura "
            "aparecendo na emenda do mapa.\n\n"
            "O item lembra demais uma marca registrada ou algo de outro jogo. "
            "Este é o único caso em que a recusa é sobre conteúdo, e refazer é "
            "o caminho.\n\n"
            "Antes de reenviar, poste aqui uma imagem do modelo e as medidas. "
            "Na maior parte das vezes dá para apontar o problema pela imagem."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Como faço a textura não esticar quando aplico no modelo?",
        "pergunta": (
            "Esta é a dúvida técnica número um dos primeiros meses, e ela tem "
            "uma causa só na esmagadora maioria dos casos."
        ),
        "resposta": (
            "Textura que estica é quase sempre problema de mapa UV, e não da "
            "imagem.\n\n"
            "O mapa UV é a planificação do modelo, como o molde de uma roupa "
            "aberto em cima da mesa. Se o molde tem pedaços de tamanhos muito "
            "diferentes entre si, a imagem chega esticada nos pedaços grandes e "
            "apertada nos pequenos.\n\n"
            "O caminho é este. Marque as costuras onde a peça abriria de "
            "verdade, refaça a planificação, e confira o resultado com uma "
            "textura quadriculada de teste. Se os quadrados aparecem quadrados "
            "no modelo inteiro, a textura vai se comportar. Se aparecem "
            "retângulos em alguma parte, é exatamente ali que ela vai esticar.\n\n"
            "Só depois de o quadriculado ficar certo é que vale a pena pintar."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Qual é a diferença entre vender na loja UGC e fazer encomenda?",
        "pergunta": (
            "Os dois caminhos aparecem no curso, e confundir um com o outro "
            "atrapalha na hora de escolher onde investir o seu tempo."
        ),
        "resposta": (
            "São dois negócios diferentes com a mesma habilidade por trás.\n\n"
            "A encomenda é trabalho sob medida: alguém pede, você entrega, e "
            "recebe uma vez. O dinheiro entra mais rápido, e você depende de "
            "encontrar cliente toda vez.\n\n"
            "A loja UGC é o contrário. Você publica um item uma vez e ele "
            "continua vendendo sozinho enquanto houver gente comprando. Demora "
            "mais para render, e não depende de você estar disponível.\n\n"
            "Quem está começando costuma se dar melhor pela encomenda, porque "
            "ela ensina prazo, conversa e revisão com cliente de verdade. A "
            "loja rende mais depois, quando você já sabe o que as pessoas "
            "procuram."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Sou menor de idade. Consigo receber em dólar pelo meu trabalho?",
        "pergunta": (
            "Quase todo aluno faz esta pergunta, e ela é uma das poucas que a "
            "família precisa responder junto."
        ),
        "resposta": (
            "Consegue, com o seu responsável junto. Isso não é burocracia à "
            "toa: as plataformas de pagamento e os sites de trabalho pedem "
            "idade mínima e documento, e a conta precisa estar no nome de quem "
            "tem essa idade.\n\n"
            "Na prática funciona assim. O trabalho é seu, a conta que recebe é "
            "do seu responsável, e vocês combinam antes como o dinheiro fica. "
            "Fazer diferente disso costuma terminar em conta bloqueada, com o "
            "dinheiro preso lá dentro.\n\n"
            "Se o seu responsável quiser entender o passo a passo antes de você "
            "procurar o primeiro cliente, pergunte aqui. A escola prefere "
            "responder essa parte antes do primeiro trabalho, e não depois."
        ),
    },
    {
        "area": "duvidas",
        "titulo": "Meu modelo fica com o tamanho errado no Roblox Studio. Por quê?",
        "pergunta": (
            "O modelo fica lindo no Blender e chega gigante ou minúsculo do "
            "outro lado. Acontece com quase todo mundo pelo menos uma vez."
        ),
        "resposta": (
            "Os dois programas medem o mundo em unidades diferentes, e a "
            "exportação não adivinha qual delas você quis dizer.\n\n"
            "O conserto tem três partes, nesta ordem.\n\n"
            "Antes de exportar, aplique a escala do objeto no Blender. Enquanto "
            "ela estiver só no visual, o arquivo continua carregando um número "
            "que o Roblox vai interpretar do jeito dele.\n\n"
            "Confira a unidade da cena e a escala da exportação. Um valor "
            "errado ali multiplica tudo de uma vez.\n\n"
            "Teste no Roblox Studio contra o corpo padrão antes de enviar. "
            "Comparar com o avatar é mais confiável do que acreditar no "
            "número.\n\n"
            "Se continuar errado depois disso, poste aqui a imagem das duas "
            "telas. O erro costuma aparecer na primeira olhada."
        ),
    },
    {
        "area": "mostre-seu-trabalho",
        "titulo": "Posso postar um modelo que ainda não terminei?",
        "pergunta": (
            "Muita gente espera o trabalho ficar perfeito para mostrar, e "
            "acaba nunca mostrando nada."
        ),
        "resposta": (
            "Pode, e é o que a escola prefere. Modelo pela metade é o que mais "
            "ensina, pois é vendo o meio do caminho que se aprende o "
            "caminho.\n\n"
            "Na hora de postar, ajuda muito escrever três coisas junto da "
            "imagem: o que você quis fazer, o que travou, e o que você já "
            "tentou. Um post com essas três linhas costuma receber resposta "
            "útil no mesmo dia. Uma imagem sozinha costuma receber elogio, que "
            "é gostoso e não resolve.\n\n"
            "Não existe trabalho ruim demais para postar aqui. Existe trabalho "
            "parado na pasta, e esse não melhora sozinho."
        ),
    },
    {
        "area": "sala-dos-alunos",
        "titulo": "Posso contratar um colega da turma para um projeto meu?",
        "pergunta": (
            "A comunidade da escola foi feita para isso, e a pergunta aparece "
            "assim que alguém pega o primeiro trabalho maior."
        ),
        "resposta": (
            "Pode, e este é um dos motivos de a sala existir. Um aluno pegar um "
            "trabalho grande e chamar outro para a parte que ele faz melhor é "
            "exatamente o que acontece no mercado.\n\n"
            "Três combinados evitam quase todo problema.\n\n"
            "Combinem antes o que cada um entrega, e deixem isso escrito, nem "
            "que seja numa mensagem aqui.\n\n"
            "Combinem antes quanto e quando, mesmo entre amigos. Trabalho sem "
            "valor combinado é a origem da maior parte das brigas.\n\n"
            "Se um dos dois for menor de idade, o responsável precisa saber. "
            "Vale a mesma regra do pagamento em dólar.\n\n"
            "A escola não entra como parte no combinado de vocês, mas responde "
            "dúvida sobre como fechar um. É só perguntar aqui."
        ),
    },
]


class Command(BaseCommand):
    help = "Publica as duvidas frequentes da escola no forum (idempotente)"

    def handle(self, *args, **opcoes):
        areas = {a.slug: a for a in Area.objects.all()}
        faltando = sorted({d["area"] for d in DUVIDAS} - set(areas))
        if faltando:
            # Fail-closed, e a recusa ensina a saída na mesma tela. Criar a área
            # aqui seria este comando virando dono do que é do `semear_areas`, e
            # uma área nascida por engano numa semeadura de conteúdo entraria com
            # a permissão errada.
            raise CommandError(
                "PAROU POR SEGURANCA: nao encontrei estas areas no banco: "
                + ", ".join(faltando)
                + ". Rode `python manage.py semear_areas` antes. "
                "NADA foi publicado."
            )

        criados, mantidos = [], []
        for duvida in DUVIDAS:
            area = areas[duvida["area"]]
            titulo = duvida["titulo"]
            if Topico.objects.filter(area=area, titulo=titulo).exists():
                mantidos.append(titulo)
                continue

            # Uma transação por tópico: se algo falhar no meio, ninguém fica com
            # uma pergunta publicada sem a resposta embaixo. Fórum semeado com
            # pergunta sem resposta é pior que fórum vazio.
            with transaction.atomic():
                topico = Topico.objects.create(
                    area=area,
                    autor=None,
                    publicado_pela_escola=True,
                    titulo=titulo,
                    fixado=bool(duvida.get("fixado")),
                )
                for texto in (duvida["pergunta"], duvida["resposta"]):
                    mensagem = Mensagem.objects.create(
                        topico=topico,
                        autor=None,
                        publicado_pela_escola=True,
                        texto=texto,
                    )
                    mensagem.indexar_para_busca()
                # A resposta é a última criada, e ela nasce já com o selo de
                # resolvida: é o selo que transforma o fórum em patrimônio em
                # vez de arquivo morto (lei §5).
                topico.resposta_aceita = mensagem
                topico.save(update_fields=["resposta_aceita"])
            criados.append(titulo)

        for titulo in criados:
            self.stdout.write(f"  publicado .... {titulo}")
        for titulo in mantidos:
            self.stdout.write(f"  ja existia ... {titulo} (nao toquei)")

        # A contagem sai do BANCO, e não do laço acima: contar o que se acabou
        # de mandar fazer é acreditar no próprio pedido.
        da_escola = Topico.objects.filter(publicado_pela_escola=True).count()
        de_pessoas = Topico.objects.filter(publicado_pela_escola=False).count()
        self.stdout.write(f"TOPICOS DA ESCOLA: {da_escola}")
        self.stdout.write(f"topicos de alunos: {de_pessoas}")
        # A linha que o pipeline procura. Só existe aqui, no fim do caminho
        # feliz, e nunca no eco do script (`armadilhas/114`).
        self.stdout.write("SEMEADURA DAS DUVIDAS OK")
