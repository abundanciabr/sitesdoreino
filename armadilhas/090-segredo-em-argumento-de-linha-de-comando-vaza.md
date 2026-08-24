# Segredo em argumento de linha de comando vaza por quatro caminhos

**Sintoma:** você entrega ao mantenedor um comando pronto no formato
`bash script.sh "ID" "SEGREDO" "email"`, ele executa, funciona — e o segredo agora
está no print de tela que ele te manda de volta, no histórico do shell dele, e no
transcript da conversa. Medido em 24/08/2026: o segredo do cliente OAuth do Google
vazou exatamente assim, no provisionamento da célula `sugestoes`.

**Causa:** argumento de linha de comando é **público dentro da máquina e fora dela**:

| Caminho | Por quê |
|---|---|
| a tela | o shell ecoa a linha inteira antes de executar |
| `~/.bash_history` | fica gravado, e sobrevive à sessão |
| `ps aux` / `/proc/<pid>/cmdline` | qualquer processo do host lê enquanto o script roda |
| o chat com o agente | a pessoa manda o print para provar que funcionou — é o fluxo NORMAL, não descuido dela |

O quarto é o que engana: o projeto já dizia "segredo nunca passa por chat com agente"
(INV-P8), e mesmo assim o desenho do comando **garantia** que passaria. A regra estava
certa e a ferramenta a contradizia.

**Solução — o segredo se PERGUNTA, com digitação invisível:**

```bash
printf 'Cole o SEGREDO (nada vai aparecer na tela): '
read -r -s SEGREDO      # -s não ecoa
echo                    # a quebra de linha que o -s engoliu
[ -n "$SEGREDO" ] || { echo "PAROU: segredo vazio"; exit 1; }
```

Sai da tela, sai do histórico, sai do `ps`, e sai do print. **Continua valendo entregar
UM comando só** (`CLAUDE.md`) — o prompt acontece dentro dele.

**Separe o que é público do que é segredo, e não trate os dois igual.** No caso do
OAuth: o **id do cliente** é público por desenho (vai no HTML da página de login) e pode
ser argumento; o **segredo**, não. Tratar tudo como segredo cansa o mantenedor; tratar
tudo como público vaza.

**Quando já vazou:** rode a credencial (gere nova, apague a velha no provedor) e rode o
provisionamento de novo — por isso o script tem de ser **idempotente**. Limpe também o
histórico do shell: `history -c && rm -f ~/.bash_history` na sessão em que aconteceu.

**Origem:** Lote 2 da Caixa de Sugestões, 24/08/2026 — a ferramenta foi corrigida no
mesmo dia (`infra/provisionar-sugestoes.sh`).
