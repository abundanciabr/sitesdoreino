# Manual completo e didático para criar, publicar e operar um sistema de quizzes

Atualizado em **02/10/2026**. Este manual reúne as decisões do mantenedor, todas as capacidades solicitadas e o estado observado no projeto. A explicação para iniciantes está em [O Crivo explicado do zero](../../documentos/o-crivo-explicado-do-zero.md); a continuidade está em [RETOMADA-CRIVO.md](RETOMADA-CRIVO.md).

Ana é nossa operadora fictícia. Ela quer receber visitantes, entender suas necessidades e indicar uma de duas ofertas low ticket, com checkout externo. **Tema, público, ofertas, mídia e conteúdo reais ainda não foram definidos.** Exemplos neste manual não são conteúdo comercial aprovado.

As indicações de estado significam:

- **Observado na base atual:** encontrado no código versionado; não significa verificado em produção.
- **Decisão aprovada:** comportamento pedido pelo mantenedor.
- **Integrado e testado localmente:** a implementação passou na prova local; ainda precisa de publicação e conferência no endereço público.
- **Pendente:** falta implementação, conteúdo, acesso ou integração.
- **Histórico:** registro anterior; não comprova a versão atual.

Este documento registra o trabalho; não cria regras permanentes, processos ou autorizações adicionais. As instruções vigentes do mantenedor estão em [AGENTS.md](../../AGENTS.md). O manual anterior foi preservado no final como histórico e pode conter descrições já superadas.

## 1. Decisão central: somente campanhas direcionadas

Uma URL estável por quiz. O link escolhe explicitamente a versão:

```text
/quiz/encontre-sua-solucao/?v=A
/quiz/encontre-sua-solucao/?v=B1
/quiz/encontre-sua-solucao/?v=B2
```

**Novas visitas ao terceiro link recebem B2.** Não haverá sorteio nem divisão automática por peso nesse modo. Um quiz pode atender várias campanhas; campanha e quiz não são sinônimos.

A, B1 e B2 podem mudar CTA, promessa, vídeo, perguntas, ordem e quantidade de etapas. Não é necessário criar outro slug para isso. Outra jornada ou produto independente pode justificar outro slug.

Uma participação mantém sua versão, formato, segmento e origem durante perguntas, resultado e saída. Um novo link explícito para outra experiência não pode misturar respostas com a anterior. Atualizar a página não cria outra conclusão nem outra visita elegível.

Versão, formato ou segmento desconhecido não deve ser substituído silenciosamente por outro. Sem `v`, a entrada pode explicar o quiz sem iniciar uma versão aleatória.

**Comparação direcionada não é um teste aleatório automaticamente confiável.** Públicos, períodos, criativos e verbas diferentes podem explicar diferenças de conversão. Os relatórios devem permitir enxergar esses contextos. A operação continuará direcionada, conforme escolha do mantenedor.

## 2. Estado real observado em 02/10

Integração local de 02/10/2026, posterior à revisão documental `94972b4e9`. A publicação do código novo depende do acesso à VPS; não foi comprovada em produção.

| Capacidade | Evidência | Estado |
|---|---|---|
| Perguntas, opções, pontos no servidor, faixas, lead | Modelos, views e templates | Observado na base atual |
| Sessão assinada, versão estável, UTMs, refazer | `views.py` e rotas | Observado na base atual |
| Telemetria, submissão, outbox e relay | Modelos, views e tarefas | Observado na base atual |
| Editor pelo site e rascunho separado | `QuizDraft`, `editor.py`, painel `conteudos.py` | Importação JSON direcionada integrada e testada; estúdio visual completo pendente |
| Direcionamento por `v`, formatos, segmentos, calculadora | `direcionadas.py`, `experiencias.py`, views e templates | Integrado e testado localmente; mídia real ainda necessária |
| Saída rastreada, demonstração e conexão dos dois checkouts | `destinos.py`, views e comandos | Integrado e testado localmente; links reais ainda não recebidos |
| JSON `quiz-low-ticket/2` e gerador de links | Importador, gerador e painel privado | Integrado e testado localmente |
| Relatório por dia e campanha | `campanhas.py`, API privada e painel administrativo | Integrado e testado localmente; sem receita/LTV confirmados |
| Conversa por IA, integrações de mídia/CRM/BI e compras externas | Escopo solicitado | Pendente |

Os modelos agora declaram `Quiz.directed`, `QuizVersion.experience` e `Submission.context`. A migração de experiências foi reconciliada como `0008_experiencias_direcionadas`, depois de `0007_portfolio_journey`; o rascunho mantém sua migração `0006_quizdraft`. As rotas ligam calculadora, demonstração, saída e API de campanhas. A conferência local do Django não encontrou problema nem migração faltante.

**Prova local de 02/10:** **193 testes do quiz e 10 do painel administrativo passaram**, incluindo versões simultâneas, Refazer, duas ofertas, calculadora, contexto, cookies e relatórios. No navegador local, B2 concluiu os dois caminhos de oferta, Refazer manteve versão/origem e a calculadora retornou 50 para uma entrada de 25. O contrato de conclusão agora aceita `context` opcional, preservando mensagens legadas. Os 94 testes de 01/10 permanecem apenas como registro histórico. A prova local não comprova publicação.

O resolvedor usa `v` nos quizzes direcionados e conserva a seleção por peso apenas no fluxo legado. Nova visita com B2 recebe B2 mesmo quando outra versão tem peso maior.

## 3. Entender o percurso sem programar

O quiz é como uma recepcionista: pergunta, organiza respostas e encaminha. A nota vem das opções no banco, nunca de um número enviado pelo visitante.

```mermaid
flowchart LR
    A[Campanha B2] --> B[Perguntas B2]
    B --> C[Pontuação no servidor]
    C --> D[Resultado e uma de duas ofertas]
    D --> E[Checkout externo]
    E --> F[Retorno de compra pela integração]
```

A última seta é uma capacidade pretendida e depende do checkout. Abrir o botão não comprova pagamento.

Exemplo didático: escolhas de 5, 10 e 0 pontos somam 15. A faixa correspondente determina resultado, mensagem e oferta. Podem existir várias faixas, mas todas indicam uma das **duas ofertas**. As pontuações possíveis precisam estar cobertas sem sobreposição. O editor atual já verifica cobertura e sobreposição.

O formulário atual exige respostas e e-mail; nome e telefone são opcionais. Entradas incompletas recebem 422 e opções de outra pergunta são recusadas. O fluxo legado pode gerar `sem_faixa` se o cadastro não cobrir a soma.

Lead é um contato; conclusão é um quiz respondido; clique é uma saída; compra é um pedido confirmado. Esses fatos são medidos separadamente.

## 4. Todos os parâmetros do texto original

```text
https://suaempresa.com/quiz/encontre-sua-solucao/?v=B2&fmt=video&seg=escalando&src=meta&med=cpc&cpg=qz_escalando_oct26&ctv=vsl_47s_cta_comprar&utm_source=meta&utm_medium=cpc&utm_campaign=qz_escalando_oct26&utm_content=vsl_47s_cta_comprar&utm_term=publico_escalando
```

O domínio é ilustrativo.

