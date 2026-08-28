(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-031-a-trava-da-colisao-mais-perigosa-foi-ligada",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "A trava da colisão mais perigosa foi ligada, e o aviso de senha vazada também",
  detalhe: "Você autorizou a Onda 0 e ela está feita. São três coisas, e nenhuma delas escreveu código.\n\nPRIMEIRA, e é a que importa: agora uma entrega não pode mais ser aprovada contra uma versão velha do projeto. Antes, um robô testava o trabalho dele contra o projeto das 14h, outro robô mudava o projeto às 14h30, e o primeiro mergeava mesmo assim — com um sinal verde que já não valia. Era o acidente mais perigoso da lista, e era o único que não tinha trava nenhuma. Agora o GitHub recusa sozinho.\n\nSEGUNDA: o aviso automático de senha vazada está ligado, junto com o bloqueio que impede um robô de publicar uma senha por acidente. São gratuitos justamente porque o projeto é aberto.\n\nTERCEIRA: corrigi a lei que estava desatualizada e que causou o erro da consulta. Ela afirmava que o projeto não podia ter proteção da versão oficial por ser paga — e o projeto já tinha, desde 26 de agosto. Foi essa frase, lida com sinceridade, que virou premissa falsa entregue às cinco IAs.\n\nA lei agora conta a própria história de ter mentido, e manda quem for decidir alguma coisa conferir o estado real antes de acreditar nela. É o começo da ideia que o plano chama de melhor da rodada: toda lei precisa dizer quem a faz valer, e lei sem ninguém fazendo valer devia aparecer em vermelho.\n\nUm aviso honesto sobre a primeira trava: enquanto a Onda 4 não chegar, cada entrega que entra obriga as outras em andamento a se atualizarem e rodarem os testes de novo. Isso dá retrabalho visível. É a troca certa mesmo assim, porque a alternativa era quebrar em silêncio — e o botão volta atrás a qualquer momento se incomodar demais.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/367 (a lei corrigida). Conferido em 28/08/2026 lendo o estado real do GitHub, não o que o script disse: gh api repos/abundanciabr/sitesdoreino/rulesets => strict_required_status_checks_policy: true, enforcement active, bypass_actors vazio, checks muralhas e ci-celula-gate intactos, os mesmos 4 tipos de regra de antes. gh api repos/abundanciabr/sitesdoreino => secret_scanning enabled, secret_scanning_push_protection enabled. Nota de honestidade: o metodo PATCH devolvia 404 em silencio e a leitura seguinte mostrou que NADA tinha mudado; so o PUT funcionou. Sem a conferencia de fora, este registro teria nascido verde e falso.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260828-024-o-plano-para-os-robos-nao-se-atrapalharem-esta-pronto",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
