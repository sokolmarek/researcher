#!/usr/bin/env python3
"""Analyze a codebase to extract information for the Methods section of a paper.

Usage:
    python codebase-analyzer.py <project-path>
    python codebase-analyzer.py <project-path> --output analysis.json

Extracts:
    - Main algorithms and their complexity
    - Data processing pipelines
    - Model architectures and hyperparameters
    - Dependencies and frameworks
    - Configuration parameters
    - Evaluation metrics
"""

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# File extensions to analyze
CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".m": "matlab",
    ".cpp": "cpp",
    ".c": "c",
    ".java": "java",
}

# Patterns indicating ML/data science code
ML_PATTERNS = {
    "frameworks": [
        r"import\s+(?:torch|tensorflow|keras|sklearn|scipy|numpy|pandas|jax)",
        r"from\s+(?:torch|tensorflow|keras|sklearn|scipy|numpy|pandas|jax)",
        r"require\(['\"](?:tensorflow|@tensorflow)['\"]",
    ],
    "training": [
        r"\.fit\(", r"\.train\(", r"optimizer\.", r"loss_fn",
        r"criterion\s*=", r"learning_rate", r"lr\s*=", r"epochs?\s*=",
        r"batch_size", r"num_epochs",
    ],
    "evaluation": [
        r"accuracy", r"precision", r"recall", r"f1.score",
        r"auc|roc", r"confusion.matrix", r"mean_squared_error",
        r"classification_report", r"evaluate\(",
    ],
    "data_processing": [
        r"pd\.read_csv", r"DataLoader", r"Dataset\(",
        r"transform", r"preprocess", r"normalize",
        r"train_test_split", r"cross_val",
    ],
}


def find_source_files(project_path: str) -> list[Path]:
    """Find all source code files in the project."""
    root = Path(project_path)
    files = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".tox"}

    for path in root.rglob("*"):
        if any(skip in path.parts for skip in skip_dirs):
            continue
        if path.suffix in CODE_EXTENSIONS:
            files.append(path)

    return sorted(files)


def analyze_python_file(filepath: Path) -> dict:
    """Analyze a Python file for structure and patterns."""
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    result = {
        "classes": [],
        "functions": [],
        "imports": [],
        "config_values": {},
        "patterns_found": defaultdict(list),
    }

    # Parse imports
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("import ") or line.startswith("from "):
            result["imports"].append(line)

    # Try AST parsing for structure
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                result["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "line": node.lineno,
                })
            elif isinstance(node, ast.FunctionDef):
                # Top-level functions only
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args if a.arg != "self"]
                    result["functions"].append({
                        "name": node.name,
                        "args": args,
                        "line": node.lineno,
                    })
    except SyntaxError:
        pass

    # Check ML patterns
    for category, patterns in ML_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                result["patterns_found"][category].extend(matches)

    return result


def analyze_config_files(project_path: str) -> dict:
    """Look for configuration files and extract parameters."""
    root = Path(project_path)
    config = {}

    config_patterns = [
        "config.yaml", "config.yml", "config.json",
        "params.yaml", "hyperparams.yaml",
        "settings.py", "config.py",
        ".env.example",
    ]

    for pattern in config_patterns:
        for f in root.rglob(pattern):
            config[str(f.relative_to(root))] = f.read_text(
                encoding="utf-8", errors="ignore"
            )[:2000]  # Cap at 2000 chars

    return config


def analyze_requirements(project_path: str) -> list[str]:
    """Extract dependencies from requirements files."""
    root = Path(project_path)
    deps = []

    for name in ["requirements.txt", "setup.py", "pyproject.toml", "package.json",
                  "environment.yml", "Pipfile"]:
        for f in root.rglob(name):
            deps.append(f"{f.relative_to(root)}: exists")

    # Parse requirements.txt specifically
    req_file = root / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line)

    return deps


def generate_report(project_path: str) -> dict:
    """Generate full analysis report."""
    files = find_source_files(project_path)

    report = {
        "project_path": project_path,
        "total_files": len(files),
        "languages": defaultdict(int),
        "all_classes": [],
        "key_functions": [],
        "frameworks_detected": set(),
        "ml_patterns": defaultdict(list),
        "dependencies": analyze_requirements(project_path),
        "config_files": analyze_config_files(project_path),
    }

    for filepath in files:
        lang = CODE_EXTENSIONS.get(filepath.suffix, "unknown")
        report["languages"][lang] += 1

        if filepath.suffix == ".py":
            analysis = analyze_python_file(filepath)
            rel_path = str(filepath.relative_to(project_path))

            for cls in analysis["classes"]:
                cls["file"] = rel_path
                report["all_classes"].append(cls)

            for func in analysis["functions"]:
                func["file"] = rel_path
                report["key_functions"].append(func)

            for category, matches in analysis["patterns_found"].items():
                report["ml_patterns"][category].extend(matches)

    # Deduplicate
    report["frameworks_detected"] = list(set(report["ml_patterns"].get("frameworks", [])))
    report["languages"] = dict(report["languages"])
    report["ml_patterns"] = {k: list(set(v)) for k, v in report["ml_patterns"].items()}

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Analyze codebase for academic paper Methods section"
    )
    parser.add_argument("project_path", help="Path to the project to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    if not Path(args.project_path).is_dir():
        print(f"Error: {args.project_path} is not a directory")
        sys.exit(1)

    report = generate_report(args.project_path)

    output = json.dumps(report, indent=2, default=list)
    if args.output:
        Path(args.output).write_text(output)
        print(f"Analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
