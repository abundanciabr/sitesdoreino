# apps/core/analise_da_caixa.py — a leitura da Caixa, com os fatos sempre vivos
"""A sexta aba da gestão da Caixa: o que a turma pediu, lido e ordenado.

Nasceu em 05/09/2026, de um pedido do mantenedor: *"analise as sugestões dos
alunos e liste tudo num documento único, da mais votada para a menos votada"*.
A primeira resposta foi uma página fora do site, e ele respondeu com a regra que
virou lei: **entrega minha mora no site, nunca num artefato solto**
(`docs/decisoes/DECISAO-onde-mora-o-que-eu-entrego.md`).

## A divisão que faz esta tela não envelhecer

    FATO      votos, plateia, etapa, título, o texto do aluno, os comentários
              → vêm VIVOS da Caixa a cada abertura (`CaixaClient.ideias`)

    JULGAMENTO  por que isto importa, o que é preciso para acontecer, de quem
                é a mesa, com que outras ideias se junta
                → mora aqui, em `ANALISE`, escrito por quem analisou

Um documento congelado com "40 votos" escrito dentro mentiria no dia seguinte,
e seria a lista paralela que a lei anti-duplicação proíbe (`CLAUDE.md`). Aqui a
ordem, os totais, as somas por família e os números dos padrões são todos
CALCULADOS do que a Caixa responde agora. O que está escrito à mão é o que
nenhuma máquina saberia: o que a ideia significa.

**Ideia que chega depois desta análise não some e não mente**: ela aparece na
sua própria seção, dizendo que ainda não foi lida. E análise de ideia que foi
apagada ou arquivada simplesmente não desenha nada, porque o laço é sobre o que
a Caixa respondeu, nunca sobre este dicionário.

## Por que não há JavaScript aqui

O modal de cada ideia abre por `:target` — o link `#ideia-20` faz o CSS mostrar
a caixa, e o botão de fechar é um link de volta para o cartão. Sem script, a
porta (`script-src 'self'`) não precisa de exceção nenhuma, o botão "voltar" do
navegador fecha o modal, e o endereço de uma ideia aberta pode ser copiado e
mandado para alguém. O que se perde: a tecla Esc não fecha. Por isso todo modal
tem um "Fechar" visível em cima e o fundo inteiro é clicável.
"""

from datetime import datetime, timezone as tz
from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .caixa import _data_curta, _email, _enriquecer, _etapa_de, _quem, esperando
from .clients import CaixaClient
from .views import _auditar

# ---------------------------------------------------------------------------
# As três mesas — de quem é a vez de trabalhar
# ---------------------------------------------------------------------------
#
# A mesa responde "quem começa", não "quem termina": o guia de portfólio (21)
# precisa dos critérios da Lívia ANTES da tela, e mesmo assim é obra de site,
# porque é a tela que não existe. Quando as duas mãos entram, a mesa é a de
# quem sem a qual nada anda.
MESAS = {
    "gravacao": ("Gravação", "aula nova ou vídeo de conserto, gravado pela Lívia"),
    "site": ("Obra de site", "tela, página ou rotina, construída por um robô"),
    "voce": ("Sua decisão", "rumo do produto: ninguém decide isto no seu lugar"),
}

# As famílias, na ordem em que a tela as mostra: por votos somados, que é
# calculado. A ordem escrita aqui é só o desempate quando duas empatam.
FAMILIAS = (
    ("cabelos", "Cabelos e acessórios", "O assunto mais pedido do quadro."),
    (
        "reta-final",
        "Reta final e trilha de estudo",
        "Onde o aluno trava perto de vender.",
    ),
    (
        "primeiro-cliente",
        "Da aula ao primeiro cliente",
        "A turma desenhou o que já está em obra.",
    ),
    (
        "acabamento",
        "Texturização e acabamento",
        "A dor difusa que aparece em cinco formas.",
    ),
    (
        "novos-itens",
        "Novos itens para vender",
        "Categorias de produto que o curso ainda não cobre.",
    ),
    (
        "praticar",
        "Praticar e mostrar trabalho",
        "Exercício, vitrine e material compartilhado.",
    ),
    ("avisos", "Avisos e comunicação", "O que se perde no meio do WhatsApp."),
    ("manutencao", "Manutenção do curso", "Aula que existe e precisa de reforço."),
    ("fora-do-trilho", "Fora do trilho de hoje", "Interesse real, outra profissão."),
)