| Parâmetro | Função |
|---|---|
| `v` | Versão publicada escolhida pelo link |
| `fmt` | Formato configurado naquela versão |
| `seg` | Segmento de público cadastrado |
| `src` | Fonte interna |
| `med` | Meio interno |
| `cpg` | Campanha interna |
| `ctv` | Criativo |
| `utm_source` | Fonte no padrão de analytics |
| `utm_medium` | Meio no padrão de analytics |
| `utm_campaign` | Campanha no padrão de analytics |
| `utm_content` | Conteúdo/criativo no padrão de analytics |
| `utm_term` | Termo ou público quando utilizado |

Parâmetros internos permitem controlar a experiência e organizar relatórios próprios. UTMs permitem comunicar a origem a ferramentas externas **quando houver integração**. Uma URL não instala analytics, não dispara CAPI e não cria tags no CRM sozinha.

O código usa parâmetros internos quando a UTM equivalente está ausente. Valores diferentes enviados em ambas as formas continuam identificáveis; sua preservação passou nos testes locais. Marcadores de entrada são limitados a 200 bytes UTF-8 por valor para caberem na sessão do navegador.

Slugs devem ser legíveis, como `encontre-sua-solucao`, sem expor IDs numéricos como endereço de campanha. Mesmo slug ajuda a organizar URLs, mas estabilidade de sessão e retargeting dependem da implementação. `rel="canonical"` somente aponta entre páginas equivalentes; um redesign diferente não deve apontar automaticamente para a página antiga como se fosse o mesmo conteúdo.

## 5. Formatos e personalização: todos permanecem no escopo

| Formato | URL | Experiência desejada | Estado |
|---|---|---|---|
| Texto | `fmt=text` | Headline, subheadline e perguntas sem vídeo | Integrado e testado localmente |
| Vídeo | `fmt=video` | VSL antes da primeira pergunta | Componente integrado; mídia real necessária |
| Híbrido | `fmt=hybrid` | Texto com vídeo curto | Componente integrado; mídia real necessária |
| Agente de IA | `fmt=ai` ou `fmt=ai_agent` | Conversa interativa substituindo perguntas fixas | Pendente; alias e aviso não constituem agente funcional |
| Calculadora | `fmt=calc` | Entradas numéricas e cálculo explicado | Rota e cálculo no servidor integrados e testados |

VSL de 30–60 segundos e híbrido de 15 segundos são recomendações editoriais do texto fornecido; não são limites técnicos já impostos.

O segmento pode personalizar headline, subheadline, vídeo, título/descrição do resultado e rótulo do botão. As respostas continuam determinando a indicação oficial, e o texto personalizado precisa corresponder à oferta calculada.

A calculadora precisa de fórmula, unidades e hipóteses explícitas. Uma estimativa de ROI não comprova retorno real. O código local aceita somente aritmética limitada sobre entradas declaradas.

O agente de IA precisa conduzir a conversa, concluir a recomendação entre as duas ofertas e registrar o percurso. Avisar indisponibilidade é comportamento provisório, não conclusão dessa capacidade. Provedor, conteúdo e integração estão pendentes. Gastos reais com API dependem da palavra do mantenedor.

## 6. Sessão: preservar o objetivo, corrigir o exemplo

O cookie atual `quiz_session` é assinado pelo Django, dura sete dias e usa `HttpOnly` e `SameSite=Lax`. Guarda sessão, versão, site e UTM por slug. Assinatura inválida não é aceita como conteúdo confiável.

O exemplo fornecido que escreve JSON diretamente em `document.cookie` não pode substituir esse cookie. A continuidade será feita aproveitando a sessão assinada. Campos ocultos e armazenamento no navegador podem ajudar a tela, mas não passam a decidir versão, pontos ou resultado.

O contexto acompanha formulário, resultado, saída e evento de conclusão. Participações de campanhas distintas são separadas, inclusive em abas diferentes. Refazer cria nova participação da mesma experiência e origem, preservando as conclusões anteriores. A sessão guarda até oito tentativas por quiz e retira tentativas antigas se atingir o limite de tamanho do cookie; uma tentativa retirada fica indisponível e não herda outra campanha. O retorno de compra ainda depende de integração externa.

## 7. Duas ofertas e checkout externo

O mantenedor enviará os dois links reais **depois de o quiz estar testado e pronto**. Até lá, cada `checkout_url` fica `null`. Não inventar links nem cobrar alguém em teste.

O código integrado mostra a demonstração da oferta indicada quando o endereço está `null`. A conexão posterior dos dois destinos preserva perguntas, pontuação, mensagens e histórico. Esses caminhos passaram nos testes locais; não são checkouts reais ativos.

É possível abrir um checkout externo e passar parâmetros aceitos por ele, preservando a consulta que o link original já possua. O trabalho local de saída evita enviar nome, telefone e e-mail pela URL. A compra pode ser correlacionada por uma identificação opaca da tentativa quando o checkout devolver essa informação.

**Limite real:** o quiz não consegue manipular livremente os campos ocultos de um formulário em outro domínio. Preenchimento de campos e retorno de pedidos dependem de parâmetros suportados, API, webhook ou mecanismo equivalente do checkout.

Sem cooperação do checkout, o clique pode ser medido; pagamento, reembolso, cancelamento e compra posterior não podem ser confirmados automaticamente com confiabilidade. Isso depende do provedor escolhido, não de uma mudança no texto do botão.

## 8. Editor existente e formato para a outra IA

O código atual possui painel em `/admin/conteudos/quiz/` e endpoints internos de listar, rascunhar e publicar quizzes. A API privada exige autenticação configurada; não é uma API pública para visitantes.

O rascunho atual usa `{title, questions, bands}`. Publicar cria uma versão `editor-...` e desativa as anteriores. Esse comportamento precisa conviver com versões direcionadas A/B1/B2 ativas simultaneamente; o editor básico **não é o estúdio completo**.

O estúdio desejado inclui versões, formatos, segmentos, duas ofertas, importação, duplicação, prévias isoladas, geração de links e leitura do desempenho pelo site. Essas capacidades continuam no escopo.

### Documento de conteúdo

O importador local usa `quiz-low-ticket/2`, diferente do rascunho simples do editor. Exemplo mínimo completo, apenas didático:

```json
{
  "formato": "quiz-low-ticket/2",
  "quiz": {"slug": "encontre-sua-solucao", "title": "Encontre sua solução"},
  "ofertas": [
    {"id": "oferta-inicial", "nome": "Oferta inicial — exemplo", "checkout_url": null},
    {"id": "oferta-avancada", "nome": "Oferta avançada — exemplo", "checkout_url": null}
  ],
  "versoes": [{
    "key": "B2",
    "default_format": "text",
    "formats": {
      "text": {"headline": "Descubra seu próximo passo", "subheadline": "Responda ao diagnóstico."}
    },
    "segments": {
      "iniciante": {
        "headline": "Encontre um ponto de partida",
        "subheadline": "Para quem está começando.",
        "video_url": null,
        "results": {
          "base": {"title": "Comece pela base", "description": "Seu próximo passo.", "botao_rotulo": "Conhecer a oferta inicial"}
        }
      }
    },
    "perguntas": [{
      "id": "momento",
      "texto": "Qual é seu momento?",
      "opcoes": [
        {"id": "inicio", "texto": "Estou começando", "pontos": 0},
        {"id": "avanco", "texto": "Já tenho experiência", "pontos": 2}
      ]
    }],
    "faixas": [
      {"key": "base", "title": "Comece pela base", "description": "Fortaleça os primeiros passos.", "min_score": 0, "max_score": 1, "oferta_id": "oferta-inicial", "botao_rotulo": "Conhecer a oferta inicial"},
      {"key": "avanco", "title": "Avance", "description": "Desenvolva o que começou.", "min_score": 2, "max_score": 2, "oferta_id": "oferta-avancada", "botao_rotulo": "Conhecer a oferta avançada"}
    ]
  }]
}
```

