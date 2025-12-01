-- Grant minimal privileges for local development
-- Run this as a superuser (example: sudo -u postgres psql -d edos_dev -f grant_privileges.sql)

-- Grant read access to cloud_resources so the consumer can map resource identifiers
GRANT SELECT ON TABLE public.cloud_resources TO edos_dev;

-- Grant write access to security_alerts so the consumer can insert alerts via raw SQL fallback
GRANT INSERT, UPDATE ON TABLE public.security_alerts TO edos_dev;

-- Optional: make edos_dev the owner of these tables (requires superuser and may not be desired)
-- ALTER TABLE public.cloud_resources OWNER TO edos_dev;
-- ALTER TABLE public.security_alerts OWNER TO edos_dev;

-- If your schema is different than `public`, adjust schema-qualified names accordingly.
