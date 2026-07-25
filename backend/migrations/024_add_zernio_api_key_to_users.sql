-- Migration 024: Add zernio_api_key column to users table
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS zernio_api_key text;
