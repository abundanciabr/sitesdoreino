# Retomada do Crivo — estado e decisões em 02/10/2026

Este arquivo registra o produto decidido e o estado observável do trabalho.
O [manual completo e didático](manual-completo-e-didatico-para-criar-publicar-e-operar-quizzes.md)
é a referência canônica para entender o produto e a jornada de uma pessoa.
Ele reúne as decisões direcionadas e identifica a seleção por peso como legado.
A seção de 26/09 abaixo é
registro histórico, não uma sequência de ações a executar hoje.

## Produto decidido para novos quizzes

Um quiz é uma jornada no mesmo endereço `/quiz/<slug>/`; várias campanhas
podem levar pessoas a ele. A pessoa chega por um
link que diz explicitamente qual versão verá: `?v=A`, `?v=B1` ou `?v=B2`. A
versão é escolhida por quem cria o link, não por divisão automática de tráfego.
As versões têm perguntas, opções, pontuação, faixas e resultados próprios.
O comportamento antigo de peso permanece para quizzes legados, sem determinar
as novas campanhas. Versão inválida não pode escolher outra silenciosamente;
a entrada sem `v` pode ser informativa, sem iniciar uma versão aleatória.

O restante do link define a experiência: `fmt` seleciona `text`, `video`,
`hybrid`, `calc` ou `ai`; sem `fmt`, vale o `default_format` da versão.
`seg` seleciona o segmento configurado. `src`, `med`, `cpg` e `ctv` identificam
origem, meio, campanha e criativo; parâmetros `utm_*` também entram na origem.
Versão, formato, segmento e marcadores da chegada devem acompanhar a tentativa,
a submissão e a leitura da campanha, sem trocar a origem quando a pessoa volta.
Exemplo de formato de link, sem afirmar que a versão ou o host já estejam
publicados: `https://exemplo.com/quiz/<slug>/?v=B2&fmt=text&seg=<segmento>&src=<origem>&med=<meio>&cpg=<campanha>&ctv=<criativo>`.

Cada faixa indica uma de **duas ofertas externas**. Os endereços de checkout
ficam `null` no documento inicial e serão fornecidos depois de testar o quiz.
Enquanto não houver link, o botão abre uma demonstração da oferta indicada,
sem cobrança. Quando os dois endereços HTTPS forem recebidos, a conexão
atualiza os destinos e recupera os rótulos originais das faixas sem alterar
perguntas, pontos, títulos nem o documento importado. O Crivo não cobra cartão
nem cria produto. A escolha de oferta e o resultado pertencem à campanha;
compra e receita exigem retorno do provedor do checkout externo. Preencher
campos em outro domínio também depende de integração oferecida por ele;
o quiz não consegue manipular livremente aquele formulário.

O formato de importação decidido é `quiz-low-ticket/2`, com `formato`, `quiz`,
duas `ofertas` e `versoes`. A mesma versão reimportada com documento idêntico
não duplica dados; conteúdo diferente pede outra `key`. Isso permite que os
checkouts sejam conectados depois sem reescrever o documento original.

## Estado observado neste checkout em 02/10/2026

| Parte | Evidência no repositório | Estado desta retomada |
|---|---|---|
| Crivo legado e Refazer | `services/quiz/apps/quiz/views.py`, rota `refazer` e `tests/test_refazer.py` | Refazer foi concluído no ciclo de 26/09; não é uma decisão pendente. |
| Links direcionados e contexto | `services/quiz/apps/quiz/direcionadas.py`, `experiencias.py`, `management/commands/gerar_links_quiz.py` | Integrados ao formulário, resultado, saída e Refazer; testes locais aprovados. |
| Conteúdo e duas ofertas | `services/quiz/apps/quiz/conteudo.py`, `destinos.py`, comandos `importar_quiz` e `conectar_checkouts` | Há importação e conexão posterior no checkout; os dois links reais ainda não foram fornecidos. |
| Editor | `services/quiz/apps/quiz/editor.py`, `QuizDraft`, painel e testes | Importação JSON direcionada no site, rascunho e publicação sem substituir versões anteriores; estúdio visual completo pendente. |
| Medição própria | `services/quiz/apps/quiz/campanhas.py`, `TelemetryEvent`, `Submission`, API e painel | Contagens e links acessíveis no painel implementado; conclusões sem visita são separadas, cliques não comprovam compra. |
| Integração de banco | `models.py` e migrações `0008_experiencias_direcionadas.py` e `0006_quizdraft.py` | Campos integrados e numeração reconciliada; Django não encontrou problema nem migração faltante. |

