(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-023-mapa-do-site-no-admin",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O site inteiro cabe numa página: 97 endereços em /admin/mapa/",
  detalhe: "Você pediu um mapa completo do site no painel do admin. Ele está no ar em meshcraft.top/admin/mapa/, com um cartão novo na visão geral levando até lá.\n\nO que a página mostra: TODO endereço que o site tem hoje — 97 — agrupado por quem consegue abrir. 13 páginas para quem só visita, 5 para quem é aluno, 20 suas, e 33 portas que só as máquinas usam. Cada linha tem nome e explicação em português, e as que dá para abrir são links.\n\nDois números que a página explica e que ninguém sabia antes: 26 desses endereços NÃO são páginas, são o que acontece quando alguém aperta um botão (votar, liberar, salvar) — é isso que explica a diferença entre 97 endereços e 38 telas. E 11 deles a internet nem alcança: são conversas internas entre as partes do site.\n\nPor que dá para confiar nele: o mapa não é uma lista digitada à mão que alguém precisa lembrar de atualizar. O endereço de cada linha é conferido, a cada mudança, contra o roteamento de verdade e contra o código das 13 partes da plataforma. Um robô que criar uma página nova e não a escrever no mapa é REPROVADO antes de a mudança entrar, e o mesmo vale para uma linha que sobrar depois que uma página deixar de existir. Só o texto em português é humano; o resto é medido.\n\nA construção descobriu duas coisas que ninguém tinha olhado: /docs/ e /admin/docs/ são a mesma página servida em dois endereços (as duas respondem), e o endereço do quiz repete o prefixo (/quiz/quiz/...). O quiz não tem conteúdo publicado hoje, então não dá para dizer pela borda se foi intenção — ficou anotado no próprio mapa e em armadilhas/197, para quem publicar o primeiro quiz conferir.",
  autoridade: "github",
  evidencia: "Entregue no PR #576 (https://github.com/abundanciabr/sitesdoreino/pull/576). Prova vermelho->verde do varredor: com a página declarada no mapa e a rota ainda inexistente, `python ci/mapa_do_site.py --verificar` saiu 1 acusando \"FANTASMA no mapa: admin -> 'mapa/' nao existe no urls.py\"; depois de criar a rota, saiu 0 com \"97 rotas medidas, 97 declaradas, mesma lista\". Testes: 17 adversariais no cartógrafo (cada um sabotando o mapa de um jeito e exigindo vermelho), 8 na tela, 353 na célula admin inteira e 1078 na suíte do próprio CI — todos verdes.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
