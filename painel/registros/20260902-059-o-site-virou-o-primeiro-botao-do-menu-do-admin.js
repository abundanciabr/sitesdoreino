(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-059-o-site-virou-o-primeiro-botao-do-menu-do-admin",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O site virou o primeiro botão do menu da administração",
  detalhe: "Você pediu que o primeiro link do menu do admin fosse o do site, antes da Visão geral. Está feito: o menu agora começa em \"Ver o site\", e a Visão geral vem logo depois.\n\nUm tracinho fino separa o primeiro dos outros. É de propósito: ele é o único que te LEVA EMBORA da administração, e os outros andam por dentro dela. No celular o tracinho some, porque ali a quebra de linha já separa os grupos sozinha.\n\nO rodapé perdeu o \"Ver o site como um visitante\" que tinha. Com o link no topo de toda tela, ele no pé seriam duas portas para o mesmo lugar na mesma página, que é exatamente a repetição que você mandou tirar poucas horas antes. O rodapé continua com a biblioteca pública.\n\nUma coisa que quase deu errado, e vale contar porque é o tipo de defeito que ninguém veria: a regra que decide qual botão fica aceso dizia \"o primeiro da lista é a capa\". Enquanto a capa era mesmo a primeira, isso funcionava. No momento em que o site passou na frente dela, \"o primeiro\" e \"a capa\" deixaram de ser a mesma coisa, e a Visão geral teria parado de acender sem ninguém notar. A regra agora chama a capa pelo nome.\n\nE um teste meu estava mentindo. O guarda que eu escrevi para travar justamente esse ponto PASSOU quando eu injetei o defeito de propósito para conferir. Motivo: aquela regra é lida uma vez, quando o programa carrega, e nenhum teste consegue diferenciar as duas formas depois disso. Reescrevi o guarda para olhar o texto do arquivo, que é o que dá para medir de verdade, e deixei o porquê escrito nele. Um teste que dá sensação de proteção sem proteger é pior do que não ter teste nenhum.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/895",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