# ---------------------------------------------------------------------------
# O JULGAMENTO — uma entrada por ideia, escrita à mão, sem um único número
# ---------------------------------------------------------------------------
#
# Número nenhum entra aqui, nem "40 votos" nem "a mais votada": isso é fato, e
# fato vem vivo. O que entra é o que a máquina não sabe.
#
#   familia    a chave de FAMILIAS
#   mesa       a chave de MESAS
#   importa    por que vale fazer, em uma ou duas frases
#   precisa    o que tem de acontecer para sair do papel
#   junta_com  ideias que são, na prática, o mesmo trabalho
#   ja_existe  um comentário da turma diz que a coisa já existe (confira antes)
#   em_obra    a casa já está construindo isto por outro caminho
#   tarefa     o despacho pronto, para virar tarefa no painel de quem executa
ANALISE = {
    20: {
        "familia": "cabelos",
        "mesa": "gravacao",
        "importa": "Acessório é o par natural do produto que a escola mais ensina a vender: "
        "quem domina o combo entrega o pedido inteiro em vez de recusar metade do trabalho.",
        "precisa": "Gravar uma ou duas aulas (modelar o acessório, encaixar na cabeça do avatar, "
        "versão leve e versão detalhada, textura) e publicar. Obra de gravação, sem código. "
        "O documento de obra já existe: CS-CURSOS-0001.",
        "tarefa": {
            "titulo": "Gravar a aula de chapéu e acessórios",
            "texto": "Aula (ou duas) cobrindo: modelar o acessório, encaixar na cabeça do avatar do "
            "Roblox, versão leve e versão detalhada, textura. É a ideia mais votada da Caixa e o par "
            "do produto que a escola mais ensina a vender. Documento de obra: CS-CURSOS-0001.",
        },
    },
    21: {
        "familia": "reta-final",
        "mesa": "site",
        "importa": "Quem escreveu terminou as aulas e travou na reta final. É o momento clássico de "
        "desistência, com o primeiro dinheiro já quase na mesa.",
        "precisa": "Só a sua assinatura, aqui mesmo nesta tela. Os critérios já chegaram: a "
        "professora escreveu o rascunho dela em 05/09 (pelo menos 3 tipos de modelo, 3 peças de "
        "cada, a maioria em high poly, nada parecido com a aula) e ele está guardado no plano do "
        "portfólio. Assinado o documento, a casa nova das páginas do aluno, chamada pages, nasce "
        "primeiro: é a fundação dela mais um passo seu no servidor. Depois vem a tela do guia, "
        "com o checklist salvo por aluno. O documento de obra já existe: CS-PAGES-0001.",
        "tarefa": {
            "titulo": "Guia de portfólio com checklist na área do aluno",
            "texto": "Tela com os critérios da escola e um checklist cujo progresso fica salvo por "
            "aluno, na casa pages. Pré-requisito: a fundação da célula pages. Os critérios da "
            "professora já existem, em rascunho, no plano do portfólio. "
            "Documento de obra: CS-PAGES-0001.",
        },
    },
    19: {
        "familia": "cabelos",
        "mesa": "gravacao",
        "ja_existe": True,
        "importa": "Metade dos avatares é masculina: quem só faz cabelo feminino atende metade do "
        "mercado.",
        "precisa": "A aula existe, gravada e completa (o mantenedor tem o link em 05/09/2026). "
        "O que falta é o link morar dentro da plataforma e a ideia ser respondida com ele.",
        "tarefa": {
            "titulo": "Publicar na plataforma a aula de cabelo masculino que já existe",
            "texto": "O vídeo existe e está fora da plataforma. Colocá-lo onde a turma assiste às "
            "demais aulas e responder a ideia com o link. Custo quase zero, e mata a dúvida de "
            "todo mundo que hoje acha que o assunto não foi ensinado.",
        },
    },
    22: {
        "familia": "novos-itens",
        "mesa": "gravacao",
        "ja_existe": True,
        "importa": "Armas são categoria forte de venda, e o pedido é extensão natural do que o curso "
        "já ensina nas armas de fogo.",
        "precisa": "Conferir com a Lívia se a aula existe (um comentário da turma diz que sim). "
        "Existindo, responder com o link. Não existindo, é gravação de escopo bem definido.",
        "tarefa": {
            "titulo": "Conferir e, se faltar, gravar a aula de armas brancas",
            "texto": "Facas, espadas e machados, nas versões leve e detalhada, aproveitando a base "
            "das armas de fogo. Antes de gravar, conferir o comentário da turma que diz que a aula "
            "já existe.",
        },
    },
    36: {
        "familia": "primeiro-cliente",
        "mesa": "site",
        "em_obra": True,
        "junta_com": (25, 38),
        "importa": "A ideia mais debatida do quadro, com alunos aprimorando a proposta uns dos outros. "
        "E ela descreve, quase palavra por palavra, o que a casa já decidiu construir: quando a turma "
        "desenha sozinha o produto que está em obra, o rumo está certo.",
        "precisa": "Quase nada a inventar: é conectar o mural de encomendas (em construção), a "
        "economia de pontos (pronta e desligada) e as simulações, que podem nascer como exercícios "
        "avaliados da área de cursos. O passo de hoje é responder contando a obra, sem prometer data.",
    },
    23: {
        "familia": "acabamento",
        "mesa": "gravacao",
        "importa": "Dor de bastidor real: horas perdidas caçando erro bobo é o que mais desanima quem "
        "estuda à noite depois do trabalho.",
        "precisa": "A ferramenta automática dentro do Blender seria cara e incerta. O mesmo problema "
        "morre por dois caminhos provados: uma aula de diagnóstico dos erros comuns e a correção dos "
        "trabalhos enviados na área de cursos.",
        "tarefa": {
            "titulo": "Aula de diagnóstico dos erros de textura",
            "texto": "Os erros mais comuns e como achar cada um: espelhamento, peças duplicadas, "
            "pintura fora do lugar, malha aberta errada. Entra no módulo de texturização.",
        },
    },
    25: {
        "familia": "primeiro-cliente",
        "mesa": "site",
        "em_obra": True,
        "junta_com": (36,),
        "importa": "Mesma direção da 36, com um acréscimo valioso: dividir trabalho grande entre "
        "alunos, o que dá experiência real a quem ainda não teria uma encomenda inteira.",
        "precisa": "É o mural de encomendas já em construção, mais o selo de entrega (as medalhas da "
        "economia de pontos, prontas e desligadas).",
    },
    34: {
        "familia": "primeiro-cliente",
        "mesa": "site",
        "importa": "Responde a pergunta mais prática de quem termina o curso: onde estão os clientes. "
        "Custo baixíssimo, retorno direto no bolso do aluno.",
        "precisa": "Uma página na área do aluno com lista curada: a Lívia indica os lugares, a equipe "
        "mantém. O editor de documentos já permite manter essa página sem tocar em código.",
        "tarefa": {
            "titulo": "Página “Onde vender e divulgar” na área do aluno",
            "texto": "Lista curada dos servidores e comunidades onde mais se vende, mantida pelo "
            "editor de documentos. A Lívia dita a lista; a página nasce vazia de opinião e cheia de "
            "endereço.",
        },
    },
    26: {
        "familia": "praticar",
        "mesa": "site",
        "importa": "Material compartilhado acelera todo mundo e cria cultura de comunidade.",
        "precisa": "A biblioteca completa (envio de arquivo, filtros, moderação) é obra grande e "
        "carrega uma pergunta séria: quem garante que a textura enviada é de quem enviou. Degrau 1: "
        "espaço fixo no fórum, que já existe, e medir o uso. Degrau 2: a tela própria.",
        "tarefa": {
            "titulo": "Espaço de texturas no fórum (degrau 1 da biblioteca)",
            "texto": "Área fixa no fórum para a turma compartilhar texturas por categoria, com a "
            "regra de uso escrita. Se o uso crescer, vira tela própria com filtros.",
        },
    },
    31: {
        "familia": "cabelos",
        "mesa": "gravacao",
        "junta_com": (27, 42),
        "importa": "É o coração pedagógico do assunto mais pedido: quem domina a anatomia destrava "
        "qualquer estilo. E estilos étnicos são nicho com muita procura e pouca oferta boa.",
        "precisa": "Uma aula de fundamento (a anatomia específica do Roblox) e uma série curta de "
        "estilos. As ideias 27 e 42 são o mesmo pacote.",
        "tarefa": {
            "titulo": "Pacote de cabelos: anatomia do Roblox e estilos variados",
            "texto": "Aula 1: a anatomia de cabelo específica do Roblox (proporção, encaixe, malha), "
            "que é diferente da real. Depois, a série de estilos: base internacional (ideia 27), "
            "cacheados (ideia 42), dreads, afro e versão leve. É a família mais votada da Caixa.",
        },
    },
    37: {
        "familia": "reta-final",
        "mesa": "gravacao",
        "importa": "Quem escreveu entendeu os pilares e sente falta da costura. É a aula que "
        "transforma “sei as partes” em “sei o ofício”.",
        "precisa": "Gravar uma sessão real, com poucos cortes: pedido do cliente, modelagem, textura, "
        "publicação, entrega. Bônus: essa gravação vira a primeira simulação de encomenda.",
        "tarefa": {
            "titulo": "Aula de fluxo de trabalho completo, do pedido à entrega",
            "texto": "Mais de uma hora, poucos cortes, um trabalho de verdade do começo ao fim. Vai "
            "para a parte de bônus e serve depois como o primeiro “projeto de exemplo” das "
            "simulações de encomenda.",
        },
    },
    35: {
        "familia": "avisos",
        "mesa": "site",
        "ja_existe": True,
        "importa": "Dor de comunicação que só cresce com a turma. E há uma boa notícia que o aluno "
        "não sabe: a central de avisos já existe, e o aplicativo já avisa no celular.",
        "precisa": "Quase nada de obra: a rotina de publicar na central tudo que hoje vai só para o "
        "WhatsApp, e contar isso à turma. Se faltar uma tela cômoda de publicar, é obra pequena.",
        "tarefa": {
            "titulo": "Rotina de avisos na central que já existe",
            "texto": "Todo aviso importante do grupo passa a ser publicado também na central de "
            "avisos da plataforma (o aplicativo já notifica no celular). Conferir se a tela de "
            "publicar é cômoda o bastante; se não for, é obra pequena.",
        },
    },
    29: {
        "familia": "reta-final",
        "mesa": "site",
        "importa": "Descreve o aluno adulto típico da escola. Uma trilha mínima clara reduz a "
        "desistência de quem só tem cinco horas por semana.",
        "precisa": "Curadoria, não aula nova: desenhar a trilha (com pouco tempo, faça estas aulas "
        "nesta ordem e foque em duas categorias) e publicá-la como página na área do aluno.",
        "tarefa": {
            "titulo": "A trilha do primeiro dólar, para quem tem pouco tempo",
            "texto": "Roteiro oficial: quais aulas fazer, em que ordem, e em quais duas categorias "
            "focar para começar a vender antes de terminar o curso inteiro. Sai como página na área "
            "do aluno.",
        },
    },
    32: {
        "familia": "praticar",
        "mesa": "site",
        "importa": "Vitrine e reconhecimento alimentam motivação, e ainda geram material de "
        "divulgação para a escola mostrar o que os alunos produzem.",
        "precisa": "Degrau 1: área “Criações do mês” no fórum, com destaque escolhido pela "
        "equipe. Degrau 2: vitrine na plataforma. Degrau 3: votação, quando as medalhas ligarem.",
        "tarefa": {
            "titulo": "Criações do mês no fórum (degrau 1 da vitrine)",
            "texto": "Área no fórum onde a turma posta criações e a equipe destaca as melhores do "
            "mês. Se o hábito pegar, vira vitrine na plataforma e depois competição.",
        },
    },
    39: {
        "familia": "acabamento",
        "mesa": "gravacao",
        "importa": "Velocidade é dinheiro para quem vive de encomenda: o mesmo mês passa a caber mais "
        "entregas.",
        "precisa": "Uma aula “caixa de ferramentas”: complementos gratuitos e confiáveis, "
        "mais os ajustes prontos da própria Lívia para baixar. Atenção à licença do que for indicado.",
        "tarefa": {
            "titulo": "Aula de complementos e automação no Blender",
            "texto": "Complementos gratuitos e confiáveis que automatizam o repetitivo (abrir a malha "
            "para pintura, reduzir peso), mais os ajustes prontos da Lívia para baixar. Conferir a "
            "licença de cada complemento indicado.",
        },
    },
    33: {
        "familia": "praticar",
        "mesa": "site",
        "ja_existe": True,
        "em_obra": True,
        "junta_com": (24, 28),
        "importa": "Prática guiada é o que transforma aula assistida em habilidade. E o comentário "
        "reforça o padrão do quadro: o que existe nem sempre é encontrado.",
        "precisa": "Conferir o “já tem” e responder mostrando o caminho. No fundo, a área de "
        "cursos que está nascendo institucionaliza isto: exercício com entrega por link e resposta em "
        "24 horas.",
    },
    38: {
        "familia": "primeiro-cliente",
        "mesa": "site",
        "em_obra": True,
        "junta_com": (36,),
        "importa": "Nomeia com precisão a trava emocional da travessia para o mercado: aprendi, mas "
        "não sei se estou pronto para cobrar.",
        "precisa": "É a metade “projetos de exemplo” da ideia 36. As simulações podem nascer "
        "como exercícios avaliados da área de cursos e crescer para o mural de encomendas.",
    },
    42: {
        "familia": "cabelos",
        "mesa": "gravacao",
        "junta_com": (31,),
        "importa": "Detalha, com precisão de execução, o pedido de estilos da ideia 31. Público "
        "enorme e pouca referência boa disponível.",
        "precisa": "Entra na série de estilos do pacote de cabelos, do volume e do esboço até os "
        "cachos e a finalização.",
    },
    44: {
        "familia": "acabamento",
        "mesa": "gravacao",
        "importa": "Modelo pesado é reprovado na plataforma ou vende mal. É o conhecimento que separa "
        "o amador do profissional.",
        "precisa": "Gravação com um caso real: o mesmo modelo antes e depois, mostrando onde cortar "
        "polígonos, que detalhe vira textura e os limites do Roblox.",
        "tarefa": {
            "titulo": "Aula de otimização de modelos para o Roblox",
            "texto": "O mesmo modelo antes e depois: redução de polígonos, topologia, detalhe que "
            "vira textura e os limites da plataforma. Fecha o módulo de texturização e acabamento.",
        },
    },
    27: {
        "familia": "cabelos",
        "mesa": "gravacao",
        "junta_com": (31,),
        "importa": "É a técnica de fundação dos estilos mais pedidos: sem a base, tranças e dreads "
        "não saem.",
        "precisa": "Vira a primeira aula prática do pacote de estilos da ideia 31.",
    },
    30: {
        "familia": "novos-itens",
        "mesa": "gravacao",
        "junta_com": (45,),
        "importa": "Abre uma categoria nova de produto (avatares completos), que costuma ter preço "
        "maior por peça.",
        "precisa": "Gravação de escopo maior que a de um acessório. Anda junto com a ideia 45, no "
        "pacote de corpos e avatares, depois dos pacotes mais votados.",
        "tarefa": {
            "titulo": "Pacote de corpos e avatares completos",
            "texto": "Criar corpos inteiros e avatares personalizados, incluindo o estilo leve e de "
            "memes que os clientes pedem (ideia 45). Entra depois dos pacotes de cabelos e "
            "texturização.",
        },
    },
    40: {
        "familia": "acabamento",
        "mesa": "gravacao",
        "junta_com": (41,),
        "importa": "O acabamento é o que precifica o trabalho, e essa dor aparece cinco vezes no "
        "quadro em formas diferentes. Poucos votos aqui, muitos votos no conjunto.",
        "precisa": "Gravar o módulo já na versão atual do Blender (junto com a ideia 41), fechando "
        "com a otimização e o diagnóstico de erros.",
        "tarefa": {
            "titulo": "Módulo de texturização e pintura, do básico ao avançado",
            "texto": "Desde colocar imagem na malha até as técnicas de pintura que deixam o modelo "
            "atrativo. Gravado na versão ATUAL do Blender, cobrindo o que mudou de lugar desde as "
            "aulas antigas (ideia 41). Fecha com otimização (44) e diagnóstico de erros (23).",
        },
    },
    43: {
        "familia": "fora-do-trilho",
        "mesa": "voce",
        "importa": "Interesse legítimo, mas é outra profissão, com outro programa de ensino. Hoje a "
        "escola é de modelagem e venda de itens.",
        "precisa": "Decisão de rumo, não tarefa: registrar como possível curso futuro e responder com "
        "honestidade. Misturar agora dispersaria a agenda das famílias mais votadas.",
    },
    24: {
        "familia": "praticar",
        "mesa": "site",
        "em_obra": True,
        "junta_com": (33,),
        "importa": "Mesma família da 33. E “missão” é justamente o vocabulário da economia "
        "de pontos que já existe desligada: as peças se encaixam sozinhas.",
        "precisa": "Vira o nível avançado dos exercícios da área de cursos.",
    },
    28: {
        "familia": "reta-final",
        "mesa": "site",
        "junta_com": (33,),
        "importa": "Poucos votos, mas das mais baratas de atender, e o momento é perfeito: a área de "
        "cursos está nascendo agora. Nascer com o mapa de dependências custa pouco; encaixar depois "
        "custa caro.",
        "precisa": "Cada exercício aponta de quais aulas depende. Requisito de nascimento da área de "
        "cursos, não remendo posterior.",
        "tarefa": {
            "titulo": "Cada exercício diz de quais aulas depende",
            "texto": "Na área de cursos que está nascendo: o exercício X declara as aulas que ele "
            "pede, para quem tem pouco tempo rever só o necessário. Entra como requisito de "
            "nascimento, junto com a busca de aulas.",
        },
    },
    41: {
        "familia": "acabamento",
        "mesa": "gravacao",
        "junta_com": (40,),
        "importa": "É um aviso de manutenção que vale ouro: o programa evolui e as aulas envelhecem "
        "em silêncio, gerando dúvida que ninguém reporta.",
        "precisa": "Gravação curta de atualização, mais uma nota nas aulas antigas dizendo o que "
        "mudou de lugar. E fica a lição de processo: revisar as aulas a cada versão grande do Blender.",
    },
    45: {
        "familia": "novos-itens",
        "mesa": "gravacao",
        "junta_com": (30,),
        "importa": "O zero de votos é idade, não desinteresse: nasceu ontem. Aponta demanda real de "
        "encomenda que já chega aos alunos.",
        "precisa": "Entra no pacote de corpos e avatares da ideia 30.",
    },
    46: {
        "familia": "manutencao",
        "mesa": "gravacao",
        "importa": "O relato mais urgente do quadro, e sem voto nenhum porque nasceu agora: um ponto "
        "específico de uma aula existente causando desistência AGORA, em alunos que já pagaram. "
        "Nenhuma ideia nova vale mais do que estancar essa perda.",
        "precisa": "Gravação curta e cirúrgica: só a anatomia da cabeça, boca e olhos, anexada à aula "
        "que existe. Custo mínimo, efeito imediato.",
        "tarefa": {
            "titulo": "Vídeo curto: a cabeça do animal, boca e olhos, com calma",
            "texto": "Reforço da parte que passa rápido na aula do animal detalhado. A aluna relata "
            "colegas desistindo de fazer o animal por não conseguir fechar a boca. Vídeo curto, "
            "anexado à aula existente. Fura a fila: está custando aluno agora.",
        },
    },
}

