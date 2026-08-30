(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-070-as-ferramentas-do-administrador-do-forum-estao-no-ar",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "As suas ferramentas do fórum estão NO AR, medidas de fora",
  detalhe: "O que entrou no PR 627 subiu para o site de verdade. Entrando no fórum com o seu e-mail, cada página passa a ter uma caixa dobrada chamada \"Ferramentas do administrador\", com os botões de editar, mover, fixar, trancar, tirar do ar, deixar privado e arquivar.\n\nMedido de fora, sem login: meshcraft.top/forum responde 200, a área de avisos responde 200, e a contagem de \"Ferramentas do administrador\" na página do visitante é ZERO. O estilo novo dos botões também já está servido pelo site.\n\nO caminho até aqui teve um tropeço que vale registrar, porque ele volta: a primeira entrega falhou nas três tentativas com \"dial tcp :22 i/o timeout\", que é o soluço de rede entre o robô do GitHub e a VPS (a armadilha 127), e não defeito do código. A reversão automática entrou sozinha e o fórum ficou no ar com a versão anterior o tempo todo, sem ninguém fora do ar. A repetição foi verde na segunda tentativa e a versão nova subiu.",
  autoridade: "github",
  evidencia: "run 33329992163 do deploy-celula, completed/success nas duas células (forum e admin), lido por gh run view --json status,conclusion — e a medição de fora: GET /forum/ 200, GET /forum/a/avisos 200 com zero ocorrências de 'Ferramentas do administrador', GET /forum/static/forum.css servindo as regras novas",
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
