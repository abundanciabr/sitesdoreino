(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-060-o-cartao-de-teste-fica-parado-ate-a-venda-voltar",
  tipo: "decisao",
  quando: "2026-08-29",
  titulo: "O cartão de teste NÃO precisa de você — o pedido estava errado, e você decidiu deixá-lo parado",
  detalhe: "ESTE PEDIDO PEDIA A COISA ERRADA, e eu só descobri porque fui procurar o nome exato do segredo para te entregar.\n\nO pedido dizia: cole a credencial de teste do Mercado Pago no cofre do GitHub, e isso destrava um teste diário automático da compra. Fui ver onde esse segredo seria lido — e NENHUM robô o lê. Procurei em todos os sete robôs automatizados do projeto: os segredos que eles usam são outros (a chave de entrega no servidor, o endereço da máquina, os tokens do GitHub). Nenhum menciona Mercado Pago.\n\nO teste da compra existe como script, mas ninguém o roda sozinho: ele lê a credencial de um arquivo NA MÁQUINA de quem roda, não do cofre. E não existe robô nenhum que o dispare todo dia — nem de madrugada, nem em hora nenhuma.\n\nOU SEJA: colar a credencial hoje não faria absolutamente nada. Ela ficaria guardada num cofre que ninguém abre. O que falta não é você — é construir o robô do teste diário, e isso é obra da frente de PAGAMENTO, congelada por ordem sua desde 22/08 ('pagamento por último').\n\nSUA DECISÃO, tomada com esse fato na mesa: fica parado até a venda voltar. Nada quebra — a plataforma não vende hoje, então não há compra para testar. O pedido sai da caixa e volta sozinho no dia em que você reabrir a frente de venda.\n\nPor que isto é melhor do que ter colado assim mesmo: um segredo guardado num cofre que ninguém lê parece proteção e não é; e a caixa deixaria de mentir que ela esperava por você, quando na verdade esperava por uma obra.",
  autoridade: "mantenedor",
  evidencia: "Decisao do mantenedor em 29/08/2026, na sessao de esvaziamento da caixa 'Precisa de voce'. O fato que a embasa foi medido na mesma sessao: 'grep -rhoE secrets.[A-Z_]+ .github/workflows/' devolve exatamente quatro segredos — DEPLOY_SSH_KEY, GITHUB_TOKEN, PISTA_TOKEN e VPS_HOST — nenhum de Mercado Pago; e 'grep -rln esqueleto .github/workflows/' nao devolve NENHUM arquivo, ou seja, nenhum robo dispara o teste de ponta a ponta. O e2e/esqueleto.sh le MP_ACCESS_TOKEN de e2e/.env.e2e, um arquivo local, nunca do cofre.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: "20260822-001-h8-cartao-de-teste-no-cofre",
  gravidade: "info",
  frente: "vender",
  vence_em_dias: null
});})();
