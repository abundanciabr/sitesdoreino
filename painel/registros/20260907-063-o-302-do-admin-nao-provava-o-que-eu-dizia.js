(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-063-o-302-do-admin-nao-provava-o-que-eu-dizia",
  tipo: "nota",
  quando: "2026-09-07",
  titulo: "A prova de fora que os robos vinham escrevendo nao provava que a tela existe",
  detalhe: "Quando um robo entrega uma tela da sua area administrativa, ele escreve no livro uma prova assim: 'de fora, o endereco responde 302 para o login, o cracha vem antes da tela'. Hoje eu fiz o teste que ninguem tinha feito: inventei um endereco que NAO existe e ele respondeu 302 igual.\n\nO motivo: a porta do admin roda ANTES do site perguntar se aquele endereco existe. Ela manda todo mundo sem cracha para o login, exista a pagina ou nao. O desenho esta certo e e seguro; a frase do robo e que dizia mais do que media.\n\nSao 25 registros do livro com essa frase. Nenhum mentiu sobre o deploy, e nenhuma tela esta quebrada por causa disso: o que falta e a ultima prova, e ela e sua. Quem tem o cracha e voce.\n\nDaqui em diante a frase certa e 'a celula respondeu depois do deploy', e quem diz 'a tela abre' e voce, abrindo.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/1328 (armadilhas/390). Medido de duas formas independentes: o controle na internet publica (/admin/placar/fechamento/ -> 302, /admin/placar/rota-que-nao-existe-abc123/ -> 302, /admin/placar/ -> 302) e o codigo (PortaAdministrativa esta na lista MIDDLEWARE de services/admin/config/settings.py, e middleware roda antes da resolucao de URL).",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica"
}); })();
