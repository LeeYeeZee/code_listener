"""
代码预处理模块：扫描目录、提取文件树、生成代码摘要
"""
import os
from pathlib import Path
from typing import Dict, List, Tuple
import config

# 不需要扫描的文件/目录
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".pytest_cache", ".mypy_cache", "third_party", "benchmarks", "doc", "docs", "helpers", "issues", "port", "cmake", ".github"}
SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".ttf", ".eot", ".mp3", ".mp4", ".wav", ".zip", ".tar", ".gz", ".yml", ".yaml", ".html", ".in", ".gitmodules", ".clang-format"}
SKIP_FILES = {"requirements.txt", "package-lock.json", "yarn.lock", "poetry.lock", ".env", ".env.example", ".gitignore", "CMakeLists.txt", "AUTHORS", "CONTRIBUTING.md", "LICENSE", "NEWS", "README.md", "TODO"}

def is_interesting_file(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if path.suffix.lower() in SKIP_EXTS:
        return False
    # 过滤测试文件
    if "_test." in path.name or "_tests." in path.name or path.name.startswith("test_"):
        return False
    return True

def scan_directory(repo_path: str) -> Tuple[List[str], Dict[str, str]]:
    """
    扫描代码仓库目录。
    
    返回：
        file_tree: 相对路径列表（用于展示文件树）
        file_contents: 相对路径 -> 截断后的文件内容
    """
    repo = Path(repo_path).resolve()
    file_tree = []
    file_contents = {}

    # 优先扫描核心目录（对大项目更重要）
    priority_dirs = ["db", "table", "util", "include"]
    
    for root, dirs, files in os.walk(repo):
        # 过滤掉不需要扫描的目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        
        for fname in files:
            fpath = Path(root) / fname
            rel_path = fpath.relative_to(repo).as_posix()
            
            if not is_interesting_file(fpath):
                continue
            
            # 标记优先级
            is_priority = any(rel_path.startswith(d + "/") for d in priority_dirs)
            file_tree.append((rel_path, is_priority))
            
            # 读取并截断内容
            try:
                raw = fpath.read_text(encoding="utf-8", errors="ignore")
                lines = raw.splitlines()
                if len(lines) > config.MAX_LINES_PER_FILE:
                    lines = lines[:config.MAX_LINES_PER_FILE]
                    lines.append("\n... [truncated] ...")
                content = "\n".join(lines)
                if len(content) > config.MAX_FILE_SIZE:
                    content = content[:config.MAX_FILE_SIZE] + "\n... [truncated] ..."
                file_contents[rel_path] = content
            except Exception:
                file_contents[rel_path] = "[Unable to read file]"
    
    # 优先排序核心目录，再按路径排序
    file_tree.sort(key=lambda x: (not x[1], x[0]))
    file_tree = [p[0] for p in file_tree]
    return file_tree, file_contents

def build_code_summary(file_tree: List[str], file_contents: Dict[str, str]) -> str:
    """
    为 LLM 构建代码摘要文本。
    包含文件树 + 每个文件的前N行内容。
    """
    lines = []
    lines.append("=== 文件树 ===")
    for p in file_tree:
        lines.append(p)
    
    lines.append("\n=== 关键文件内容（已截断）===")
    # 对大型项目，优先传入核心目录的文件，同时保证各类文件都有代表
    summary_files = file_tree[:config.MAX_FILES_FOR_SUMMARY]
    
    for p in summary_files:
        content = file_contents.get(p, "")
        lines.append(f"\n--- {p} ---")
        lines.append(content)
    
    if len(file_tree) > config.MAX_FILES_FOR_SUMMARY:
        remaining = len(file_tree) - config.MAX_FILES_FOR_SUMMARY
        lines.append(f"\n... 还有 {remaining} 个文件未展示，涵盖 {len(set(Path(p).parts[0] for p in file_tree[config.MAX_FILES_FOR_SUMMARY:]))} 个子目录 ...")
    
    return "\n".join(lines)
