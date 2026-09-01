(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-033-o-banco-passa-a-ter-copia-antes-de-toda-mudanca",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A plataforma passa a guardar uma cópia do banco antes de toda mudança que ela publica",
  detalhe: "Até hoje, quando uma parte do site subia com uma mudança na forma de guardar os dados, essa mudança acontecia e pronto. Não havia volta. Se ela apagasse uma coluna sem querer, ou convertesse um dado de um jeito errado, o dado ia embora e não existia nenhuma cópia de antes. Isso acabou.\n\nO que passa a acontecer, sozinho, em toda entrega: antes de a versão nova entrar no ar, a plataforma tira uma cópia completa do banco daquela parte do site e guarda no servidor. Só depois disso ela deixa a versão nova subir. É uma foto do estado exato de segundos antes.\n\nA parte incômoda, e ela é de propósito: se a cópia não conseguir ser feita, a entrega PARA. O site continua no ar com a versão anterior, nada muda, e o robô te diz o que aconteceu. Um backup que tenta e desiste é um backup que não existe justamente no dia em que você precisa dele.\n\nPor que a cópia é feita sempre, e não só quando há mudança de banco: para descobrir se existe mudança de banco seria preciso subir a versão nova e perguntar a ela, que é exatamente o risco que estamos evitando. Copiar sempre é mais simples e não tem como errar em silêncio.\n\nO caminho de volta também existe, e é isso que faz a cópia valer alguma coisa. Um segundo comando devolve o banco ao estado de qualquer cópia guardada. Ele não faz nada sem você confirmar com todas as letras: rodado normalmente, ele só mostra o que faria e para. E ele avisa, em português simples, que a volta apaga tudo o que entrou depois daquela hora e que não dá para desfazer.\n\nFicam guardadas as 20 cópias mais recentes de cada parte do site, e as antigas são apagadas sozinhas. O espaço em disco é conferido ANTES de gravar: se faltar espaço, a entrega para com uma mensagem clara, em vez de gravar meio arquivo. Arquivo pela metade com nome de backup é pior que backup nenhum, porque ele mente no pior dia.\n\nProva: numa cópia de mentira da plataforma, com um banco de verdade, criei uma tabela com uma linha, rodei a entrega inteira, apaguei a tabela e restaurei. A linha voltou idêntica.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/837",
  verificado_em: "2026-09-01",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
