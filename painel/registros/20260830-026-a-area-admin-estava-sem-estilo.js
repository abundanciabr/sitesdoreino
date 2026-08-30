(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-026-a-area-admin-estava-sem-estilo",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A área administrativa estava chegando SEM ESTILO no seu navegador — e nada media isso",
  detalhe: "Achei isto por acidente, conferindo o mapa do site que acabei de entregar: as telas da administração estavam sendo servidas ao seu navegador com o desenho DESLIGADO. Texto puro, empilhado, sem cor e sem caixas.\n\nValia para quase tudo: a visão geral, a escola, os alunos, a Caixa, os documentos e o mapa novo. As duas exceções eram o painel do sistema (/admin/painel/) e a aba \"Os robôs\" — elas escapavam por acaso, porque mandam uma configuração própria de segurança por outro motivo.\n\nO que acontecia, sem jargão: o servidor mandava junto com cada página uma regra de segurança dizendo ao navegador \"só aceite folha de estilo que venha por link\". Só que o estilo desta área vem DENTRO da própria página (por um bom motivo, documentado). O navegador obedecia a regra e jogava o desenho fora. A página respondia certo, o servidor estava saudável, e nenhum teste reclamava.\n\nPor que ninguém pegou antes: os instrumentos que a casa usa não medem isso. O teste do Django devolve a página e a regra, mas não aplica uma sobre a outra. O curl baixa a página inteira, com o estilo lá dentro, sem nunca desenhá-la. Os dois ficavam verdes. A prova só apareceu quando abri a página num Chrome de verdade, que recusou em voz alta — e ainda disse exatamente qual assinatura faltava.\n\nO conserto: em vez de afrouxar a regra (o caminho fácil, que liberaria qualquer estilo injetado de fora), o servidor agora assina o estilo daquela página e manda a assinatura junto. Como a assinatura é calculada da própria página servida, ninguém precisa lembrar de atualizá-la quando o visual mudar.\n\nFalta uma metade, e ela é pequena: uns 39 ajustes soltos de margem espalhados pelas telas continuam bloqueados, porque para esses o padrão exige outra coisa. O próximo passo troca esses ajustes por regras na folha. A diferença prática: hoje as telas voltam a ter desenho; antes não tinham nenhum.",
  autoridade: "sonda",
  evidencia: "PR #579 (https://github.com/abundanciabr/sitesdoreino/pull/579). Prova de FORA, com Chrome headless batendo na produção em https://meshcraft.top/docs/: \"Applying inline style violates the following Content Security Policy directive 'style-src 'self''. ... The action has been blocked\" — e o hash que o Chrome pediu (sha256-g1URTZmJNLktPGlRhWn6uQA0uhs8YibnAsi1DpcL2EQ=) é exatamente o que o conserto calcula. Vermelho->verde: sem o conserto, 6 dos 9 testes novos reprovam nomeando as 5 famílias de tela; com ele, 9/9, e a suíte da célula inteira em 362 verdes.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