Identificadores são legíveis e sem espaços. A versão aceita A, B1, B2 e equivalentes. No importador local, reimportar documento idêntico não muda conteúdo; alterar perguntas ou mensagens exige nova chave de versão. Conectar os links reais é uma operação separada. Não executar o importador como se já estivesse integrado à base atual.

Para os demais formatos:

- `video` e `hybrid`: headline, subheadline e `video_url` real reproduzível. Roteiros ficam fora do JSON. Sem mídia real, não inventar URL nem ativar esse formato no conteúdo importável.
- `ai`: headline, subheadline e `instructions` com abordagem, percurso e critérios de conclusão entre as duas ofertas; execução ainda pendente.
- `calc`: headline, subheadline e `calculator` com `inputs` (`key`, `label`, `default`, `min`, `max`), `expression` e `result_label`. O avaliador local aceita soma, subtração, multiplicação e divisão, sem funções externas.
- `segments`: alterações dos textos e vídeo; resultados indexados pela chave da faixa. A oferta permanece ligada à pontuação.

### Pedido reutilizável para a outra IA

> Crie conteúdo para um quiz low ticket que indique exatamente uma de duas ofertas externas. Ainda não defini tema, público ou ofertas: proponha três combinações concretas, com público, problema, promessa realista e duas ofertas complementares, e explique sua recomendação e hipóteses. Após definir a combinação, entregue resumo das ofertas e público, roteiro completo e JSON puro no formato quiz-low-ticket/2 mostrado neste manual. Use um slug estável e versões A, B1, B2. Explique fora do JSON o que muda entre versões e qual hipótese cada campanha direcionada compara; não criar sorteio ou percentuais de tráfego. Inclua perguntas, opções com pontos, faixas cobrindo todas as pontuações possíveis e vínculo de cada faixa a uma das duas ofertas. Entregue headline, subheadline, resultado e CTA, personalizados para os segmentos propostos. Prepare roteiros de vídeo e híbrido, instruções de conversa por IA e calculadora com fórmula, unidades e hipóteses quando fizer sentido. Sem arquivo real de vídeo, entregue roteiro fora do JSON; não invente links. Mantenha os dois checkout_url como null. Separe JSON importável, notas, roteiros, sugestões de campanha e dependências. Inclua exemplos de respostas, soma e oferta esperada para conferirmos o comportamento. Não inclua credenciais, dados pessoais ou promessa de retorno garantido.

## 9. Escala, tracking, CRM e BI

Nomes como `qz_escalando_oct26` e `vsl_47s_cta_comprar` são exemplos úteis do texto original. Sua grafia consistente permite agrupar a campanha. Não foi criada uma convenção permanente adicional.

Quatro criativos × dois formatos × três segmentos geram 24 combinações por versão. Gerar URL não cria criativo, campanha ou formato ausente. O gerador local precisa apontar somente para experiências configuradas.

| Camada contemplada | Capacidade pretendida | Dependência |
|---|---|---|
| Builder próprio | Resolver versão/formato/segmento e aplicar personalização | Integrar arquivos locais ao runtime e editor |
| GA4 | UTMs, eventos e dimensões de versão/formato/segmento | Propriedade e configuração de coleta |
| Meta CAPI | Eventos no servidor e deduplicação | Credenciais, integração e prova de entrega |
| TikTok Events API | Eventos e contexto de versão/formato/criativo | Credenciais, integração e prova de entrega |
| Klaviyo / ActiveCampaign | Contatos, tags, origem, resultado e histórico | Contas e conexão; envio explícito |
| Looker / Metabase | Campanhas, coortes, pedidos, receita e LTV | Fonte de dados e dashboard |
| Checkout externo | Contexto aceito e retorno dos estados do pedido | Links, provedor e integração |
| Retargeting | Participantes de B2 que ainda não compraram | Eventos, identidade compatível e exclusão de compradores confirmados |

Nenhuma dessas integrações foi descartada. Credenciais ou conteúdo ausentes são dependências, não impossibilidade. Não é necessário contratar todos os serviços para preparar o quiz, e nenhum segredo deve entrar no documento ou na URL.

Cada ferramenta precisa receber as propriedades explicitamente conforme sua interface. Identificadores permitem deduplicar novas tentativas e, quando aplicável, o mesmo evento enviado pelo navegador e servidor. Preferências e consentimento do produto precisam acompanhar o uso real dos dados; este manual não inventa política jurídica.

### Eventos internos atuais

[quiz.completado.v1](../../contracts/eventos/quiz.completado.v1.json) exige site, slug, faixa, score e lead. O contrato **permite `version_key` opcional**, e a view atual o emite. Também permite `utm`. A antiga afirmação de que não existe `version_key` está superada. O contrato atual **não permite `context`**; integrar o contexto novo requer compatibilizar produtores e consumidores.

Submissão e outbox são gravadas na mesma transação. O relay entrega antes de marcar publicado e mantém tentativas pendentes em caso de falha. Telemetria registra visualização, pergunta, opção e abandono; não substitui a conclusão no banco.

## 10. Melhoria contínua diária e por campanha

O objetivo continua sendo acompanhar a jornada completa e criar versões melhores mantendo a escolha por URL. A análise diária está no escopo; **nenhum novo agendamento foi criado nesta atualização**.

| Medida | Significado | Dependência |
|---|---|---|
| Visitas elegíveis | Participações iniciadas sem contar refresh como outra pessoa | Sessão/experiência e identificação de tráfego de teste |
| Avanço e abandono | Perda em cada etapa | Telemetria |
| Conclusões / visitas | Conversão do quiz | Conclusão ligada à entrada |
| Saídas / conclusões | Uso do botão da oferta | Saída rastreada |
| Compras / visitas | Conversão comercial | Compra confirmada |
| Receita por visitante | Receita atribuída / visitantes elegíveis | Pedidos, moeda, período e reembolsos |
| LTV por versão/coorte | Valor acumulado dos clientes daquele grupo | Histórico de compras, identidade e janela de observação |

A análise agrupa dia, versão, formato, segmento, fonte, meio, campanha e criativo. Dia/fuso, denominador e janela de atribuição precisam estar explícitos. O relatório local ainda não recebe receita/LTV automaticamente.

Ana identifica perdas e prepara B3 para uma mudança concreta: headline, CTA, vídeo, ordem ou extensão. Depois observa o desempenho da nova campanha. Não há garantia de melhoria diária nem de resultado financeiro.

Retargeting por “viu B2 e não comprou” depende de conhecer compras. Comparar lances por formato permanece no escopo analítico; executar mudanças que gastem dinheiro real exige a palavra do mantenedor.

## 11. Conferência integral do texto fornecido