# ---------------------------------------------------------------------------
# As fusões propostas — 13 ideias que são, na prática, 5 trabalhos
# ---------------------------------------------------------------------------
#
# A Caixa ainda não tem o gesto de juntar de verdade (mover votos e comentários
# é operação inteira, e o `<select>` da equipe não oferece "mesclado" de
# propósito, para a lista de mescladas não nascer mentindo). Enquanto ele não
# existe, a fusão é uma RECOMENDAÇÃO de leitura, e a tela diz isso.
FUSOES = (
    (
        (36, 25, 38),
        "Oportunidades por nível: simulações e trabalhos reais",
        "Os próprios autores pediram a fusão nos comentários.",
    ),
    (
        (31, 27, 42),
        "Cabelos além do básico: anatomia e estilos",
        "Uma anatomia e uma série de estilos, gravadas de uma vez.",
    ),
    (
        (40, 41),
        "Módulo de texturização no Blender atual",
        "Gravar duas vezes o mesmo assunto seria desperdício de estúdio.",
    ),
    (
        (33, 24, 28),
        "Exercícios por aula, com pré-requisitos",
        "As três descrevem o mesmo sistema da área de cursos.",
    ),
    (
        (30, 45),
        "Corpos e avatares completos",
        "Mesmo pacote de gravação, dificuldade parecida.",
    ),
)


