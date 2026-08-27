(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo",
  tipo: "rumo",
  quando: "2026-08-27",
  titulo: "Próximo na comunidade: a porta de avisos ganha corpo, e depois os dois consumidores — a tela da Caixa e o sino do site",
  detalhe: "Com a Fase 4 fechada (registro 20260827-006), sobram três passos até o sininho estar de verdade ao lado do seu nome em qualquer página. Todos são trabalho de robô — nenhum pede você.\n\n1) A PORTA GANHA CORPO. Hoje a caixa central de avisos (`notificacoes`) só ouve o fio e responde 'estou bem' — o desenho das três rotas (contagem, lista, marcar como lido) já é lei, mas nenhuma delas responde nada ainda. Este passo constrói as três dentro da célula.\n\n2) OS DOIS CONSUMIDORES, em paralelo (células diferentes, sem depender um do outro): a tela de avisos da Caixa passa a consultar a porta nova em vez da tabela local; e o sino aparece ao lado do seu nome em qualquer página do site, escondendo-se sozinho se a caixa de avisos estiver fora do ar.\n\n3) FECHAMENTO: testes de volume (a mesma disciplina de sempre — o custo não pode crescer com a plateia), auditoria batendo o documento contra o código (do jeito que fechamos o plano da própria Caixa), e prova medida de fora — o sino aparecendo de verdade num navegador, a contagem batendo com a tela de avisos.\n\nUM DETALHE JÁ ESCRITO NO PLANO PARA QUEM CONSTRUIR O PASSO 2: os avisos antigos da Caixa (de antes de 26/08) foram copiados para a caixa central marcados como 'não lidos', porque não existia leitor nenhum quando chegaram lá. Antes de ligar o sino de vez, esse passo precisa marcar essas notificações como já lidas — senão todo mundo veria uma enchente de avisos de coisa que já leu há semanas. Já está escrito em docs/notificacoes/PLANO-MESTRE.md, Fase 5, para não virar surpresa.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com a porta de avisos da célula notificacoes'.",
  autoridade: "sessao",
  evidencia: "registro 20260827-006 (a conversa da Fase 4) + docs/notificacoes/PLANO-MESTRE.md §6 Fases 4 a 6; services/notificacoes/config/urls.py hoje só expõe /healthz (medido em 27/08/2026); ci/manifesto-de-contratos.json declara notificacoes como freeze:required sem o management command export_openapi ainda existir — o ci-celula dela nasce vermelho até o próximo lote, por desenho",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: 30
});})();
