(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-022-etiqueta-de-nivel-no-forum",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "O nivel do aluno agora aparece no forum, ao lado do nome de quem escreve",
  detalhe: "Ate hoje o progresso do aluno so existia para quem abrisse a pagina de conquistas de proposito. O forum e o lugar da escola com mais gente passando, e agora e ali que o nivel encontra quem nunca foi procura-lo: numa conversa, ao lado do nome de quem escreveu, aparece o degrau dele, por exemplo \"Nv 7 Artesao\".\n\nQuem ainda nao pontuou aparece exatamente como sempre, sem nada ao lado do nome. Isso e o normal por enquanto, porque a economia da escola continua desligada: ninguem ganha ponto ate voce ligar a primeira regra em /admin/economia/.\n\nA fala publicada em nome da escola nunca recebe etiqueta. A Meshcraft Academy nao e uma aluna, e estampar um nivel nela seria fingir que e.\n\nSE A PARTE DAS CONQUISTAS ESTIVER FORA DO AR, o forum abre igual: a etiqueta simplesmente nao aparece e nenhuma conversa deixa de abrir. Foi assim que a peca foi construida de proposito, e ha teste provando cada forma de isso dar errado.\n\nFALTA UM PASSO SEU, e ele e uma linha so dentro da VPS: o script infra/provisionar-par-do-forum-com-a-gamificacao.sh. Ele liga a senha de maquina entre as duas partes do site (senha nao pode viajar pela esteira automatica, por lei do projeto). Enquanto ele nao rodar, as paginas do forum abrem exatamente como abrem hoje, sem etiqueta nenhuma, e NADA quebra. A sessao que coordena o lote vai te entregar o bloco pronto para colar.\n\nA suite da celula forum foi de 218 para 239 testes, todos verdes, e cada guarda foi provado quebrando o codigo de proposito e vendo o teste ficar vermelho.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/828",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