| Recomendação original | Tratamento |
|---|---|
| Base estável, slug legível, sem ID numérico | Mantida |
| Mesmo slug para A/B1/B2/C, inclusive quiz mais curto | Mantida; campanhas direcionadas |
| Todos os parâmetros internos e UTMs | Mantidos, incluindo meio e termo |
| Duplas de parâmetros e Variable Logic | Mantidas no builder próprio, com envio explícito às ferramentas |
| Headline, VSL, CTA e resultado por segmento | Mantidos |
| Contexto pelas etapas, resultado e checkout | Mantido; trecho externo depende do provedor |
| Cookie/localStorage/hidden fields | Objetivo mantido; exemplo corrigido para sessão assinada |
| Texto, vídeo, híbrido, AI Agent e calculadora | Todos mantidos |
| Naming e centenas de combinações | Mantidos como organização e gerador de campanhas |
| GA4, Meta CAPI e TikTok | Mantidos |
| Klaviyo, ActiveCampaign, Looker e Metabase | Mantidos |
| LTV, receita por visitante, retargeting e lances por formato | Mantidos, com dados de compra e autorização para gastar |
| Redesign exige outro slug com canonical para original | Corrigido: pode ser outra versão; canonical só entre conteúdos equivalentes |
| `v` sozinho cria A/B confiável | Corrigido: comparação direcionada não prova causalidade |
| Preencher formulário externo via JS do quiz | Exige mecanismo oferecido pelo checkout |
| Plataformas comerciais citadas como builder | Capacidades contempladas no Crivo; não significa contratar todas |

Nenhuma capacidade foi omitida só porque exige implementação. Os limites reais são cooperação de serviços externos, diferenças entre ferramentas e ausência de garantia de resultado comercial.

## 12. Documento no projeto e documento no site

Conforme [documentos.py](../../services/admin/apps/core/documentos.py), o site lê os documentos da tabela `Documento`. A pasta `documentos/` é semente de migrações e não sincroniza o texto automaticamente a cada deploy.

Editar o Markdown registra o trabalho no projeto; não comprova atualização do documento existente no site. Esse documento tem editor e histórico próprios em `/admin/documentos/o-crivo-explicado-do-zero`. A revisão deve preservar a versão anterior e a visibilidade existente. O documento observado no painel é **privado para administradores**.

A regra de publicação já dada pelo mantenedor continua: backup antes; se a prova falhar ou o site cair, voltar o código à última versão aprovada, sem restaurar o banco automaticamente.

## 13. Prova e próximo trabalho

A prova documental confere conteúdo, referências, exemplo JSON e renderização. A integração foi submetida à suíte completa do quiz e aos testes correspondentes do painel. O endereço público do código novo ainda depende de publicação.

O Makefile atual tem `test`, `lint` e `type`; `ci` consta em `.PHONY`, mas não possui receita naquele arquivo. Portanto, `make ci` não comprova que toda a suíte executou.

A continuação precisa publicar a integração testada, conferir a jornada pública e receber o conteúdo real. Permanecem o estúdio visual completo, a conversa por IA e as conexões externas de marketing, relacionamento e compra. Depois do teste do quiz, o mantenedor entrega os dois links, que serão conectados e verificados. Integrações de compra e medição têm provas próprias.

Entrega pronta do site significa prova automática aprovada e endereço abrindo. Arquivos presentes ou URL antiga respondendo não comprovam a nova experiência.

## 14. Fontes atuais

- [Modelos](../../services/quiz/apps/quiz/models.py), [views](../../services/quiz/apps/quiz/views.py), [rotas](../../services/quiz/config/urls.py) e [tarefas](../../services/quiz/apps/quiz/tasks.py).
- [Editor de quiz](../../services/quiz/apps/quiz/editor.py) e [painel de conteúdos](../../services/admin/apps/core/conteudos.py).
- [Migração do rascunho](../../services/quiz/apps/quiz/migrations/0006_quizdraft.py) e [migração de experiências](../../services/quiz/apps/quiz/migrations/0008_experiencias_direcionadas.py).
- [Direcionamento local](../../services/quiz/apps/quiz/direcionadas.py), [experiências locais](../../services/quiz/apps/quiz/experiencias.py) e [destinos locais](../../services/quiz/apps/quiz/destinos.py).
- [Importador de conteúdo local](../../services/quiz/apps/quiz/conteudo.py) e [exemplo dos testes](../../services/quiz/tests/test_importar_quiz.py).
- [Gerador de links local](../../services/quiz/apps/quiz/management/commands/gerar_links_quiz.py), [conexão local de checkouts](../../services/quiz/apps/quiz/management/commands/conectar_checkouts.py), [relatório local](../../services/quiz/apps/quiz/campanhas.py).
- [Contrato de conclusão](../../contracts/eventos/quiz.completado.v1.json), [Makefile](../../services/quiz/Makefile).
- [Armazenamento/renderização documental](../../services/admin/apps/core/documentos.py) e [editor de documentos](../../services/admin/apps/core/editor_de_documentos.py).

## Histórico do manual anterior

<details>
<summary>Texto anterior preservado para consulta histórica; as decisões e o estado de 02/10 acima prevalecem.</summary>

**Atenção histórica:** as seções abaixo descrevem a base anterior, com seleção por peso, seed e afirmações hoje superadas sobre editor e contrato. Não são instruções vigentes para os novos quizzes. Referências antigas removidas do projeto aparecem como nomes de arquivo, sem fingir que ainda são fontes disponíveis.

# Manual completo e didático para criar, publicar e operar um sistema de quizzes

Este manual explica o Crivo, a célula de quizzes deste projeto, para três pessoas:

- quem nunca criou um site e precisa operar um quiz;
- quem trabalha com campanhas e quer entender respostas, leads e origem;
- quem está começando em tecnologia e quer enxergar o que acontece nos bastidores.

Leia as etiquetas assim:

- **Confirmado no sistema**: está demonstrado no código, no teste ou no contrato citado.
- **Explicação simplificada**: é uma tradução didática de um comportamento confirmado.
- **Não identificado no código analisado**: não encontramos a capacidade ou a regra nas fontes examinadas. Não use essa frase como instrução.

O manual usa Ana como personagem fictícia. Ana representa uma operadora iniciante. A história ajuda a entender, mas as instruções reais sempre vencem a história.

## Antes de começar

### A resposta curta

Um quiz é uma página que apresenta perguntas, recebe escolhas, calcula uma pontuação no servidor, encontra uma faixa de resultado, registra uma submissão e pode encaminhar a pessoa para um próximo passo.

**Confirmado no sistema:** o Crivo expõe páginas HTML, não uma API JSON pública. A célula publica páginas em `/quiz/*` segundo constituicoes/AGENTS.quiz.md (referência histórica) e as rotas reais estão em [services/quiz/config/urls.py](../../services/quiz/config/urls.py).

**Explicação simplificada:** pense em uma recepcionista. Ela faz perguntas, organiza as respostas, identifica o perfil da pessoa e entrega uma orientação. O Crivo faz isso com regras gravadas no banco.

### O que Ana quer fazer

Ana tem uma pequena empresa. Ela quer atrair visitantes, entender o perfil deles, mostrar um resultado, pedir um contato e comparar campanhas. Ela não quer que o visitante escolha a própria pontuação nem que a origem do anúncio desapareça no caminho.