# ---------------------------------------------------------------------------
# O cálculo
# ---------------------------------------------------------------------------


def _juntar(ideias: list) -> list:
    """Cada ideia viva, com o julgamento colado quando existir.

    O laço é sobre o que a CAIXA respondeu. Ideia sem entrada em `ANALISE`
    (escrita depois desta leitura) vem com `analisada = False` e a tela a
    separa; entrada sem ideia viva (arquivada, apagada) não desenha nada.
    """
    for ideia in ideias:
        escrito = ANALISE.get(ideia["id"]) or {}
        ideia["analisada"] = bool(escrito)
        ideia["etapa"] = _etapa_de(ideia)
        ideia["criada"] = _data_curta(ideia.get("criada_em", ""))
        ideia["importa"] = escrito.get("importa", "")
        ideia["precisa"] = escrito.get("precisa", "")
        ideia["junta_com"] = escrito.get("junta_com", ())
        ideia["ja_existe"] = escrito.get("ja_existe", False)
        ideia["em_obra"] = escrito.get("em_obra", False)
        ideia["tarefa"] = escrito.get("tarefa")
        ideia["familia"] = escrito.get("familia", "")
        mesa = escrito.get("mesa", "")
        ideia["mesa"] = mesa
        ideia["mesa_rotulo"], ideia["mesa_explicacao"] = MESAS.get(mesa, ("", ""))
    return ideias


