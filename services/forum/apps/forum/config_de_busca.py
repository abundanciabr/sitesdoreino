"""COM QUAL CONFIGURAÇÃO O POSTGRESQL INDEXA E PROCURA — um lugar só.

**O problema, medido em `armadilhas/154`:** a configuração `portuguese` do
PostgreSQL é sensível a acento. Quem procura `chapeu` não acha `chapéu`. No
Brasil quase ninguém acentua ao buscar, então isso erra boa parte das buscas
reais **sem que ninguém perceba que errou** — a pessoa conclui que a resposta
não existe e pergunta de novo, que é exatamente o que o fórum existe para
evitar.

**A cura** é uma configuração de busca própria que passa o texto pela extensão
`unaccent` antes de radicalizar. Ela vive no BANCO, não no código: criar
extensão exige superusuário do PostgreSQL, poder que a célula não tem e não
deve ter (`infra/provisionar-forum.sh` é quem roda com ele).

**Por que o nome vem do env, e não cravado aqui.** Se o código exigisse a
configuração nova, uma célula que subisse antes de o banco ganhá-la quebraria
em TODA escrita e em TODA busca, com o deploy verde. Lendo do env com
`portuguese` como padrão, o pior caso é o comportamento de hoje: a busca
funciona, sensível a acento, e a tela avisa. É o mesmo desenho de
`armadilhas/097` — variável ausente não derruba página.

**As duas pontas mudam juntas, e é por isso que elas moram no mesmo arquivo:**
indexar com uma configuração e procurar com outra é a forma silenciosa de a
busca não achar o que existe.
"""

from __future__ import annotations

import os

# O que sempre existiu no PostgreSQL, e o que continua valendo se ninguém
# instalar nada.
CONFIG_PADRAO = "portuguese"

# O nome da configuração curada. Ele aparece em três lugares que TÊM de
# concordar: aqui, no SQL abaixo e no `infra/provisionar-forum.sh` — e existe um
# teste-guarda que compara os dois últimos com este arquivo.
CONFIG_SEM_ACENTO = "portugues_sem_acento"


def config_de_busca() -> str:
    """A configuração ativa. Lida no PONTO DE USO, nunca no import.

    Ler no import congelaria o valor para o processo inteiro e faria um teste
    que troca o env não ter efeito nenhum — o tipo de teste que passa verde
    provando o contrário do que afirma.
    """
    return (os.environ.get("FORUM_BUSCA_CONFIG") or "").strip() or CONFIG_PADRAO


def acento_importa() -> bool:
    """A busca de hoje diferencia `chapeu` de `chapéu`?

    A tela usa isto para avisar quando não acha nada. Quando a cura estiver
    instalada, o aviso some sozinho — e some por MEDIÇÃO do que está ativo, não
    porque alguém lembrou de apagar a frase.
    """
    return config_de_busca() == CONFIG_PADRAO


# ---------------------------------------------------------------------------
# O SQL DA CURA — a fonte única
# ---------------------------------------------------------------------------
# Roda como SUPERUSUÁRIO, no banco `forum_db`. Extensão é por banco, não por
# servidor. É idempotente de propósito: rodar duas vezes tem de ser inofensivo,
# porque quem o roda é uma pessoa colando um bloco, e colar duas vezes acontece.
#
# `unaccent` vem do pacote contrib, que já está na imagem oficial do PostgreSQL.
# A configuração COPIA a `portuguese` e troca o dicionário das palavras: primeiro
# tira o acento, depois radicaliza. As categorias `word`, `hword` e `hword_part`
# são as que carregam palavra de gente; número e URL não precisam.
SQL_DA_CURA = f"""\
CREATE EXTENSION IF NOT EXISTS unaccent;
DROP TEXT SEARCH CONFIGURATION IF EXISTS {CONFIG_SEM_ACENTO};
CREATE TEXT SEARCH CONFIGURATION {CONFIG_SEM_ACENTO} (COPY = {CONFIG_PADRAO});
ALTER TEXT SEARCH CONFIGURATION {CONFIG_SEM_ACENTO}
  ALTER MAPPING FOR hword, hword_part, word
  WITH unaccent, portuguese_stem;
"""

# A reindexação das mensagens que já existem. Sem ela, o texto antigo continua
# guardado COM acento enquanto a busca passa a procurar SEM — e o resultado é
# uma busca que deixa de achar o que achava. As duas coisas andam juntas.
SQL_DA_REINDEXACAO = (
    f"UPDATE forum_mensagem SET busca = to_tsvector('{CONFIG_SEM_ACENTO}', texto);"
)
