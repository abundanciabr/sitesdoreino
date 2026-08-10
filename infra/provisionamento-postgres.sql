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

-- =============================================================================
-- PROVA DA MURALHA (o red-team repete isto — golpe nº 7):
--   psql "postgres://quiz_user:SENHA@localhost:5432/pagamentos_db"
--   → deve falhar: "permission denied for database pagamentos_db"
-- Acesso cruzado não é convenção. É negado pelo Postgres.
-- =============================================================================
