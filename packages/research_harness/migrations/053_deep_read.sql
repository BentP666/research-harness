-- Add deep_read flag for papers marked as thoroughly read
ALTER TABLE papers ADD COLUMN deep_read INTEGER DEFAULT 0;