def _por_votos(ideias: list) -> list:
    """A ordem da tela, e a mesma da exportação: mais votada primeiro.

    Desempate por plateia e depois por id, porque duas ideias empatadas em voto
    precisam de uma ordem ESTÁVEL — sem isso a página troca de ordem sozinha
    entre duas aberturas e quem lê acha que perdeu alguma coisa.
    """
    return sorted(ideias, key=lambda i: (-i["votos"], -i["pessoas"], i["id"]))


def _numerar(ordenadas: list) -> list:
    """A posição no quadro e o tamanho da barra — as duas contadas sobre TODAS.

    A posição é calculada aqui, e não com o contador do laço do template, porque
    a tela mostra as ideias em duas listas (as lidas e as que chegaram depois) e
    um contador por lista daria dois "número 1" na mesma página.
    """
    mais_votada = ordenadas[0]["votos"] if ordenadas else 0
    for posicao, ideia in enumerate(ordenadas, start=1):
        ideia["posicao"] = posicao
        # Em passos de 5 porque a largura vira CLASSE no template, e não
        # atributo `style` (a política da porta descarta atributo de estilo
        # sem avisar). 21 classes cobrem a escala inteira.
        crua = 100 * ideia["votos"] / mais_votada if mais_votada else 0
        ideia["largura"] = 5 * round(crua / 5)
    return ordenadas


