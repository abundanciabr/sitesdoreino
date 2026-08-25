-- =============================================================================
-- ETAPA A — MURALHA DE DADOS: um database + um role por célula.
-- Rode como superuser:  psql -U postgres -f provisionamento-postgres.sql
-- ANTES: substitua cada TROQUE_* por uma senha de  openssl rand -hex 24
-- (as mesmas senhas entram nos env/<celula>.env correspondentes).
-- funil não tem banco: é a única célula stateless (formulários postam em leads).
-- =============================================================================
\set ON_ERROR_STOP on

-- catalogo -------------------------------------------------------------------
CREATE ROLE catalogo_user LOGIN PASSWORD 'TROQUE_catalogo';
CREATE DATABASE catalogo_db OWNER catalogo_user;
REVOKE ALL ON DATABASE catalogo_db FROM PUBLIC;

-- quiz -----------------------------------------------------------------------
CREATE ROLE quiz_user LOGIN PASSWORD 'TROQUE_quiz';
CREATE DATABASE quiz_db OWNER quiz_user;
REVOKE ALL ON DATABASE quiz_db FROM PUBLIC;

-- leads ----------------------------------------------------------------------
CREATE ROLE leads_user LOGIN PASSWORD 'TROQUE_leads';
CREATE DATABASE leads_db OWNER leads_user;
REVOKE ALL ON DATABASE leads_db FROM PUBLIC;

-- checkout -------------------------------------------------------------------
CREATE ROLE checkout_user LOGIN PASSWORD 'TROQUE_checkout';
CREATE DATABASE checkout_db OWNER checkout_user;
REVOKE ALL ON DATABASE checkout_db FROM PUBLIC;

-- pagamentos (a fortaleza) ---------------------------------------------------
CREATE ROLE pagamentos_user LOGIN PASSWORD 'TROQUE_pagamentos';
CREATE DATABASE pagamentos_db OWNER pagamentos_user;
REVOKE ALL ON DATABASE pagamentos_db FROM PUBLIC;

-- alunos ---------------------------------------------------------------------
CREATE ROLE alunos_user LOGIN PASSWORD 'TROQUE_alunos';
CREATE DATABASE alunos_db OWNER alunos_user;
REVOKE ALL ON DATABASE alunos_db FROM PUBLIC;

-- mensageria -----------------------------------------------------------------
CREATE ROLE mensageria_user LOGIN PASSWORD 'TROQUE_mensageria';
CREATE DATABASE mensageria_db OWNER mensageria_user;
REVOKE ALL ON DATABASE mensageria_db FROM PUBLIC;

-- sugestoes (a Caixa de Sugestões) -------------------------------------------
-- Guarda dado pessoal de aluno (e-mail da Identidade — DECISAO-EVO-01 §3), por
-- isso o par isolado vale dobrado aqui: nem `alunos` lê este banco, nem esta
-- célula lê o de `alunos` (Lei 3 — a matrícula se consulta por HTTP).
CREATE ROLE sugestoes_user LOGIN PASSWORD 'TROQUE_sugestoes';
CREATE DATABASE sugestoes_db OWNER sugestoes_user;
REVOKE ALL ON DATABASE sugestoes_db FROM PUBLIC;

-- identidade (o login do site) ------------------------------------------------
-- Guarda O dado pessoal do site (e-mail da Identidade — a linha única que a
-- EVO-01 §3 exigia, agora nesta célula: DECISAO-celula-de-identidade). O par
-- isolado vale dobrado: nenhuma célula lê este banco — quem quer saber quem é
-- a pessoa pergunta por HTTP à API interna, com o token do par.
CREATE ROLE identidade_user LOGIN PASSWORD 'TROQUE_identidade';
CREATE DATABASE identidade_db OWNER identidade_user;
REVOKE ALL ON DATABASE identidade_db FROM PUBLIC;

-- admin (a área administrativa) ------------------------------------------------
-- Guarda a AUDITORIA da plataforma — quem mexeu em quê, quando, e qual era o
-- valor antes (DECISAO-celula-admin §4). É justamente o banco que alguém com
-- acesso indevido gostaria de editar para apagar o próprio rastro, então o par
-- isolado vale dobrado aqui. A área admin também não lê o banco de NINGUÉM:
-- métricas entram por HTTP, com token de leitura (Lei 3).
CREATE ROLE admin_user LOGIN PASSWORD 'TROQUE_admin';
CREATE DATABASE admin_db OWNER admin_user;
REVOKE ALL ON DATABASE admin_db FROM PUBLIC;

-- =============================================================================
-- PROVA DA MURALHA (o red-team repete isto — golpe nº 7):
--   psql "postgres://quiz_user:SENHA@localhost:5432/pagamentos_db"
--   → deve falhar: "permission denied for database pagamentos_db"
-- Acesso cruzado não é convenção. É negado pelo Postgres.
-- =============================================================================