O quiz ajuda a organizar esse atendimento. Ele não substitui uma equipe comercial, não cria automaticamente uma oferta e não prova sozinho que uma campanha vendeu.

### O mapa geral

```mermaid
flowchart LR
    V[Visitante] --> P[Página do quiz]
    P --> Q[Perguntas e opções]
    Q --> S[Pontuação no servidor]
    S --> R[Faixa e resultado]
    R --> L[Lead e submissão]
    L --> E[Evento de conclusão]
```

**Pergunta de verificação:** em que momento a nota é calculada?

**Resposta:** depois que o servidor recebe as escolhas, nunca confiando em uma nota enviada pelo navegador.

## 1. O problema que o quiz resolve

Um formulário comum coleta campos. Um quiz coleta escolhas que podem ser comparadas com regras. Isso permite orientar a pessoa para um resultado diferente conforme suas respostas.

Imagine uma atendente que pergunta:

1. Qual é seu maior desafio?
2. Quanto tempo você tem?
3. Qual é sua experiência?

Com essas pistas, ela indica um próximo passo. O sistema transforma a conversa em dados: cada pergunta tem opções, cada opção tem pontos e cada intervalo de pontos corresponde a uma faixa.

### O que o quiz faz

**Confirmado no sistema:** o modelo tem `Quiz`, `QuizVersion`, `Question`, `Option`, `ResultBand`, `Submission`, `OutboxEvent` e `TelemetryEvent` em [models.py](../../services/quiz/apps/quiz/models.py).

**Explicação simplificada:** cada modelo é uma peça da ficha de atendimento. O quiz é a campanha, a versão é uma variação, a pergunta é uma etapa, a opção é uma escolha, a faixa é a classificação e a submissão é o registro final.

### O que o quiz não resolve sozinho

**Não identificado no código analisado:** painel administrativo para uma pessoa leiga criar e editar quizzes. A fonte observada fornece o comando de seed e o banco, mas não foi encontrada uma tela de administração do Crivo.

**Confirmado no sistema:** o Crivo não consome APIs de outras células. Sua constituição diz `Consome: nada`. Ele armazena o destino do botão como texto opaco e não sabe o que é checkout.

**Explicação simplificada:** o quiz pode apontar para um endereço que outra parte da plataforma entende. Ele não cria o produto, não cobra o cartão e não entrega o acesso.

### Exercício mental

Escolha uma empresa real e complete a frase: “Depois de responder, a pessoa precisa descobrir ______”. Se a resposta for uma oferta, uma aula ou uma conversa, isso é o próximo passo. Não transforme esse próximo passo em uma responsabilidade que o código do quiz não possui.

## 2. Vocabulário essencial

| Termo | Definição simples | Analogia | O que o sistema faz | Erro comum |
|---|---|---|---|---|
| Site | Um host atendido pelo quiz | Uma loja | Resolve o host para um `site_id` local | Usar o ID de outro site |
| Página | Endereço que o navegador abre | A porta da loja | Renderiza formulário ou resultado | Testar apenas a rota interna |
| Quiz | Campanha completa | O projeto da loja | Agrupa versões | Confundir com uma pergunta |
| Pergunta | Texto que pede uma escolha | Uma pergunta da atendente | Pertence a uma versão e tem ordem | Misturar perguntas de versões |
| Opção | Resposta possível | Uma resposta na ficha | Pertence a uma pergunta e tem pontos | Enviar um ID de outra pergunta |
| Resposta | Escolha feita pelo visitante | O que a pessoa disse | É guardada em `answers` | Mandar a pontuação no POST |
| Pontuação | Soma dos pontos das opções | Uma planilha de pontos | É calculada no servidor | Confiar no navegador |
| Faixa | Intervalo de pontuação | Uma categoria | Escolhe título, descrição e botão | Criar buracos ou sobreposição |
| Resultado | O que a faixa apresenta | A orientação da atendente | Mostra a faixa ligada à submissão | Achar que é uma venda |
| CTA | Botão do próximo passo | “Vá até este balcão” | Vem da faixa | Usar destino sem rótulo |
| Lead | Contato informado | A ficha da pessoa | Guarda e-mail e campos opcionais | Tratar como cliente pagante |
| Sessão | Identificação do atendimento | Uma senha de fila | Cookie assinado com UUID | Trocar de versão no meio |
| Versão | Variação do mesmo quiz | Outra vitrine | Tem perguntas, peso e faixas próprias | Editar a versão errada |
| Tráfego | Pessoas que chegam | Fluxo na calçada | Não é uma tabela própria nesta célula | Confundir visitas com leads |
| Campanha | Esforço para atrair pessoas | Uma ação de divulgação | É representada pelo quiz e UTMs | Achar que o quiz cria anúncios |
| UTM | Marcador na URL de origem | Etiqueta em uma encomenda | É capturada na entrada e preservada | Ler a UTM apenas na conclusão |
| Telemetria | Eventos de uso antes da submissão | Contador de passos | Registra visualização, clique e abandono | Tratar telemetria como lead |
| Banco de dados | Memória estruturada | Arquivo de fichas | Guarda configurações e submissões | Esperar que Redis seja o banco principal |
| Redis | Serviço de mensagens rápidas | Uma esteira | Recebe streams de telemetria e eventos | Assumir que ele substitui a submissão |
| Evento | Mensagem sobre algo ocorrido | Um aviso | Publica conclusão em formato definido | Inventar campos fora do contrato |
| Outbox | Registro pendente de entrega | Caixa de correspondência | Guarda o evento na transação local | Marcar como entregue antes de publicar |
| Relay | Processo que entrega eventos | Entregador | Publica pendências no stream | Achar que o navegador entrega o evento |
| Stream | Sequência de mensagens | Fila de cartas | Transporta mensagens no Redis | Confundir com tabela de respostas |
| Contrato | Formato combinado | Formulário padronizado | Define nome e campos do evento | Alterar o payload sem rito |
| JSON | Texto estruturado em chaves e valores | Formulário digital | Transporta metadados e contrato | Enviar texto fora do formato |
| Servidor | Processo que executa regras | A retaguarda da loja | Valida, soma e grava | Deixar decisão importante no cliente |
| Navegador | Programa do visitante | A pessoa diante do balcão | Exibe HTML e envia escolhas | Considerá-lo confiável |
| Worker | Processo que executa tarefas | Funcionário da retaguarda | Drena telemetria e roda o relay periódico | Rodar o site sem o worker e esperar entrega |

**Até aqui, pense assim:** a pessoa preenche uma ficha em uma loja.

**Na prática, o sistema faz isto:** o navegador envia escolhas; o Django valida, calcula e grava usando os modelos da célula quiz.

## 3. Como o visitante enxerga o quiz

### Passo 1. Chegada

Ana clica em um anúncio com uma URL como:

```text
https://exemplo/quiz/crivo/?utm_source=instagram&utm_medium=paid&utm_campaign=campanha_maio
```

**Confirmado no sistema:** a view aceita chaves que começam com `utm_`, limita cada valor a 200 caracteres, guarda no máximo oito chaves e salva os nomes sem o prefixo `utm_` em [views.py](../../services/quiz/apps/quiz/views.py).

**O que Ana vê:** a página do quiz.

**O que o sistema registra:** a UTM entra no cookie de sessão e depois na submissão.

**Se der errado:** um slug inexistente ou quiz inativo resulta em 404. Escolha um slug existente e ativo.