def _familias(ideias: list) -> list:
    """As famílias com os votos SOMADOS do que está vivo agora."""
    quadro = []
    for chave, nome, situacao in FAMILIAS:
        membros = _por_votos([i for i in ideias if i["familia"] == chave])
        if not membros:
            continue
        quadro.append(
            {
                "chave": chave,
                "nome": nome,
                "situacao": situacao,
                "membros": membros,
                "votos": sum(i["votos"] for i in membros),
                "total": len(membros),
            }
        )
    return sorted(quadro, key=lambda f: -f["votos"])


def _mesas(ideias: list) -> list:
    """Quanto de voto espera por cada mesa. É o número que decide onde o esforço rende."""
    quadro = []
    for chave, (rotulo, explicacao) in MESAS.items():
        na_mesa = [i for i in ideias if i["mesa"] == chave]
        if not na_mesa:
            continue
        quadro.append(
            {
                "chave": chave,
                "rotulo": rotulo,
                "explicacao": explicacao,
                "total": len(na_mesa),
                "votos": sum(i["votos"] for i in na_mesa),
            }
        )
    return sorted(quadro, key=lambda m: -m["votos"])


def _percentagem(parte: int, todo: int) -> int:
    return round(100 * parte / todo) if todo else 0


def _padroes(ideias: list, mesas: list, familias: list) -> list:
    """Os padrões, com todo número CALCULADO na hora.

    Escrever "72% dos votos" na prosa seria um fato guardado num segundo lugar,
    e ele começaria a mentir no primeiro voto novo. Aqui a frase é um molde e o
    número vem da mesma conta que desenha o resto da tela.
    """
    votos = sum(i["votos"] for i in ideias)
    analisadas = [i for i in ideias if i["analisada"]]
    gravacao = next((m for m in mesas if m["chave"] == "gravacao"), None)
    maior = familias[0] if familias else None
    obra = [i for i in analisadas if i["em_obra"]]
    ja_existe = [i for i in analisadas if i["ja_existe"]]
    assinar = [i for i in ideias if i["coluna"] == "assinar"]
    sem_avaliacao = [i for i in ideias if not i.get("tem_avaliacao")]

    padroes = []

    if gravacao:
        padroes.append(
            (
                "A turma pede mais aula do que site",
                f"{gravacao['total']} das {len(ideias)} ideias do quadro esperam a Lívia gravar, e "
                f"elas concentram {gravacao['votos']} dos {votos} votos "
                f"({_percentagem(gravacao['votos'], votos)}%). Isso muda onde o esforço rende: uma "
                "tarde de estúdio atende hoje mais gente do que uma semana de código.",
            )
        )

    if maior:
        padroes.append(
            (
                f"{maior['nome']} é o assunto âncora",
                f"{maior['total']} ideias e {maior['votos']} votos somados, "
                f"{_percentagem(maior['votos'], votos)}% do quadro inteiro. É nicho com procura alta "
                "e oferta fraca de referência, ou seja, diferencial de venda real para o aluno.",
            )
        )

    if obra:
        padroes.append(
            (
                "Os alunos desenharam o produto que já está em obra",
                f"{len(obra)} ideias, com {sum(i['votos'] for i in obra)} votos somados, descrevem "
                "encomendas liberadas por nível, simulações avaliadas e selo de reputação: em "
                "detalhe, o mural de encomendas em construção mais a economia de pontos pronta e "
                "desligada. Ninguém contou isso a eles, e é a melhor validação de rumo que a escola "
                "já recebeu.",
            )
        )

    padroes.append(
        (
            "O fio que costura quase tudo: o medo da travessia",
            "Portfólio, simulador, trilha para quem tem pouco tempo, oportunidades por nível: são "
            "formas do mesmo sentimento, aprendi mas não sei se estou pronto para cobrar. A escola "
            "que resolver a travessia do aprender para o vender entrega o que promete no nome.",
        )
    )

    if ja_existe:
        padroes.append(
            (
                "O conteúdo existe, o aluno não acha",
                f"Em {len(ja_existe)} ideias, um comentário da própria turma afirma que aquilo já "
                "existe. Cada caso se cura com uma resposta e um link; a classe inteira se cura com "
                "busca e índice de aulas na área de cursos. Conteúdo que não é encontrado não existe "
                "para quem paga.",
            )
        )

    padroes.append(
        (
            "Voto cru engana: as ideias têm idades diferentes",
            "Uma ideia de cinco dias atrás teve cinco dias para juntar voto; a de ontem teve horas. "
            "A régua justa combina votos, plateia e idade, e o caso extremo está no quadro: a ideia "
            "sobre a cabeça do animal tem zero voto e é o relato mais urgente que a turma escreveu.",
        )
    )

    if sem_avaliacao:
        padroes.append(
            (
                "A Caixa coleta muito bem, e ainda não respondeu",
                f"{len(sem_avaliacao)} das {len(ideias)} ideias não têm uma linha de avaliação escrita "
                + (
                    f", e {len(assinar)} esperam a sua assinatura. "
                    if assinar
                    else ". "
                )
                + "A coleta provou que funciona; o que sustenta o fluxo agora é a resposta. Turma que "
                "vê ideia virar obra continua escrevendo.",
            )
        )

    return [{"titulo": t, "texto": x} for t, x in padroes]


