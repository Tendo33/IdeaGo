#!/usr/bin/env python3
"""
包名重命名脚本

用法:
    python scripts/rename_package.py <新包名>

例如:
    python scripts/rename_package.py my_awesome_project

此脚本会自动完成以下操作:
    1. 重命名 src/ideago 目录为 src/<新包名>
    2. 更新 pyproject.toml 中的所有包名引用
    3. 更新 README.md 中的所有包名引用
    4. 更新所有 Python 文件中的导入语句
    5. 更新文档文件中的包名引用
"""

import argparse
import io
import shutil
import sys
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 旧包名
OLD_PACKAGE_NAME = "ideago"
OLD_PROJECT_NAME = "ideago"


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent


def validate_package_name(name: str) -> bool:
    """
    验证包名是否有效
    - 必须以字母或下划线开头
    - 只能包含字母、数字和下划线
    - 不能是 Python 关键字
    """
    import keyword

    if not name:
        return False

    # 检查是否是有效的 Python 标识符
    if not name.isidentifier():
        return False

    # 检查是否是 Python 关键字
    return not keyword.iskeyword(name)


def to_project_name(package_name: str) -> str:
    """
    将包名转换为项目名 (下划线转换为连字符)
    例如: my_awesome_project -> my-awesome-project
    """
    return package_name.replace("_", "-")


def rename_directory(root: Path, new_package_name: str) -> bool:
    """重命名包目录"""
    old_dir = root / "src" / OLD_PACKAGE_NAME
    new_dir = root / "src" / new_package_name

    if not old_dir.exists():
        print(f"❌ 错误: 源目录不存在: {old_dir}")
        return False

    if new_dir.exists():
        print(f"❌ 错误: 目标目录已存在: {new_dir}")
        return False

    try:
        shutil.move(str(old_dir), str(new_dir))
        print(f"✅ 重命名目录: {old_dir.name} -> {new_dir.name}")
        return True
    except Exception as e:
        print(f"❌ 重命名目录失败: {e}")
        return False


def update_file_content(
    file_path: Path,
    old_package: str,
    new_package: str,
    old_project: str,
    new_project: str,
) -> bool:
    """更新文件内容，替换包名和项目名"""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # 替换包名 (下划线版本)
        content = content.replace(old_package, new_package)

        # 替换项目名 (连字符版本)
        content = content.replace(old_project, new_project)

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except UnicodeDecodeError:
        # 跳过二进制文件
        return False
    except Exception as e:
        print(f"⚠️ 更新文件失败 {file_path}: {e}")
        return False


def get_files_to_update(root: Path) -> list[Path]:
    """获取需要更新的文件列表"""
    files = []

    # 需要更新的文件扩展名
    extensions = {
        ".py",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".txt",
        ".rst",
        ".cfg",
        ".ini",
    }

    # 需要排除的目录
    exclude_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".ruff_cache",
        ".pytest_cache",
        "node_modules",
        ".history",
        "logs",
    }

    for item in root.rglob("*"):
        # 跳过排除的目录
        if any(excluded in item.parts for excluded in exclude_dirs):
            continue

        # 检查文件扩展名
        if item.is_file() and (
            item.suffix in extensions
            or item.name in {"Makefile", "Dockerfile", ".gitignore", ".env.example"}
        ):
            files.append(item)

    return files


def main():
    parser = argparse.ArgumentParser(
        description="重命名 Python 包名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/rename_package.py my_new_package
    python scripts/rename_package.py --dry-run my_new_package
        """,
    )
    parser.add_argument(
        "new_package_name",
        help="新的包名 (使用下划线, 例如: my_awesome_project)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只显示将要修改的内容，不实际执行",
    )

    args = parser.parse_args()
    new_package_name = args.new_package_name
    dry_run = args.dry_run

    # 验证包名
    if not validate_package_name(new_package_name):
        print(f"❌ 无效的包名: '{new_package_name}'")
        print("包名必须:")
        print("  - 以字母或下划线开头")
        print("  - 只包含字母、数字和下划线")
        print("  - 不能是 Python 关键字")
        sys.exit(1)

    new_project_name = to_project_name(new_package_name)
    root = get_project_root()

    print(f"\n{'=' * 60}")
    print("包名重命名工具")
    print(f"{'=' * 60}")
    print(f"项目根目录: {root}")
    print(f"旧包名: {OLD_PACKAGE_NAME} -> 新包名: {new_package_name}")
    print(f"旧项目名: {OLD_PROJECT_NAME} -> 新项目名: {new_project_name}")
    if dry_run:
        print("⚠️ 预览模式 - 不会执行实际修改")
    print(f"{'=' * 60}\n")

    # 检查旧目录是否存在
    old_dir = root / "src" / OLD_PACKAGE_NAME
    if not old_dir.exists():
        print(f"❌ 错误: 包目录不存在: {old_dir}")
        print("可能包名已经被修改过，或者项目结构不正确。")
        sys.exit(1)

    # 获取需要更新的文件
    files = get_files_to_update(root)

    # 统计将要修改的文件
    files_to_modify = []
    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
            if OLD_PACKAGE_NAME in content or OLD_PROJECT_NAME in content:
                files_to_modify.append(file_path)
        except (UnicodeDecodeError, Exception):
            continue

    print("📁 将要重命名目录:")
    print(f"   src/{OLD_PACKAGE_NAME} -> src/{new_package_name}")
    print()

    print(f"📝 将要更新的文件 ({len(files_to_modify)} 个):")
    for f in sorted(files_to_modify):
        print(f"   {f.relative_to(root)}")
    print()

    if dry_run:
        print("✅ 预览完成。使用不带 --dry-run 的命令来执行实际修改。")
        sys.exit(0)

    # 确认执行
    confirm = input("确认执行以上修改? (y/N): ").strip().lower()
    if confirm != "y":
        print("操作已取消。")
        sys.exit(0)

    print("\n开始执行修改...\n")

    # 1. 先更新文件内容
    updated_count = 0
    for file_path in files_to_modify:
        if update_file_content(
            file_path,
            OLD_PACKAGE_NAME,
            new_package_name,
            OLD_PROJECT_NAME,
            new_project_name,
        ):
            updated_count += 1
            print(f"  ✅ 更新: {file_path.relative_to(root)}")

    # 2. 重命名目录
    print()
    if not rename_directory(root, new_package_name):
        print("\n❌ 重命名目录失败，请手动检查并修复。")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("✅ 完成!")
    print(f"{'=' * 60}")
    print(f"  • 更新了 {updated_count} 个文件")
    print("  • 重命名了包目录")
    print()
    print("📌 后续步骤:")
    print("  1. 检查修改是否正确: git diff")
    print("  2. 重新安装包: uv pip install -e .")
    print("  3. 运行测试确认: pytest")
    print("  4. 提交更改: git add -A && git commit -m 'chore: rename package'")
    print()


if __name__ == "__main__":
    main()
