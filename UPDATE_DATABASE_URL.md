# Update Your .env File

Your local PostgreSQL is using port 5432, so Docker is now using port 5433.

**Update your `.env` file to use port 5433:**

```bash
DATABASE_URL=postgresql://et_intel_user:my_secure_password_123@localhost:5433/et_intel
POSTGRES_PASSWORD=my_secure_password_123
```

Then test the connection again!

