(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-067-a-pista-de-pouso-precisa-de-uma-chave-sua",
  tipo: "pendencia",
  quando: "2026-08-28",
  titulo: "A pista de pouso está travada numa chave que só você pode criar — são 3 minutos no navegador",
  detalhe: "Você escolheu ir para a Onda 4, a pista de pouso — a peça que acaba com o trabalho repetido de atualizar e tentar de novo. Comecei, e esbarrei num limite do GitHub que muda o desenho e que eu não posso resolver sozinho.\n\nO problema, em linguagem simples: a pista precisa aprovar entregas em seu nome. Mas o GitHub tem uma regra de segurança — quando um programa automático aprova algo usando a chave padrão que ele já tem, o GitHub NÃO considera isso um acontecimento novo. Consequência: a publicação no servidor nunca seria disparada. A plataforma pararia de se atualizar em silêncio, e ninguém perceberia até alguém abrir o site e ver conteúdo velho.\n\nIsso não é opinião minha: está escrito na documentação oficial do GitHub, e duas das cinco IAs consultadas tinham avisado. Conferi antes de construir, porque construir primeiro e descobrir depois seria caro.\n\nO caminho oficial é dar à pista uma chave própria, criada por você — é um item de segurança da sua conta, e por isso nenhum robô pode criar no seu lugar. São três minutos no navegador, e eu te dou o passo a passo com um comando único de colar para guardar a chave.\n\nEnquanto isso não acontece, entreguei o que não depende dela: o portão parou de dizer verde e falhar em seguida (registro anterior). O trabalho repetido continua até a pista existir, mas pelo menos deixou de confundir.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/421. Documentacao oficial do GitHub (docs.github.com, 'Triggering a workflow'): 'Events triggered by the GITHUB_TOKEN will not create a new workflow run', com excecao apenas de workflow_dispatch e repository_dispatch. E o .github/workflows/deploy-celula.yml recusa workflow_dispatch por decisao escrita no proprio arquivo ('SEM workflow_dispatch, de proposito: deploy que ninguem amarra a commit revisado nao existe aqui'). Logo, pista que mergeia com o token padrao => deploy nunca dispara.",
  verificado_em: "2026-08-28",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: "A Onda 4 fica parada, e o trabalho repetido continua: hoje uma entrega de 4 arquivos e nenhuma linha de código precisou de cinco rodadas para entrar, porque a versão oficial anda cerca de 98 vezes por dia e cada tentativa gasta 90 segundos de teste. Não quebra nada — só desperdiça tempo de robô e sua franquia.",
  recomendacao: "Criar a chave quando você tiver 3 minutos. Eu te mando o passo a passo com as telas e um comando único de colar no fim. Se preferir não criar, existe o caminho de desligar a trava estrita até a pista existir — mas aí volta o risco de duas entregas certas quebrarem o sistema juntas, que foi o pior acidente já medido aqui.",
  reversivel: true,
  impacto: "medio"
});})();
