"""原生任务契约校验器（issue #139）.

第三方照着 `native/template/` 写完自己的任务后，用它机械地核对是否满足契约——
人读的清单会漂移，这个脚本不会。

用法::

    python native/validate_contract.py native/template
    python native/validate_contract.py <crate_dir> --expect-fail   # 演示：故意写错的 crate

检查项（对应 docs/native-tasks.md 的四条纪律）：

1. `contract_version()` 等于框架的 `CONTRACT_VERSION`
2. `capabilities()` 不声明适配器不支持的能力
3. `tasks()` 的每个值都是框架侧 `NativeTaskContract` 的真实实例，且字段非空
4. `execute()` 存在且可调用

构建方式：`cargo build --release`，把产物复制成 `<模块名>.pyd|.so` 后导入——
刻意不依赖 maturin，让校验器在只有 Rust 工具链的环境里也能跑。

退出码：0 通过；1 有违规；2 用法/环境错误。
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

#: 适配器不支持的能力——声明它们即违规（原生契约 v1）
UNSUPPORTED_CAPABILITIES = {"internal_parallel", "zero_copy"}

_NAME_RE = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)
_LIB_RE = re.compile(r"^\[lib\][^\[]*?^name\s*=\s*\"([^\"]+)\"", re.MULTILINE | re.DOTALL)


def _crate_name(crate_dir: Path) -> str:
    """取 [lib].name（模块名），回退到 [package].name."""
    text = (crate_dir / "Cargo.toml").read_text(encoding="utf-8")
    lib = _LIB_RE.search(text)
    if lib:
        return lib.group(1)
    package = _NAME_RE.search(text)
    if not package:
        raise SystemExit(f"[用法] {crate_dir}/Cargo.toml 里找不到 name")
    return package.group(1)


def _build_and_import(crate_dir: Path):
    """Cargo build --release，把产物放到临时目录并按模块名导入."""
    module_name = _crate_name(crate_dir)
    subprocess.run(
        ["cargo", "build", "--release", "--manifest-path", str(crate_dir / "Cargo.toml")],
        check=True,
    )
    # cargo 的 cdylib 产物后缀随平台不同：Windows 是 .dll、Linux 是 .so、macOS 是 .dylib；
    # 而 Python 只按 .pyd / .so 找扩展模块，故下面统一改名后再导入。
    import_suffix = ".pyd" if os.name == "nt" else ".so"
    built_suffixes = (".dll", ".so", ".dylib", ".pyd")
    release_dir = crate_dir / "target" / "release"
    candidates = [
        p
        for p in release_dir.glob(f"*{module_name}*")
        if p.is_file() and p.suffix in built_suffixes and "deps" not in p.parts
    ]
    if not candidates:
        raise SystemExit(
            f"[环境] {release_dir} 里找不到 {module_name} 的动态库，检查 crate-type 是否 cdylib"
        )
    staging = Path(tempfile.mkdtemp(prefix="native-contract-"))
    shutil.copyfile(candidates[0], staging / (module_name + import_suffix))
    sys.path.insert(0, str(staging))
    importlib.invalidate_caches()
    return importlib.import_module(module_name)


def check(crate_dir: Path) -> list[str]:
    """返回违规清单（空列表 = 通过）."""
    from zoo_framework.native.contract import CONTRACT_VERSION, NativeTaskContract

    module = _build_and_import(crate_dir)
    violations: list[str] = []

    for entry in ("contract_version", "capabilities", "tasks", "execute"):
        if not callable(getattr(module, entry, None)):
            violations.append(f"缺少入口 {entry}()（契约要求四个入口齐备）")
    if violations:
        return violations

    reported = module.contract_version()
    if reported != CONTRACT_VERSION:
        violations.append(
            f"contract_version() = {reported}，框架的 CONTRACT_VERSION = {CONTRACT_VERSION}"
            "（主版本不匹配时适配器会拒绝加载）"
        )

    capabilities = module.capabilities()
    if not isinstance(capabilities, (list, tuple)):
        violations.append(f"capabilities() 返回 {type(capabilities).__name__}，应为序列")
    else:
        bad = sorted(UNSUPPORTED_CAPABILITIES.intersection(capabilities))
        if bad:
            violations.append(f"capabilities() 声明了适配器不支持的能力：{bad}")

    registry = module.tasks()
    if not isinstance(registry, dict):
        violations.append(f"tasks() 返回 {type(registry).__name__}，应为 dict")
    elif not registry:
        violations.append("tasks() 是空的——至少要注册一个任务")
    else:
        for name, contract in registry.items():
            if not isinstance(contract, NativeTaskContract):
                violations.append(
                    f"tasks()[{name!r}] 是 {type(contract).__name__}，"
                    "必须是框架侧 NativeTaskContract 的真实实例（dict 会在执行路径上炸）"
                )
                continue
            for field in ("name", "input_format", "output_format"):
                if not getattr(contract, field, ""):
                    violations.append(f"tasks()[{name!r}] 的 {field} 为空")
            if not getattr(contract, "max_input_bytes", 0):
                violations.append(f"tasks()[{name!r}] 的 max_input_bytes 必须为正")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="校验原生任务 crate 是否满足契约")
    parser.add_argument("crate_dir", type=Path, help="含 Cargo.toml 的 crate 目录")
    parser.add_argument(
        "--expect-fail",
        action="store_true",
        help="反转退出码：用于演示「故意写错的 crate 会被报错」",
    )
    args = parser.parse_args()

    if not (args.crate_dir / "Cargo.toml").is_file():
        print(f"[用法] {args.crate_dir} 下没有 Cargo.toml", file=sys.stderr)
        return 2

    violations = check(args.crate_dir)
    if violations:
        print(f"契约校验未通过（{len(violations)} 项）：")
        for item in violations:
            print(f"  - {item}")
        return 0 if args.expect_fail else 1

    print(f"契约校验通过：{args.crate_dir}")
    if args.expect_fail:
        print("但 --expect-fail 期望它失败——这个 crate 是合法的，演示设置有问题")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
