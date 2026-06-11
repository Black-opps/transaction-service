import sys
from pathlib import Path

# Add your project path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.config import settings
from src.models.transaction import Base

target_metadata = Base.metadata
