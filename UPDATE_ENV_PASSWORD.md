# Update Your .env File

The Docker container is now using port 5432 and password `simplepass123`.

**Update your `.env` file:**

```bash
DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5432/et_intel
POSTGRES_PASSWORD=simplepass123
```

Then test: `python cli.py status`

