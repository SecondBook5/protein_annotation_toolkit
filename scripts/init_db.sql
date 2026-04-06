-- Enable PostgreSQL extensions needed for the toolkit
-- This script runs automatically when the PostgreSQL container starts

-- Enable trigram extension for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable UUID extension for correlation IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant privileges to the application user
GRANT ALL PRIVILEGES ON DATABASE protein_annotation_db TO pat_user;
