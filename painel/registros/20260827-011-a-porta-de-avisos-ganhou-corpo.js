(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-011-a-porta-de-avisos-ganhou-corpo",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A porta de consulta da caixa central de avisos já responde de verdade",
  detalhe: "Primeiro degrau do rumo registrado em 20260827-007. Até hoje de manhã a caixa central de avisos só sabia ouvir o fio e dizer 'estou bem' — agora ela responde às três perguntas que o Rito da Fase 4 desenhou: quantos avisos faltam ler, quais são eles, e marcar todos como lidos de uma vez. Já nasceu respeitando a decisão de escopar por site (registro 20260827-010).\n\nDOIS CUIDADOS QUE VALEM SER CONTADOS: (1) a contagem não lê a tabela inteira — ela lê um contador que já era mantido desde o nascimento da célula, então o custo não cresce com o tempo. (2) a lista de avisos junta o que está 'quente' com o que já foi arquivado (avisos lidos há mais de um mês saem do caminho rápido, mas continuam existindo) — sem isso, um aviso que a pessoa já leu sumiria da vida dela depois de um tempo, em vez de só sair da lista de 'não lidos'.\n\nUM TROPEÇO E UMA CORREÇÃO NO MEIO DO CAMINHO: a primeira versão do índice do banco apostou que a busca não precisaria separar por site (antes da decisão do registro 010). Em vez de confiar na aposta, medi de propósito com um cenário adversarial (uma pessoa com avisos espalhados por 5 sites) — e a aposta perdeu: sem o ajuste, o banco leria os avisos da pessoa em QUALQUER site antes de descartar os errados. Corrigido, medido de novo, e a prova ficou como teste permanente, para nenhuma sessão futura repetir o mesmo tropeço sem perceber.\n\nCONFERIDO DE FORA depois do deploy: o site inteiro continuou respondendo normalmente, e a porta nova está corretamente INVISÍVEL para qualquer um de fora — só as peças internas da plataforma conseguem falar com ela, como já era o desenho desde o nascimento da célula.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/280 — MERGED, commit c1ec86c; deploy-celula 33096408835 success; medido de fora depois: meshcraft.top, /healthz e /forms/sugestoes/healthz em 200, /notificacoes/healthz em 404 (sem porta pra rua, por desenho); 77 testes na célula, incluindo prova por EXPLAIN ANALYZE do plano de consulta",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