def _fusoes(ideias: list, caixa: CaixaClient) -> list:
    """As fusões propostas, com a PRÉVIA de cada uma vinda da Caixa.

    A prévia não é enfeite do modal: ela é a única fonte que sabe quantas
    pessoas votaram em mais de uma das ideias. Deste lado só existe a contagem
    por ideia, e somá-la prometeria uma popularidade que a junção não entrega.

    Uma chamada só para todos os grupos. Se ela não responder, as fusões
    continuam aparecendo como leitura (é análise, e vale sem o botão), mas sem
    o gesto de juntar: confirmar uma junção sem ver o resultado é exatamente o
    que o modal existe para evitar.
    """
    vivas = {i["id"]: i for i in ideias}
    propostas = []
    for ids, nome, motivo in FUSOES:
        membros = [vivas[i] for i in ids if i in vivas]
        if len(membros) < 2:
            continue
        canonica, *absorvidas = membros
        propostas.append(
            {
                "membros": membros,
                "canonica": canonica,
                "absorvidas": absorvidas,
                "nome": nome,
                "motivo": motivo,
                "votos": sum(i["votos"] for i in membros),
                "absorvidas_ids": ",".join(str(i["id"]) for i in absorvidas),
                "previa": None,
            }
        )

    previas = caixa.previas_de_fusao(
        [
            {
                "canonica": p["canonica"]["id"],
                "absorvidas": [i["id"] for i in p["absorvidas"]],
            }
            for p in propostas
        ]
    )
    if previas and len(previas) == len(propostas):
        for proposta, previa in zip(propostas, previas):
            proposta["previa"] = previa
    return propostas


