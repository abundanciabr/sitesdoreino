(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-005-a-caixa-de-pergunta-virou-regra-permanente",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Você pediu para eu sempre usar a caixa de múltipla escolha, em vez de deixar texto solto esperando resposta — agora é regra permanente, em qualquer conversa",
  detalhe: "Depois de eu fechar um relatório com uma frase solta ('isso vai precisar de uma conversa sua quando puder'), você pediu a 'caixa daquelas que aparece pedindo a resposta' no lugar — e perguntou se dava para deixar isso padrão para qualquer robô, em qualquer conversa.\n\nO QUE FIZ: escrevi a regra em dois lugares. Primeiro, fora deste projeto — em `~/.claude/CLAUDE.md`, no seu computador — porque você escolheu que isso vale para QUALQUER conversa sua comigo, não só aqui na plataforma. Segundo, reforcei a versão que já existia na lei deste projeto (o `CLAUDE.md` daqui), porque aqui tem uma nuance a mais: quando vários robôs trabalham ao mesmo tempo (o que este projeto chama de 'lote'), só UM deles fala com você — os outros reportam para esse, em texto — para você nunca receber cinco caixas de pergunta ao mesmo tempo.\n\nA REGRA, em uma frase: sempre que sobrar algo pendente com você ao fim de uma tarefa — decisão técnica ou só um agendamento tipo 'quer que eu explique agora ou depois' — a resposta é abrir a caixa de múltipla escolha ali mesmo, nunca deixar frase solta.\n\nEsta mudança só toca instruções (arquivos de texto que me guiam), nenhum código da plataforma — por isso não há tela nem comportamento do site para testar.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/272 — MERGED (commit f8855b4); checks detectar/muralhas/ci-celula-gate PASS (ci-celula pulado de propósito, PR não toca célula nenhuma); pedido explícito do mantenedor nesta conversa, com a escolha de alcance ('qualquer conversa') respondida por ele via AskUserQuestion",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
