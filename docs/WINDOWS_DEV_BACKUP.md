# Windows Development Backup Configuration

For native Windows development with PostgreSQL 18, configure the backend `.env` with paths to the PostgreSQL CLI tools if they are not already on `PATH`:

```env
BACKUP_DIR=./backups
PG_DUMP_PATH=C:\\Program Files\\PostgreSQL\\18\\bin\\pg_dump.exe
PG_RESTORE_PATH=C:\\Program Files\\PostgreSQL\\18\\bin\\pg_restore.exe
```

Use the exact PostgreSQL installation path on the workstation. The application runs the commands without a shell, so spaces in `Program Files` are supported.
