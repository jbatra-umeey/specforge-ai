"""Run python -m app.migrate before starting production API instances."""
from .storage import get_store
if __name__ == '__main__':
    get_store().migrate()
    get_store().check_schema()
    print('Database schema v1 ready')
