(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-062-o-boletim-mostrava-o-teto-como-se-fosse-o-total",
  tipo: "nota",
  quando: "2026-08-28",
  titulo: "O boletim dizia 40 entregas em 24 horas, e foram 98 — defeito meu, anotado para consertar junto com a Onda 3",
  detalhe: "Você me pediu para mostrar onde o plano parou. Ao conferir, achei um defeito na ferramenta que eu mesmo entreguei hoje.\n\nO boletim que toda sessão lê ao abrir anuncia 'o que pousou nas últimas 24h' seguido de um número. Esse número não é a contagem de verdade: é o teto do que eu mandei ele buscar. Onde ele dizia 40, tinham sido 98.\n\nNão quebra nada e não esconde risco nenhum: o resto do boletim continua certo — quem está mexendo em quê, lei que mudou, número livre. Mas é um número que parece exato e está errado, e isso este projeto trata como defeito, não como detalhe. Foi rodar a ferramenta e comparar com a realidade que revelou, do mesmo jeito que aconteceu três vezes ontem.\n\nVocê decidiu não gastar um ciclo de entrega só nisso, e sim consertar junto com a Onda 3, que já vai mexer nessa vizinhança. Para essa decisão não virar promessa esquecida, ela não ficou só aqui: está escrita dentro do escopo da Onda 3 no próprio plano. Quem pegar aquela onda vai esbarrar nela sem precisar lembrar.\n\nO conserto combinado: dizer a contagem verdadeira e, quando a lista não couber na tela, escrever 'mostrando 15 de 98' em vez de fingir que 98 são 40 — com um teste que reprove quem voltar a confundir teto com contagem.\n\nDe resto, o plano está firme: as ondas 0, 1 e 2 estão no ar e conferidas hoje, e outras sessões já estão pedindo número ao servidor sem ninguém mandar.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/414. Medido em 28/08/2026: `gh pr list --state merged` filtrado por mergedAt nas ultimas 24h devolveu 98; LIMITE_DE_POUSOS em ci/boletim.py e 40, e o boletim imprimia len(pousos) = 40. Conferido no mesmo momento que as ondas 0, 1 e 2: ruleset com strict=true e enforcement active; ci/boletim.py e ci/reservar.py presentes; 10 numeros ja alocados pelo cofre por outras sessoes (056 a 060 entre eles); 59 registros no dia sem numero repetido.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
