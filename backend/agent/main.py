"""
main.py — Print the compliance pipeline graph visualization.
Run from anywhere: python backend/agent/main.py
"""

import sys
from pathlib import Path

# Ensure 'backend/' is on sys.path so `agent.*` imports resolve
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from agent.pipeline import get_graph_visualization, print_graph, get_langgraph_png

if __name__ == "__main__":
    # Print Mermaid diagram to stdout
    print_graph()

    # Also export LangGraph native PNG
    png_path = get_langgraph_png("assets/pipeline_graph.png")
    print(f"\nPNG exported to: {png_path}")
