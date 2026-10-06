# Contracts and Operations Adapter

Use for API contracts, schemas, migrations, deployments, permissions, infrastructure,
security, performance, and other changes with compatibility or operational risk.

- Identify producers, consumers, ownership, versioning, rollout order, compatibility window,
  and rollback/forward-fix strategy before editing.
- Compare old and new request/response/schema/config shapes with representative valid,
  empty, unknown, and failure inputs. Check generated clients and operational tooling.
- For migrations and deploys, prove expand/backfill/contract or equivalent ordering, retry
  safety, observability, and recovery. Keep destructive or irreversible actions behind an
  explicit boundary and confirmation required by the environment.
- For permissions and security, verify both allowed and denied paths without exposing
  secrets. For performance, record a baseline, workload, measurement method, and regression
  threshold rather than relying on intuition.
