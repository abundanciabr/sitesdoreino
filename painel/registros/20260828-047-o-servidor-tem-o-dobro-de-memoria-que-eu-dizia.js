(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-047-o-servidor-tem-o-dobro-de-memoria-que-eu-dizia",
  tipo: "medicao",
  quando: "2026-08-28",
  titulo: "O servidor tem o DOBRO da memória que eu afirmei — e o aperto está no processador, não na memória",
  detalhe: "Você mandou a tela do painel da Hostinger, e ela me corrigiu.\n\nEU ESTAVA ERRADO: escrevi nos documentos da consulta do fórum que a máquina tinha 2 GB de memória. Tem 4 GB. O plano é o KVM 1 — 1 núcleo de processador, 4 GB de memória, 50 GB de disco, 4 TB de tráfego. Você estava mais certo do que eu quando disse que dava para pensar no Discourse, e o registro fica.\n\nO ESTADO MEDIDO, em 28/08/2026: processador em 50%, memória em 35%, disco em 12 dos 50 GB, tráfego em 0.002 dos 4 TB. É a primeira vez que este projeto tem esses números escritos em algum lugar — não existiam em nenhum documento.\n\nO QUE ISSO MUDA: sobra memória de verdade (65% livre). O argumento que eu usei contra o Discourse — \"não cabe por falta de memória\" — ficou bem mais fraco.\n\nO QUE ISSO REVELOU, e ninguém tinha olhado: o gargalo é o PROCESSADOR. É um núcleo só, e ele já está em 50% de uso sustentado com o fórum ainda nem existindo. Isso vale para qualquer coisa nova que a gente pense em instalar, não só para fórum.\n\nE VOCÊ DISSE QUE SOBE DE PLANO quando for necessário — KVM 2, com 2 núcleos e 8 GB. Isso muda a pergunta da consultoria inteira: deixou de ser \"cabe?\" e virou \"vale a pena pagar mais por mês para rodar o Discourse, em vez de uma solução que roda no que já existe?\". É essa a pergunta que está no prompt agora.\n\nO QUE NÃO MUDA, e virou o argumento mais forte que sobrou contra o Discourse: a forma normal de atualizá-lo é entrar no servidor e rodar o instalador dele. Nenhum robô entra lá. Trocar de plano não resolve isso — seria tarefa recorrente sua, no terminal, para sempre.\n\nOs quatro arquivos da consulta foram corrigidos antes de você colar o prompt em qualquer IA. Se tivessem ido com o número errado, as respostas viriam envenenadas — três consultores calculando com metade da memória real.\n\nO bloco de medir a memória continua na pasta, mas deixou de ser urgente: agora ele serve para o que o painel não mostra — quanto cada um dos 24 programas consome, se existe memória de emergência em disco, e a fila do processador.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/386. Fonte: captura do painel da Hostinger enviada pelo mantenedor em 28/08/2026, mais a ficha do plano KVM 1 (1 vCPU, 4 GB RAM, 50 GB NVMe, 4 TB) e a do KVM 2 (2 vCPU, 8 GB, 100 GB, 8 TB), ambas enviadas por ele. Numero deste registro alocado pelo servidor via ci/reservar.py (Onda 2), nao adivinhado.",
  verificado_em: "2026-08-28",
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