def _de_volta(desfecho: str, recado: str):
    """Volta para a análise dizendo o que aconteceu.

    Redirecionar depois do POST é o que impede o F5 de repetir a junção — e
    repetir uma junção é diferente de repetir um clique inofensivo.
    """
    campo = "recado" if desfecho == CaixaClient.OK else "erro"
    return HttpResponseRedirect(
        f"{reverse('caixa_analise')}?{urlencode({campo: recado})}#juncoes"
    )


@require_POST
def fundir(request):
    """A confirmação: o mantenedor viu a prévia no modal e apertou o botão."""
    try:
        canonica = int(request.POST.get("canonica") or 0)
        absorvidas = [
            int(i) for i in (request.POST.get("absorvidas") or "").split(",") if i
        ]
    except ValueError:
        return _de_volta(CaixaClient.RECUSADO, "Não entendi quais ideias juntar.")
    if not canonica or not absorvidas:
        return _de_volta(CaixaClient.RECUSADO, "Escolha as ideias antes de juntar.")

    desfecho, recado = CaixaClient().fundir(
        canonica=canonica,
        absorvidas=absorvidas,
        nota=(request.POST.get("nota") or "").strip(),
        quem=_quem(request),
    )
    _auditar(
        request,
        Registro.FUNDIR_IDEIAS,
        f"ideia:{canonica}<-{'+'.join(str(i) for i in absorvidas)}",
        {
            CaixaClient.OK: Registro.OK,
            CaixaClient.RECUSADO: Registro.RECUSADO_PELA_CELULA,
        }.get(desfecho, Registro.NAO_RESPONDEU),
        detalhe=recado,
    )
    return _de_volta(
        desfecho,
        (
            "Pronto: as ideias viraram uma só, e todo mundo que estava atrás "
            "delas foi avisado. Dá para desfazer aqui embaixo."
            if desfecho == CaixaClient.OK
            else recado
        ),
    )


@require_POST
def desfazer_fusao(request, fusao_id: int):
    desfecho, recado = CaixaClient().desfazer_fusao(fusao_id, quem=_quem(request))
    _auditar(
        request,
        Registro.DESFAZER_FUSAO,
        f"fusao:{fusao_id}",
        {
            CaixaClient.OK: Registro.OK,
            CaixaClient.RECUSADO: Registro.RECUSADO_PELA_CELULA,
        }.get(desfecho, Registro.NAO_RESPONDEU),
        detalhe=recado,
    )
    return _de_volta(
        desfecho,
        (
            "Desfeito: cada ideia voltou a andar sozinha, com os votos e "
            "comentários que tinha antes."
            if desfecho == CaixaClient.OK
            else recado
        ),
    )


@require_GET
def analise(request):
    caixa = CaixaClient()
    quadro = caixa.ideias(por_email=_email(request), com_conversa=True)
    if quadro is None:
        return render(request, "admin/caixa_analise.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _juntar(_enriquecer(quadro["ideias"], agora))
    ordenadas = _numerar(_por_votos(ideias))
    familias = _familias(ideias)
    mesas = _mesas(ideias)

    return render(
        request,
        "admin/caixa_analise.html",
        {
            "quadro": quadro["quadro"],
            "ideias": [i for i in ordenadas if i["analisada"]],
            "sem_analise": [i for i in ordenadas if not i["analisada"]],
            # A lista inteira serve a UM laço só: o dos modais. Desenhar o modal
            # dentro de cada uma das duas listas de cima duplicaria o mesmo
            # bloco de marcação, e duas cópias derivam.
            "todas": ordenadas,
            "total": len(ideias),
            "votos": sum(i["votos"] for i in ideias),
            "familias": familias,
            "mesas": mesas,
            "fusoes": _fusoes(ideias, caixa),
            "juncoes_feitas": caixa.fusoes(),
            "recado": request.GET.get("recado", ""),
            "erro": request.GET.get("erro", ""),
            "padroes": _padroes(ideias, mesas, familias),
            "esperando_assinatura": [i for i in ordenadas if i["coluna"] == "assinar"],
            "gerada_em": agora,
            "na_mesa": len(esperando(ideias)),
        },
    )