Passaram **193 testes do quiz e 10 do painel administrativo** na integração
local de 02/10. No navegador local, os dois caminhos de oferta, Refazer com
versão/origem preservadas e a calculadora funcionaram. A prova de
**94 testes em 01/10/2026** permanece
histórica. Desde 02/10 a integração nova está na main, e a main publica
sozinha pela VPS (veja "Como operar hoje"). Conteúdo real, mídias, contas
externas e os dois links de checkout ainda não foram fornecidos.

## Continuação do produto, por etapa

1. **Conteúdo e experiência:** consolidar a campanha com `A`, `B1` e `B2` no
   mesmo slug; perguntas, faixas, dois destinos e cópia próprios por versão;
   texto, vídeo, híbrido, calculadora e IA conforme o conteúdo aprovado.
   Vídeo precisa de URL reproduzível; calculadora usa expressão aritmética
   limitada; a configuração `ai` já pode apresentar texto, mas a integração
   com agente de IA não está demonstrada como disponível no código lido.
2. **Estúdio:** chegar a uma criação e edição completas no site, com rascunho,
   prévia, publicação e edição das versões, formatos, segmentos, ofertas e
   resultado. A API privada de rascunho existente é uma peça dessa etapa;
   não equivale à interface final para quem opera campanhas.
3. **Jornada e prova:** gerar links com versão, formato, segmento e campanha;
   testar formulário, pontuação no servidor, resultado, Refazer, retorno da
   pessoa e persistência do contexto. A prova automática e o endereço público
   abrindo são o fechamento de uma entrega, não uma inferência a partir dos
   arquivos presentes.
4. **Checkout:** após o teste do quiz e o recebimento dos dois URLs reais,
   conectá-los às ofertas externas, confirmar cada botão e medir a saída.
   Nenhum endereço de `example.com` usado em teste é checkout real.
5. **Aquisição e relacionamento:** instrumentar GA4, Meta e TikTok; integrar
   os eventos e segmentos a CRMs e mensagens, incluindo Klaviyo e
   ActiveCampaign; operar públicos de retargeting. Contas, permissões,
   identificadores e credenciais dessas plataformas são dependências a
   configurar, não prova de que integrações já estejam ativas.
6. **Resultado econômico:** unir origem e conclusão do quiz às compras
   confirmadas; acompanhar receita, conversão, recorrência e LTV por versão,
   formato, segmento, criativo e dia de chegada da campanha. Expor a análise
   em Looker e Metabase e usar o que foi medido para melhorar conteúdo e
   investimento. O relatório próprio do Crivo mede visita, submissão e saída;
   não mede sozinho venda nem LTV.

Os comandos existentes em `services/quiz/apps/quiz/management/commands/` são
`importar_quiz --arquivo --host --site-id --site-name`, `gerar_links_quiz
--slug --versoes --formatos` (com `--site-id` quando necessário) e
`conectar_checkouts --slug --site-id --arquivo`. O último lê um JSON que mapeia
os dois IDs de oferta a URLs HTTPS, depois que esses endereços existirem.
`campanhas --slug --site-id` lê as contagens próprias. Os argumentos exatos
estão nos próprios comandos; esta seção registra o que já existe, sem assumir
que foi implantado.

Antes de publicar, há backup. Se a prova falhar ou o site cair, o código volta
sozinho para a última versão aprovada; o banco **não** é restaurado sozinho.
Isso vem do `AGENTS.md` do projeto. Esta rodada integrou e testou código local,
sem publicar código nem conectar plataformas de marketing. O documento
explicativo já existente no site tem edição e histórico próprios no banco;
atualizar o arquivo de origem não sincroniza automaticamente esse corpo.

## Como operar hoje

- Publicar: envie para a main (`git push origin HEAD:main`). A VPS recebe e
  publica sozinha em até 1 minuto. Acompanhe com
  `ssh sitesdoreino-vps /opt/plataforma/bin/plataforma receber --esperar` até
  `LOTE-CONCLUIDO ... falhas=0`. Se a prova falhar, o código volta sozinho.
- Medir a configuração do quiz em produção:
  `ssh sitesdoreino-vps /opt/plataforma/bin/plataforma operar operacoes-vps --operacao quiz-configuracao --servico quiz`.
- Comandos de gerência da célula (`importar_quiz`, `conectar_checkouts`,
  `gerar_links_quiz`, `campanhas`) rodam na VPS, dentro do serviço `quiz`.

## Registro histórico de 26/09/2026

As notas daquela retomada descreviam fila de tarefas, bancadas, linhas de
mandato, `ci/fila.py` e o workflow `operacoes-vps.yml`, que não existem mais.
O texto integral fica no histórico do git:
`git show 94972b4e9:docs/quiz/RETOMADA-CRIVO.md`. O que dele ainda vale está
resumido acima: Refazer foi entregue, e a oferta `curso-teste` e o menu daquela
data dizem respeito ao Crivo legado.
