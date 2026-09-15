# Deployment

Production requirements:
- APP_ENV=production
- DEBUG=false
- unique 32+ character SECRET_KEY
- non-example Super Admin password
- HTTPS/TLS
- database/Redis not publicly exposed
- encrypted off-server backups
- verified restore drill
- separate development/staging/production databases and secrets

Docker, Nginx and GitHub workflow files remain deployment scaffolding and should be
revalidated for the final target environment before go-live.
