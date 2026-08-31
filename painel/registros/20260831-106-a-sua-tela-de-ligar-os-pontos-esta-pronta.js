(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-106-a-sua-tela-de-ligar-os-pontos-esta-pronta",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A sua tela de ligar os pontos esta pronta",
  detalhe: "E a tela que voce pediu. Ela fica no seu painel, junto com as outras: 'Ligar os pontos da escola'. Cada linha e uma coisa que o aluno pode fazer, com quantos pontos vale e um botao de ligar ou desligar.\n\nO QUE ELA TE DIZ ANTES DE VOCE CLICAR, e essa parte eu so escrevi porque medi antes: uma regra pode estar ligada e mesmo assim nao fazer numero nenhum se mexer. Entao a tela avisa, em portugues, quando ligar nao vai adiantar ainda: 'nada no site avisa quando isso acontece', ou 'o aviso chega, mas sem dizer de quem e o ponto' (o caso do quiz). Sem esse aviso voce ligaria a primeira regra, o numero ficaria zero, e voce ia procurar defeito na tela.\n\nE ELA AVISA A ESPERA, que e a coisa mais confusa de todas: em algumas regras o ponto e creditado na hora mas so aparece no perfil 24 horas depois. Isso e de proposito, e a janela para desfazer se um conteudo for moderado. Sem a frase na tela, voce ligaria, faria a acao, nao veria nada mudar e concluiria que quebrou.\n\nOS CRISTAIS: a tela diz, na regra que promete Cristais, que os pontos saem e os Cristais NAO. Continua sendo decisao sua, e mexer nisso mexe na trava que garante que Cristal nao se compra.\n\nUM DETALHE QUE IMPORTA: esta tela nao guarda nada. Ela pergunta para a parte das conquistas e mostra o que voltou. Se guardasse uma copia, um dia as duas discordariam e a tela te mostraria uma coisa enquanto o sistema pagaria outra.\n\nCADA VEZ QUE VOCE LIGAR OU DESLIGAR, fica uma linha registrada dizendo que foi voce e quando. Junto com a data que a regra guarda do lado de la, isso e o 'anunciado' que a lei pede.\n\nFALTA UM PASSO SEU, e e uma linha so colada no servidor. Ele cria a senha que faz esta tela conversar com a parte das conquistas. Enquanto voce nao rodar, a tela ABRE e diz, em portugues, que ainda nao consegue falar com a parte das conquistas. Nada quebra e nada muda no site. Eu te mando o comando na conversa.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/780. 15 testes novos; suite da celula 535 -> 550 passed. Os guardas cobrem: a porta (sem cracha nada responde, e o gesto de ESCRITA nem chega a chamar a gamificacao), as tres traducoes para portugues, os tres avisos de impedimento, a frase da quarentena, o fail-open sem o par de tokens, os dois verbos de auditoria (ligar e desligar separados), a recusa virando frase e nao 500, e a tela mostrando o que esta GRAVADO depois de uma recusa. ci/mapa_de_celulas.py PASS (20 consumos declarados e medidos no codigo), ci/mapa_do_site.py PASS (135 rotas medidas, 135 declaradas, mesma lista), ci/travessao.py PASS, black limpo. Depende do #773 e do #776 (ambos mergeados) e do #777 (o par de tokens).",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "amarelo",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A tela fica no ar mas abre dizendo que ainda nao consegue falar com a parte das conquistas. Nada quebra e nada muda no site: a economia continua inteira desligada e nenhum aluno ganha nem perde ponto. So nao da para ligar a primeira regra.",
  recomendacao: "Rodar a linha do provisionamento dentro da VPS quando o PR 777 estiver no ar, e depois ligarmos a primeira regra juntos.",
  reversivel: true,
  impacto: "Sem o passo, a tela existe mas nao funciona. Com o passo, voce passa a poder ligar e desligar cada regra sozinho, sem depender de robo nenhum."
});})();
