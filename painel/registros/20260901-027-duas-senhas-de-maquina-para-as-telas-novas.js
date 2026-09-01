(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-027-duas-senhas-de-maquina-para-as-telas-novas",
  tipo: "pendencia",
  quando: "2026-09-01",
  titulo: "Duas senhas de maquina, para a etiqueta do forum e o quadrinho da home acenderem",
  detalhe: "As duas telas que o Lote A entregou estao no ar e nao mostram nada, porque falta ligar a conversa entre as celulas. Uma senha de maquina e a credencial que uma parte do site usa para perguntar algo a outra, e credencial nunca viaja pela esteira automatica: e passo do mantenedor, por lei (Lei 5, INV-P8), e por isso os robos escreveram os dois scripts em vez de rodar por conta propria.\n\nSao duas linhas para colar DENTRO da VPS (o prompt comeca com deploy@srv ou root@srv), uma para cada par:\n\ninfra/provisionar-par-do-forum-com-a-gamificacao.sh liga o par forum para gamificacao.\ninfra/provisionar-par-do-funil-com-a-gamificacao.sh liga o par funil para gamificacao.\n\nOs dois foram escritos no molde do provisionar-par-da-economia.sh, que ja rodou aqui e deu certo: recusam ser carregados com source, param com PAROU POR SEGURANCA se algo estiver estranho, geram o segredo dentro da propria VPS sem nunca imprimi-lo, guardam copia de seguranca de cada arquivo antes de escrever, e sao idempotentes: rodar de novo reusa o token existente em vez de troca-lo, entao repetir e seguro. O do forum foi exercitado contra uma VPS simulada antes de entrar, inclusive as quatro recusas de seguranca.\n\nSE NADA FOR RODADO: as paginas do forum e a home abrem exatamente como hoje, sem etiqueta e sem quadrinho, e nada quebra. Nao ha urgencia tecnica; ha so uma entrega que fica invisivel.\n\nE vale lembrar o segundo degrau: mesmo com as duas senhas ligadas, nada aparece enquanto a economia continuar desligada, porque nenhum aluno tem ponto nenhum. Ligar as regras e decisao do mantenedor, na tela dele em /admin/economia/, e esta registrada em separado.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/828",
  verificado_em: "2026-09-01",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: "As duas telas novas continuam no ar sem mostrar nada. Nada quebra e nada se perde, mas o trabalho do Lote A fica invisivel para os alunos ate as duas linhas serem rodadas.",
  recomendacao: "Rodar as duas linhas na mesma sessao da VPS, uma depois da outra. Sao trinta segundos cada, sao seguras de repetir, e junta-las evita que uma fique para tras e vire duvida depois.",
  reversivel: true,
  impacto: "medio"
});})();