### Passo 2. Escolha da versão

```mermaid
flowchart LR
    A[Entrada] --> B{Cookie válido?}
    B -- não --> C[Criar sessão]
    B -- sim --> D[Recuperar sessão]
    C --> E[Escolher versão por peso]
    D --> F[Manter version_id]
    E --> G[Mostrar perguntas]
    F --> G
```

**Confirmado no sistema:** versões ativas com peso maior que zero participam do corte. O código soma os pesos, usa o UUID da sessão para obter um ponto e percorre as versões ordenadas por ID. Isso está em `escolher_versao()`.

**Explicação simplificada:** não é um sorteio novo a cada clique. A sessão recebe uma versão e o cookie guarda essa escolha.

### Passo 3. Respostas

O formulário apresenta uma pergunta por etapa no navegador. O HTML usa campos `radio`, exige escolha para cada pergunta e depois mostra os campos de lead.

**Confirmado no sistema:** o template [formulario.html](../../services/quiz/apps/quiz/templates/quiz/formulario.html) mostra perguntas, opções, e-mail obrigatório, nome opcional e telefone opcional. O botão final diz “Ver resultado”.

**O que Ana vê:** uma pergunta, opções e o botão “Continuar”; no final, os dados de contato e “Ver resultado”.

**O que pode dar errado:** sem resposta, o servidor devolve status 422 e a mensagem “responda todas as perguntas”. Sem e-mail, devolve 422 e “e-mail é obrigatório”. Corrija o campo e envie novamente.

### Passo 4. Conclusão e resultado

Depois do POST, o servidor grava a submissão e redireciona para uma URL com `?lead=<UUID>`.

**Confirmado no sistema:** o resultado localiza a submissão pelo UUID, pelo quiz e pelo `site_id`. Um lead inválido ou de outro quiz resulta em 404.

**O que Ana vê:** título da faixa, descrição e, quando configurado, um botão.

**O que pode dar errado:** uma pontuação sem faixa gera `result_key = "sem_faixa"`; a tela pode não ter descrição nem botão. Corrija as faixas antes de publicar.

### Passo 5. Próximo passo

**Confirmado no sistema:** o botão é da `ResultBand`. Destino e rótulo são gravados juntos e a restrição do banco rejeita apenas um dos dois.

**Explicação simplificada:** uma pessoa iniciante e uma pessoa avançada podem receber convites diferentes. O quiz apenas apresenta o link plantado pelo operador.

**Não identificado no código analisado:** venda concluída, pagamento aprovado ou matrícula criada após o clique.

### Narrativa completa de Ana

Ana chega com uma UTM, recebe a versão original, responde às três perguntas, informa o e-mail e envia. O servidor soma os pontos, encontra a faixa “Você já tem base”, grava as respostas, grava a origem e apresenta o botão daquela faixa. Quando Ana clica, sai da responsabilidade do quiz.

**Perguntas de revisão:**

1. O botão aparece antes ou depois da faixa?
2. Quem decide o resultado?
3. O clique no CTA prova uma compra?

**Respostas:** depois da faixa; o servidor; não.

## 4. Como o quiz é montado

### A receita de cozinha

Pense em uma receita:

1. o quiz é o prato completo;
2. a versão é uma variação da receita;
3. cada pergunta é uma etapa;
4. cada opção é uma escolha de ingrediente;
5. os pontos são pesos;
6. a faixa é o resultado final;
7. o CTA é o próximo prato servido.

### Exemplo completo do seed existente

**Confirmado no sistema:** o comando [seed_quiz.py](../../services/quiz/apps/quiz/management/commands/seed_quiz.py) cria um quiz com slug configurável, três perguntas e três opções por pergunta.

| Pergunta | Opção | Pontos |
|---|---|---:|
| Qual é o seu maior desafio hoje? | Não sei por onde começar | 0 |
| Qual é o seu maior desafio hoje? | Já comecei mas travei no meio | 5 |
| Qual é o seu maior desafio hoje? | Quero acelerar o que já funciona | 10 |
| Quanto tempo você tem disponível por semana? | Menos de 2 horas | 0 |
| Quanto tempo você tem disponível por semana? | Entre 2 e 5 horas | 5 |
| Quanto tempo você tem disponível por semana? | Mais de 5 horas | 10 |
| Como você descreveria sua experiência atual? | Iniciante | 0 |
| Como você descreveria sua experiência atual? | Intermediário | 5 |
| Como você descreveria sua experiência atual? | Avançado | 10 |

As faixas do seed são:

| Faixa | Pontuação | Rótulo do botão |
|---|---:|---|
| Você está começando | 0 a 9 | Começar pelo básico |
| Você já tem base | 10 a 19 | Destravar o próximo passo |
| Você está pronto para escalar | 20 a 30 | Quero escalar agora |

O destino do botão é argumento obrigatório do comando. O seed não fixa uma oferta porque o Crivo não conhece checkout.

### Pontuação linha por linha

Se Ana escolhe 5, 10 e 0:

```text
Pergunta 1: 5 pontos
Pergunta 2: 10 pontos
Pergunta 3: 0 pontos
Total: 5 + 10 + 0 = 15
Faixa encontrada: 10 a 19
Resultado: Você já tem base
```

### Por que o navegador não pode decidir a nota?

**Até aqui, pense assim:** o aluno entrega respostas e o professor corrige.

**Na prática, o sistema faz isto:** o navegador envia somente `option_id` por pergunta. O servidor procura a opção pertencente àquela pergunta e soma `Option.points`. Se o ID não pertencer à pergunta, a view retorna 404.

O navegador é útil para mostrar a tela, mas não é autoridade para nota, faixa ou submissão. Alterar HTML ou JavaScript não deve alterar a pontuação oficial.

## 5. Versões e divisão de tráfego

### Duas vitrines para a mesma loja

```mermaid
flowchart TD
    Q[Quiz crivo] --> A[Versão original]
    Q --> B[Versão dor-primeiro]
    A --> QA[Perguntas da original]
    B --> QB[Perguntas da dor-primeiro]
    QA --> R[Resultado]
    QB --> R
```

**Confirmado no sistema:** uma `QuizVersion` tem `key`, `weight` e `active`; perguntas e faixas pertencem à versão. O seed aceita `--variacao` com JSON próprio.

**Explicação simplificada:** Ana pode testar duas vitrines sem criar dois quizzes independentes.

| Versão | Descrição | Peso | Expectativa |
|---|---|---:|---:|
| original | Texto atual | 70 | Cerca de 70% |
| dor-primeiro | Aborda o problema antes | 30 | Cerca de 30% |

A expectativa não é uma garantia exata para poucas visitas. O corte usa o UUID da sessão, não o navegador escolhendo uma opção.

### Editar ou criar outra versão

Edite a versão existente quando a identidade da experiência não precisa ser comparada com uma anterior. Crie outra versão quando a pergunta, a promessa ou a estrutura que você quer medir deve continuar separada.

**Não identificado no código analisado:** uma interface visual para fazer essa edição. O caminho confirmado é o comando de seed e seus argumentos.

### O que ainda não pode ser prometido

**Confirmado no sistema:** a versão é preservada na sessão, na telemetria e na submissão.

