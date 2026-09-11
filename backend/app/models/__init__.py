"""SQLAlchemy entities. Import the module so every table is registered on the shared metadata."""
from app.models import building_violations  # noqa: F401
from app.models.building_violations import *  # noqa: F401,F403
