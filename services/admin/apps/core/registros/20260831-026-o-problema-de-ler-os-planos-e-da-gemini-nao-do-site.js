(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-026-o-problema-de-ler-os-planos-e-da-gemini-nao-do-site",
  tipo: "medicao",
  quando: "2026-08-31",
  titulo: "Descoberto por que as IAs nao liam os planos: e a Gemini, nao o site — e o GPT le normalmente",
  detalhe: "Voce testou e trouxe o dado que fechou o diagnostico: O GPT LEU O DOCUMENTO NORMALMENTE, pelo mesmo link do GitHub que a Gemini recusou. Isso isola o problema — nao e o documento, nao e o endereco, e a Gemini.\n\nO QUE FOI MEDIDO E DESCARTADO no site, uma causa por vez: nao exige login (responde sem cookie); nao bloqueia robo (responde 200 para GPTBot, GoogleOther e Google-Extended); nao ha robots.txt proibindo; nao ha IPv6 quebrado; a cadeia de certificado verifica completa; o servidor fala HTTP/2 igual ao GitHub; e o DNS do proprio Google devolve o endereco certo. Tirei tambem um marcador meu ('noindex') que dizia as IAs para ignorarem a pagina — esse era erro meu, e foi corrigido.\n\nMesmo assim a Gemini continua sem alcancar meshcraft.top, com um erro de rede que acontece do lado dela. O que sobra sao duas hipoteses que eu NAO consigo medir daqui: o servidor pode estar barrando as maquinas do Google por regra de firewall (e eu nao tenho acesso ao servidor, por lei do projeto), ou a Gemini pode desconfiar de um dominio novo terminado em .top.\n\nA GEMINI TAMBEM ERROU no proprio diagnostico, e eu conferi antes de repassar: ela disse que o texto do GitHub 'e carregado por JavaScript' e por isso nao aparecia. Falso — o texto ESTA no HTML (a palavra 'jornadas' aparece 14 vezes la). Ela so nao conseguiu extrair. Tanto que o GPT extraiu.\n\nO QUE FAZER NA PRATICA: para qualquer IA, use o endereco 'raw' do GitHub. E texto puro, sem pagina, sem JavaScript e sem marcador nenhum — e a forma que a propria Gemini recomendou. O endereco do site continua servindo bem para voce e para qualquer navegador.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/692 (a retirada do noindex, com deploy verde) e https://github.com/abundanciabr/sitesdoreino/pull/695. Medicoes: 200 para GPTBot/GoogleOther/Google-Extended; robots.txt 404; sem registro AAAA; openssl Verify return code 0; ALPN h2 nos dois servidores; 8.8.8.8 e 1.1.1.1 devolvem 217.196.62.220; o HTML do /blob/ do GitHub contem 'jornadas' 14 vezes. Testemunho do mantenedor: o GPT leu o /blob/ normalmente.",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,

  se_eu_nao_decidir: "Nada quebra, e voce continua com um caminho que funciona (o endereco raw do GitHub). O que fica sem resposta e por que as maquinas do Google nao alcancam meshcraft.top — e isso pode importar depois por outro motivo: se for o servidor barrando, o site tambem nao sera lido pelo buscador do Google quando voce quiser que ele seja.",
  recomendacao: "Nao gastar tempo nisso agora. O caminho do GitHub resolve o seu problema de hoje. Vale investigar quando alguem com acesso ao servidor puder olhar o firewall — e ai a pergunta certa e se ha regra barrando faixas de datacenter.",
  reversivel: true,
  impacto: "baixo"
});})();