**Não identificado no contrato de conclusão analisado:** `version_key` dentro de `quiz.completado.v1`. O contrato exige `site_id`, `quiz_slug`, `result_key`, `score` e `lead`, mas não exige a versão. Portanto, não instrua alguém a comparar versões usando esse evento como se a versão estivesse garantida no payload. Para analisar versões, use as submissões ou a telemetria enquanto essa fonte estiver acessível.

## 6. Sessão estável e continuidade

### A ficha de atendimento

```mermaid
sequenceDiagram
    participant N as Navegador
    participant S as Servidor
    participant B as Cookie assinado
    N->>S: Abre o slug e UTMs
    S->>S: Cria session_id e escolhe versão
    S->>B: Grava versão, site e UTM
    B-->>N: Cookie quiz_session
    N->>S: Envia respostas
    S->>B: Reusa a mesma ficha
    S-->>N: Resultado da submissão
```

**Confirmado no sistema:** o cookie se chama `quiz_session`, é assinado pelo Django, dura sete dias, é `HttpOnly`, usa `SameSite=Lax` e guarda `session_id`, `version_id`, `version_key`, `site_id` e UTM por slug.

Se Ana atualizar a página, o cookie válido mantém a versão. Se fechar e voltar dentro do prazo, o sistema tenta reutilizar a mesma ficha. Se a assinatura for inválida, o cookie é ignorado e uma nova sessão pode ser criada.

**Explicação simplificada:** a sessão é uma senha de atendimento. Ela evita misturar respostas da vitrine A com a vitrine B.

**Pergunta de verificação:** o que acontece se a versão salva ficar inexistente ou inválida? O sistema resolve uma nova versão para aquela sessão, porque a versão recuperada deixa de ser utilizável.

## 7. Perguntas, respostas e pontuação

### O caminho confiável

1. A versão determina quais perguntas existem.
2. As perguntas são ordenadas por `order`.
3. Cada pergunta determina suas opções.
4. Cada opção tem `points` no banco.
5. O POST envia a escolha de cada pergunta.
6. O servidor busca a opção dentro da pergunta.
7. O servidor soma os pontos.
8. A soma encontra uma faixa.

### Entrada inválida

| Situação | Resposta do sistema | Ação do operador |
|---|---|---|
| E-mail vazio | 422 e mensagem de e-mail obrigatório | Preencher o e-mail |
| Pergunta sem escolha | 422 e mensagem para responder tudo | Escolher uma opção |
| Opção de outra pergunta | 404 | Corrigir o formulário ou a tentativa de adulteração |
| Quiz ou site inexistente | 404 | Conferir host, slug e seed |
| Nenhuma versão ativa | 404 | Ativar uma versão com peso maior que zero |
| Lead inválido na URL | 404 | Abrir o resultado por um link gerado pelo sistema |
| Pontuação sem faixa | Resultado com `sem_faixa` | Corrigir intervalos antes de publicar |

Uma opção inválida não deve ser “consertada” aceitando qualquer ID. O vínculo entre pergunta e opção é uma barreira contra respostas adulteradas.

## 8. Faixas de resultado e CTA

### Faixa como régua

Uma faixa tem `min_score`, `max_score`, `key`, título, descrição e campos do botão. O servidor busca a faixa cujo mínimo é menor ou igual à pontuação e cujo máximo é maior ou igual.

```text
0 ----- 10 ----- 20 ----- 30
| baixo | médio | alto   |
0 a 9   10 a 19 20 a 30
```

**Até aqui, pense assim:** uma régua classifica a pontuação.

**Na prática, o sistema faz isto:** `ResultBand` converte a soma em `result_key` e a tela usa essa faixa para mostrar descrição e botão.

Faixas sobrepostas podem fazer a primeira faixa encontrada vencer de modo inesperado. Faixas com buracos produzem `sem_faixa`. Antes de publicar, confira mínimo, máximo e fronteiras.

### Resultado não é venda

O resultado é uma classificação explicada. O CTA é um endereço e um rótulo. **Não identificado no código analisado:** prova de que o visitante clicou, comprou ou foi matriculado.

## 9. Captura de lead

### O cadastro

O template apresenta e-mail obrigatório, nome opcional e telefone opcional. A submissão guarda ainda quiz, versão, site, pontuação, faixa, respostas, UTM e data.

**Confirmado no sistema:** o evento de conclusão leva o e-mail e inclui nome e telefone somente quando foram informados. Leva também site, slug, faixa, score e UTM conforme o payload produzido em `views.formulario`.

**Não identificado no código analisado:** política de privacidade, consentimento jurídico ou prazo de retenção específico desta célula. Não invente uma regra legal a partir deste manual.

### Cuidado operacional

Um lead é um contato capturado. Não diga que ele é cliente, comprador ou pessoa consentida para qualquer uso. Use os dados apenas conforme as políticas reais do produto e as capacidades reais das outras células.

## 10. UTMs e campanhas

### A etiqueta na encomenda

```text
?utm_source=instagram&utm_medium=paid&utm_campaign=campanha_maio
```

**Confirmado no sistema:** o Crivo lê chaves com prefixo `utm_`, remove esse prefixo ao guardar e associa a origem ao cookie da sessão. Uma chegada posterior sem UTM não substitui uma UTM já guardada.

**Explicação simplificada:** a etiqueta acompanha a ficha de atendimento. Ela ajuda a perguntar “de onde veio esta pessoa?”.

UTM não prova sozinha que o anúncio causou a compra. Ela identifica a origem declarada na URL que chegou ao quiz. A análise de campanha precisa combinar origem, versão, submissões e a prova real de conversão, caso exista em outra célula.

## 11. O que acontece nos bastidores

### Submissão e outbox

```mermaid
flowchart LR
    F[Formulário] --> T[Transação do banco]
    T --> S[Submission]
    T --> O[OutboxEvent]
    O --> R[Relay]
    R --> X[Redis Stream]
    X --> C[Outras células]
```

**Confirmado no sistema:** a submissão e o `OutboxEvent` são criados na mesma transação. Depois do commit, o código agenda o relay. Existe também uma tarefa periódica de segurança a cada minuto.

**Até aqui, pense assim:** primeiro coloque a carta na caixa de correspondência; depois um entregador tenta levá-la.

**Na prática, o sistema faz isto:** registra o evento antes da entrega externa. O relay publica antes de marcar `published_at`. Se a publicação falhar, o evento continua pendente e pode ser tentado novamente.

### Contrato de evento

O contrato é um formulário padronizado. Ele exige o envelope `event`, `version`, `event_id`, `occurred_at` e `data`. Dentro de `data`, exige `site_id`, `quiz_slug`, `result_key`, `score` e `lead`.

**Importante:** o contrato observado não inclui `version_key` na conclusão. A telemetria inclui versão, mas o evento `quiz.completado.v1` não garante esse campo.

### Telemetria

O navegador emite `view_quiz`, `view_question`, `click_option` e `abandon`. O endpoint exige POST, valida tamanho, JSON, cookie de sessão, tipo de evento e metadados. O Redis recebe o envelope e uma tarefa drena o stream para `TelemetryEvent`.

Telemetria é descartável e não substitui a submissão. Se Redis perder o stream, a submissão completa continua no banco.

## 12. Separação entre componentes

