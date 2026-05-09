# Models And SDK Usage

## Pydantic Models

- Reusable data models should inherit the project `BaseModel` from
  `ideago.models.base`.
- Use Pydantic v2 syntax: `model_config`, `model_dump`, `model_validate`,
  `field_validator`, and `model_validator`.
- Public reusable models live under `src/ideago/models/` and should be exported
  from `src/ideago/models/__init__.py` when they are part of the stable surface.
- Use `Field()` descriptions and constraints for public request, response, and
  domain fields.
- Use `default_factory` for mutable defaults.

## Imports

IdeaGo uses a standard `src` layout. Import from the package name:

```python
from ideago.config.settings import get_settings
from ideago.models.research import ResearchReport
```

Do not write `from src.ideago...`.

Pytest is configured with `pythonpath = ["src"]`, and editable installs should
use:

```bash
uv pip install -e .
```

File paths are still relative to the current working directory. Use `pathlib`
when code needs stable project paths.
