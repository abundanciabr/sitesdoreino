(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-007-o-forum-da-escola-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O FÓRUM DA ESCOLA ESTÁ NO AR — meshcraft.top/forum abriu",
  detalhe: "O fórum estava construído e desligado havia dois dias: as telas prontas, o modelo de dados pronto, e nenhuma eletricidade. Hoje ele abriu.\n\nO QUE VOCÊ FEZ: colou uma linha na janela da VPS. O instalador criou o banco do fórum, escreveu as configurações e abriu as duas conversas que ele precisa ter (com o login do site e com a lista de alunos).\n\nO QUE EU FIZ ANTES DISSO — e o que achei no caminho:\n\n1) RESGATE. O instalador existia desde 28/08 numa pasta de trabalho abandonada, com 290 linhas nunca salvas no projeto. Não havia nada equivalente. Conferi cada afirmação dele contra o código que ele configura, e trouxe para dentro.\n\n2) UM DEFEITO NO INSTALADOR. Ele escrevia as chaves novas nos arquivos das duas células parceiras e não as reiniciava. Um programa só lê a configuração quando renasce — as duas seguiriam sem conhecer o fórum, e ele levaria erro de permissão em toda página, com o sinal de entrega verde. Corrigido: a sua tela mostrou \"recarreguei: identidade alunos\", que é essa correção rodando.\n\n3) UM DEFEITO PIOR, ANTES. O fórum perguntava no endereço errado se a pessoa é aluna. Teria deixado NINGUÉM ser aluno, para sempre, em silêncio. Corrigido e travado em teste (registro anterior).\n\nPROVA DE FORA, medida na internet pública logo após o deploy: /forum/ responde 200 com página de verdade; /forum/healthz 200; o CSS 200; uma área inexistente dá 404 (o roteamento funciona). E o resto do site intacto: a home 200, a área administrativa e a Caixa continuam redirecionando para o login como sempre.\n\nO QUE O FÓRUM MOSTRA HOJE: a página diz, com honestidade, que ainda não há nenhuma área aberta. Ele é só de leitura — ninguém escreve ainda. Escrever é o próximo degrau.\n\nO QUE AINDA DEPENDE DE VOCÊ, e não é para agora: antes de o fórum abrir ao PÚBLICO, duas perguntas precisam de resposta sua — como ele não fica deserto nos primeiros 90 dias, e como ficam menores de idade, moderação e a lei brasileira. Construir não depende delas; abrir a porta depende.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/549",
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
