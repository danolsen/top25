import json
from pathlib import Path

from app.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2))
    print(target)


if __name__ == "__main__":
    main()
