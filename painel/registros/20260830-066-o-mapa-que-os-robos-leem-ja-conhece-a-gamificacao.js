(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-066-o-mapa-que-os-robos-leem-ja-conhece-a-gamificacao",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O mapa que todo robo novo le antes de trabalhar ja sabe que a gamificacao existe",
  detalhe: "Existe no projeto um mapa escrito para robo recem-chegado: quem chega sem saber nada le ele para entender como o site e feito por dentro antes de encostar em qualquer coisa. Ate hoje esse mapa nao sabia que a gamificacao existe. Agora sabe. Foi a primeira das tarefas que a sua aprovacao de hoje destravou.\n\nPOR QUE ISSO IMPORTA, NA PRATICA. Sem essa pagina no mapa, um robo trabalhando no forum amanha inventaria um sisteminha de pontos ali dentro, do zero, sem saber que ja existe uma parte do site sendo construida exatamente para cuidar disso. Seria trabalho jogado fora, e pior: a pontuacao do aluno ficaria espalhada em varios lugares que nao conversam, que e justamente a doenca que a parte nova existe para evitar.\n\nO QUE O MAPA PASSOU A DIZER. O que a parte nova faz; de onde ela tira os fatos (ela nao inventa nada: fica ouvindo o que as outras partes do site ja afirmam, como um quiz respondido ou uma resposta aceita no forum); o que ela devolve para as outras partes (o selo do aluno, entregue de um jeito que, se ela cair, a pagina so fica sem o selo, nunca quebra); e a lista do que ela NUNCA vai fazer. Essa ultima e a parte mais importante e esta escrita como tabela, uma linha por proibicao, com o motivo do lado: nada se compra com dinheiro real, enfeite e so enfeite, aula nunca fica trancada atras de ponto, sem placar publico global, e a conta nunca e feita dentro de outra parte do site.\n\nOS NOMES QUE VOCE ESCOLHEU FICARAM ONDE O PROXIMO ROBO LE. Bronze, Prata, Ouro e Platina; a Forja como medidor de esforco; a vitrine do aluno em meshcraft.top/estudio/apelido. O plano tecnico foi escrito ANTES da conversa de hoje e ainda usa um nome velho em um lugar ou outro; o mapa agora avisa, por escrito, qual dos dois vale.\n\nDE QUEBRA, CONSERTEI O QUE JA TINHA ENVELHECIDO. O mapa foi escrito em 27/08 e ainda descrevia o forum como obra mal comecada, quando ele esta no ar desde hoje de manha. A conta das partes do site tambem nao fechava: dizia 12 num lugar e 13 em outro, e uma soma dava 12 num projeto de 13. Refeito conferindo o disco, nao de cabeca. E deixei escrito no proprio mapa uma coisa que continua velha e que eu NAO consertei aqui, para ninguem descobrir pelo tranco: a contagem do catalogo de erros do projeto, que diz 126 e hoje sao 200.\n\nNada disso muda o que o aluno ve no site. E mapa interno, e ele evita retrabalho caro na obra que voce acabou de aprovar.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/626 (este PR). O teste-guarda do mapa passa: 'python -m pytest ci/tests/test_painel_ia_atualizado.py -q' devolve 2 passed. As correcoes de fato nao foram inferidas, foram medidas contra o disco no mesmo worktree: ci/manifesto-de-contratos.json (9 celulas required, 4 not-applicable), 'ls services/forum/apps' (core, forum), 'grep -c operationId contracts/forum.openapi.yaml' (3) e contracts/notificacoes.openapi.yaml (4), 'git ls-files services/' (13 celulas). Tarefa TAR-033 da fila, concluida com o comprovante fila/eventos/20260830-185348-TAR-033-concluida.json. Arquivos tocados: so painel/ia/04-arquitetura-de-celulas-e-contratos.md e painel/ia/INDICE.md. Nenhum caminho CODEOWNERS tocado.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
