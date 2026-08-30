(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-033-o-admin-passa-a-mostrar-com-base-em-que-a-obra-foi-liberada",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O painel de administração agora mostra com base em qual documento cada obra foi liberada",
  detalhe: "Faltava uma coisa para as telas velhas da Caixa de Sugestões poderem ser desligadas, e era esta: quando você assina a autorização de uma obra, o painel guardava só um carimbo de \"assinada\" — não dava para voltar depois e ver QUAL documento você aprovou, em que dia, e quem trouxe isso para dentro do sistema. Só a tela antiga mostrava. Agora a tela de cada ideia mostra a ficha inteira, e mostra todas as versões: quando um escopo muda, nasce um documento novo com o sufixo -v2, e os dois continuam valendo.\n\nJunto veio uma coisa pequena que estava errada e ninguém tinha visto: se você digitasse uma nota fora da escala de 0 a 5 na avaliação da equipe (um 99, ou uma palavra), a tela guardava outro número no lugar em silêncio e respondia \"Avaliação guardada\". Agora ela recusa e explica, como a tela antiga fazia — escrever outra coisa no lugar do que a pessoa quis é pior do que dizer que não entendeu.\n\nForam três degraus, nesta ordem, porque mexer no contrato entre duas partes do sistema é um rito à parte: primeiro o contrato (PR #581), depois a Caixa aprendendo a responder a ficha (PR #588), e por último o painel mostrando (PR #589). Falta o quarto degrau: desligar os cinco endereços antigos, redirecionando quem os tiver salvo em vez de apagá-los.",
  autoridade: "github",
  evidencia: "Escada da TAR-023, com o mandato explícito do mantenedor de 30/08/2026 para tocar contracts/ (CODEOWNERS): https://github.com/abundanciabr/sitesdoreino/pull/581 (contrato — 4ª emenda, componente ChangeSpecAssinado) · https://github.com/abundanciabr/sitesdoreino/pull/588 (a Caixa responde a ficha — 507 testes verdes, vermelho→verde com a segunda medida da armadilhas/195) · https://github.com/abundanciabr/sitesdoreino/pull/589 (o Admin mostra — 370 testes verdes, 7 vermelhos de asserção sem o conserto). O #581 está MERGEADO (merge 1dfce1a4417db435be83371ee30011b468a82bed).",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: "20260830-019-parei-antes-de-aposentar-a-moderacao",
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
