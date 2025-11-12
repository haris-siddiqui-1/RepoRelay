# Migration Generation Instructions

## Model Changes Summary

### Product Model
Added 47 new fields to track repository health and binary signals.

### Finding Model
Added 3 new fields for auto-triage functionality.

## Generating the Migration

Once Docker is running, execute:

```bash
# Start DefectDojo containers
docker compose up -d

# Generate migration for model changes
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# The migration will be created in: dojo/db_migrations/

# Review the generated migration file to ensure correctness

# Apply the migration
docker compose exec uwsgi bash -c "python manage.py migrate"

# Verify migration success
docker compose exec uwsgi bash -c "python manage.py showmigrations dojo"
```

## Expected Migration Operations

The generated migration should include:

### AddField operations for Product model (47 fields):
- last_commit_date (DateTimeField, nullable)
- active_contributors_90d (IntegerField, default=0)
- days_since_last_commit (IntegerField, nullable)
- github_url (URLField, blank)
- github_repo_id (CharField, blank)
- readme_summary (TextField, blank, max_length=500)
- readme_length (IntegerField, default=0)
- primary_language (CharField, blank)
- primary_framework (CharField, blank)
- codeowners_content (TextField, blank)
- ownership_confidence (IntegerField, default=0, validators=[0-100])
- 36 BooleanField binary signals (all default=False)

### AddField operations for Finding model (3 fields):
- auto_triage_decision (CharField, default='PENDING', choices)
- auto_triage_reason (TextField, blank)
- auto_triaged_at (DateTimeField, nullable)

### Recommended Database Indexes (add separately after migration):

```sql
-- Performance indexes for new query patterns
CREATE INDEX idx_product_last_commit ON dojo_product(last_commit_date);
CREATE INDEX idx_product_github_repo_id ON dojo_product(github_repo_id);
CREATE INDEX idx_product_business_criticality ON dojo_product(business_criticality);
CREATE INDEX idx_finding_auto_triage ON dojo_finding(auto_triage_decision);
CREATE INDEX idx_finding_component_lookup ON dojo_finding(component_name, component_version);
```

## Migration Safety

All new fields are:
- ✅ Nullable or have defaults
- ✅ Non-breaking for existing data
- ✅ Backward compatible with existing queries
- ✅ Safe for zero-downtime deployment

## Rollback Procedure

If needed, rollback with:

```bash
# Identify the migration number
docker compose exec uwsgi bash -c "python manage.py showmigrations dojo"

# Rollback to previous migration
docker compose exec uwsgi bash -c "python manage.py migrate dojo XXXX_previous_migration"

# Where XXXX is the migration number before the enterprise enrichment migration
```

## Next Steps After Migration

1. **Commit the generated migration:**
   ```bash
   git add dojo/db_migrations/XXXX_enterprise_context_enrichment.py
   git commit -m "chore: add migration for enterprise context enrichment fields"
   ```

2. **Create database indexes** (optional, for performance):
   ```bash
   docker compose exec postgres psql -U defectdojo -d defectdojo < indexes.sql
   ```

3. **Verify field access:**
   ```bash
   docker compose exec uwsgi bash -c "python manage.py shell"
   ```
   ```python
   from dojo.models import Product, Finding
   p = Product.objects.first()
   print(p.github_url)  # Should work without error
   ```

## Troubleshooting

**Issue:** Migration conflicts with existing migrations
**Solution:** Use `--merge` flag:
```bash
docker compose exec uwsgi bash -c "python manage.py makemigrations --merge"
```

**Issue:** CharField max_length warning
**Solution:** This is expected for existing fields, safe to ignore for new fields

**Issue:** Index creation fails
**Solution:** Indexes are optional optimizations, can be added later
