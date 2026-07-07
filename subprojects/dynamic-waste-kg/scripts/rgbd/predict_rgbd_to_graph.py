"""提供 predict rgbd to graph 命令行入口。"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.rgbd.predict_to_graph import main


if __name__ == "__main__":
    raise SystemExit(main())
