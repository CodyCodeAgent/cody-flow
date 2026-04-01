"""CodyFlow — start the web server.

Usage:
    python -m codyflow              # default: 127.0.0.1:8080
    python -m codyflow --port 3000  # custom port
    codyflow                        # via entry point
"""

from __future__ import annotations

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="CodyFlow — AI 工作流编排")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址 (默认 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8080, help="服务器端口 (默认 8080)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("错误: uvicorn 未安装，请运行: pip install codyflow", file=sys.stderr)
        sys.exit(1)

    print("\n  CodyFlow Web UI")
    print(f"  http://{args.host}:{args.port}\n")
    uvicorn.run("codyflow.web.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