```text
+------------------- Navegador -------------------+
| HTML, escolhas, JavaScript de passos e telemetria|
+-------------------------+------------------------+
                          |
                          v
+------------------- Célula quiz ------------------+
| Django, regras, sessão, pontuação e submissão    |
+-----------+------------------+------------------+
            |                  |
            v                  v
      Banco quiz          Redis Streams
      configurações       eventos rápidos
      e submissões              |
                               v
                       Outras células consumidoras

Checkout e pagamentos ficam fora do quiz. O CTA pode apontar para eles,
mas o Crivo não cria pedido nem confirma pagamento.
```

**Confirmado no sistema:** a constituição da célula proíbe acesso ao banco de outra célula e diz que o quiz não consome API de outra célula. O destino do botão é opaco.

## 13. Como publicar e testar

### O comando confirmado

O comando de seed exige host, site ID, nome do site e destino do botão:

```text
python manage.py seed_quiz --host exemplo.com --site-id site-exemplo --site-name "Exemplo" --slug crivo --destino-do-botao /checkout/curso-teste/
```

No PowerShell, use uma única linha ou o acento grave para continuação, conforme o ambiente. **Confirme o comando real no diretório `services/quiz` antes de executar**, porque a operação depende do ambiente Django e do banco da célula.

**Confirmado no sistema:** o seed é idempotente, cria ou atualiza dados fixos e pode receber `--variacao` para uma versão extra. Ele recusa slugs que conflitam com caminhos reservados.

**Não identificado no código analisado:** um botão de painel web para publicar. O processo confirmado é o comando de gerenciamento e a infraestrutura de deploy do projeto.

### Testes locais da célula

```text
cd services/quiz
python -m pytest -q
```

O Makefile também define:

```text
make ci
```

Esse alvo executa lint, tipagem quando configurada, testes e verificação de contrato. Rode a suíte no ambiente preparado da célula. Não declare publicação apenas porque o teste local passou.

### Teste de ponta a ponta para Ana

1. Abra o host correto.
2. Abra o slug sem e com UTM.
3. Confirme que as perguntas aparecem.
4. Recarregue e confirme que a versão não muda.
5. Tente enviar sem e-mail.
6. Tente enviar sem uma resposta.
7. Envie um caso válido.
8. Confirme o resultado e o botão da faixa.
9. Verifique a submissão e o evento conforme o acesso operacional permitido.

## 14. Diagnóstico de problemas

```mermaid
flowchart TD
    A[Sintoma] --> B[Hipóteses]
    B --> C[Verificar código, teste ou dado]
    C --> D[Corrigir a causa]
    D --> E[Repetir o cenário]
    E --> F{Passou?}
    F -- não --> B
    F -- sim --> G[Registrar a evidência]
```

| Sintoma | Verificação | Correção segura |
|---|---|---|
| 404 no quiz | Host, slug, ativo e `site_id` | Corrigir seed e caminho |
| 404 em `/healthz` ou `/static/` | Caminho isento do middleware | Não criar quiz com slug reservado |
| Versão muda no meio | Cookie, `version_id` e validade | Preservar a sessão e conferir versões ativas |
| Resultado sem botão | Faixa sem destino ou rótulo | Rodar seed com destino e rótulo coerentes |
| `sem_faixa` | Intervalos e score máximo | Cobrir toda a faixa possível |
| E-mail recusado | Campo obrigatório e CSRF | Corrigir formulário e token |
| Telemetria 401 | Cookie ausente ou inválido | Reabrir a página do quiz e tentar de novo |
| Telemetria 503 | Redis indisponível | Verificar Redis e worker; o lead válido continua no banco |
| Evento não aparece | Outbox pendente ou relay parado | Verificar worker e tarefa periódica |
| UTM desaparece | Cookie ou chegada inicial sem UTM | Testar a primeira URL com os parâmetros corretos |

### Quatro perguntas antes de mudar código

1. O sintoma ocorre na borda pública ou apenas em teste interno?
2. O dado foi gravado no banco?
3. O evento ficou na outbox?
4. A falha é do quiz ou de quem deveria consumir o evento?

## 15. Exercícios práticos

### Exercício 1. Desenhe a recepção

Desenhe cinco caixas: entrada, perguntas, pontuação, resultado e próximo passo. Em cada caixa, escreva uma entrada e uma saída.

### Exercício 2. Confira um caso

Use três perguntas com pontos 0, 5 e 10. Escolha uma opção de cada e calcule a soma manualmente. Depois diga em qual faixa ela cai.

### Exercício 3. Teste a sessão

Abra o quiz com `utm_source=instagram`, atualize a página e depois abra sem UTM. A origem esperada continua sendo a primeira, enquanto a sessão for válida.

### Exercício 4. Encontre o buraco

Crie faixas 0 a 9 e 11 a 20. O que acontece com 10? A resposta correta é `sem_faixa`. O exercício mostra por que fronteiras precisam ser conferidas.

### Exercício 5. Separe fato de explicação

Pegue uma frase do manual e localize a fonte. Se não encontrar fonte em código, teste ou contrato, troque por “Não identificado no código analisado”.

## 16. Checklist da operadora

- [ ] O host pertence ao site correto.
- [ ] O `site_id` local foi informado corretamente no seed.
- [ ] O slug não conflita com caminho reservado.
- [ ] Existe pelo menos uma versão ativa com peso maior que zero.
- [ ] Todas as perguntas têm opções.
- [ ] Os pontos das opções foram revisados.
- [ ] As faixas cobrem a pontuação possível sem sobreposição.
- [ ] Cada botão tem destino e rótulo juntos.
- [ ] O destino do botão foi escolhido para aquele site.
- [ ] O formulário exige e-mail e respostas.
- [ ] O teste com UTM preserva a origem.
- [ ] O teste de atualização mantém a versão.
- [ ] O resultado real aparece para um lead de teste.
- [ ] A submissão está no banco autorizado para consulta.
- [ ] Outbox e relay foram verificados quando a operação exige eventos.

## 17. Fontes conferidas

- Constituição da célula quiz (referência histórica removida)
- [Modelos do quiz](../../services/quiz/apps/quiz/models.py)
- [Views do quiz](../../services/quiz/apps/quiz/views.py)
- [Relay e telemetria](../../services/quiz/apps/quiz/tasks.py)
- [Comando de seed](../../services/quiz/apps/quiz/management/commands/seed_quiz.py)
- [Formulário](../../services/quiz/apps/quiz/templates/quiz/formulario.html)
- [Resultado](../../services/quiz/apps/quiz/templates/quiz/resultado.html)
- [Contrato `quiz.completado.v1`](../../contracts/eventos/quiz.completado.v1.json)
- [Testes de telemetria](../../services/quiz/tests/test_telemetria.py)
- [Testes de superfície pública](../../services/quiz/tests/test_superficie_publica.py)
- [Testes de pontuação e outbox](../../services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py)
- Lições da célula (referência histórica removida)

### Veredito para Ana

Ana agora consegue explicar o caminho inteiro sem atribuir ao quiz o que pertence a outra célula: a pessoa chega, recebe uma versão estável, responde, tem a pontuação calculada pelo servidor, recebe uma faixa, informa o contato, vê o CTA e deixa um evento pendente de entrega confiável. Onde o código não comprova um painel, uma regra legal, uma comparação de versões no evento ou uma venda, o manual diz isso explicitamente.


</details>
