from alembic import context
from kubesentinel_api.config import get_settings
from kubesentinel_api.database import Base
from kubesentinel_api.escalations import Escalation  # noqa: F401
from kubesentinel_api.models import GreetingJob  # noqa: F401
from kubesentinel_api.operations.models import Snapshot  # noqa: F401
from sqlalchemy import create_engine, pool

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=str(get_settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(str(get_settings().database_url), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
