CREATE SCHEMA IF NOT EXISTS coordenacao;
CREATE TABLE IF NOT EXISTS coordenacao.autoridade (
 coorte text PRIMARY KEY, backend text NOT NULL DEFAULT 'git' CHECK (backend IN ('git','postgres')),
 epoca bigint NOT NULL DEFAULT 1 CHECK (epoca > 0), origem_sha text NOT NULL,
 hash_historico text NOT NULL, atualizado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS coordenacao.tarefa (
 id text PRIMARY KEY, coorte text NOT NULL REFERENCES coordenacao.autoridade,
 documento jsonb NOT NULL, projecao jsonb NOT NULL, versao bigint NOT NULL DEFAULT 1,
 dono text, concessao bigint NOT NULL DEFAULT 0, expira_em timestamptz
);
CREATE TABLE IF NOT EXISTS coordenacao.historico (
 id text PRIMARY KEY, tarefa text NOT NULL REFERENCES coordenacao.tarefa,
 conteudo jsonb NOT NULL, sha256 text NOT NULL CHECK (length(sha256)=64)
);
CREATE TABLE IF NOT EXISTS coordenacao.operacao (
 coorte text NOT NULL REFERENCES coordenacao.autoridade, chave text NOT NULL,
 sha256 text NOT NULL, resultado jsonb NOT NULL, PRIMARY KEY(coorte,chave)
);
CREATE TABLE IF NOT EXISTS coordenacao.evento (
 id bigserial PRIMARY KEY, coorte text NOT NULL REFERENCES coordenacao.autoridade,
 tarefa text REFERENCES coordenacao.tarefa, ator text NOT NULL, operacao text NOT NULL,
 conteudo jsonb NOT NULL, criado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS coordenacao.outbox (
 evento bigint PRIMARY KEY REFERENCES coordenacao.evento, entregue_em timestamptz
);
CREATE TABLE IF NOT EXISTS coordenacao.candidato (
 id text PRIMARY KEY, tarefa text NOT NULL REFERENCES coordenacao.tarefa,
 manifesto jsonb NOT NULL, epoca bigint NOT NULL, criado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
 revogado boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS coordenacao.publicador (
 celula text PRIMARY KEY, coorte text NOT NULL REFERENCES coordenacao.autoridade,
 dono text NOT NULL, concessao bigint NOT NULL, expira_em timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS coordenacao.publicacao (
 id text PRIMARY KEY, candidato text NOT NULL REFERENCES coordenacao.candidato,
 celula text NOT NULL REFERENCES coordenacao.publicador, epoca bigint NOT NULL,
 concessao bigint NOT NULL, estado_anterior jsonb NOT NULL,
 estado text NOT NULL DEFAULT 'autorizada' CHECK(estado IN ('autorizada','publicada','falhou','incerta')),
 prova jsonb
);
CREATE OR REPLACE FUNCTION coordenacao.proteger_historico() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'historico imutavel: registre um novo evento'; END $$;
DROP TRIGGER IF EXISTS historico_imutavel ON coordenacao.historico;
CREATE TRIGGER historico_imutavel BEFORE UPDATE OR DELETE ON coordenacao.historico
 FOR EACH ROW EXECUTE FUNCTION coordenacao.proteger_historico();
DROP TRIGGER IF EXISTS evento_imutavel ON coordenacao.evento;
CREATE TRIGGER evento_imutavel BEFORE UPDATE OR DELETE ON coordenacao.evento
 FOR EACH ROW EXECUTE FUNCTION coordenacao.proteger_historico();
DROP TRIGGER IF EXISTS operacao_imutavel ON coordenacao.operacao;
CREATE TRIGGER operacao_imutavel BEFORE UPDATE OR DELETE ON coordenacao.operacao
 FOR EACH ROW EXECUTE FUNCTION coordenacao.proteger_historico();
