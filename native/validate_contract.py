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

构建方式：`maturin build --release`，再从**生成的 wheel** 里取出扩展模块导入。
为什么不是裸 `cargo build`：macOS arm64 上用裸 cargo 链接 cdylib 会失败
（`ld: symbol(s) not found for architecture arm64`，`_Py_NoneStruct` 等未解析符号）——
而本仓库真实的构建与发布路径本来就是 maturin（见 issue #220）。

退出码：0 通过；1 有违规；2 用法/环境错误。
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
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
    """Maturin build --release，从 wheel 里取出模块并按名导入."""
    module_name = _crate_name(crate_dir)
    staging = Path(tempfile.mkdtemp(prefix="native-contract-"))
    dist = staging / "dist"
    # 捕获输出：构建失败时把构建器自己的报错原样打出来。否则失败只剩一句
    # "returned non-zero exit status"——首轮 CI 上 macOS 的失败就是这样变成了一次
    # 没有诊断信息的排查（补上回显后才看到是 ld 的未解析符号）。
    built = subprocess.run(
        [
            "maturin",
            "build",
            "--release",
            "--manifest-path",
            str(crate_dir / "Cargo.toml"),
            "--out",
            str(dist),
        ],
        capture_output=True,
        text=True,
        # 显式 UTF-8 + 兜底：构建输出的颜色控制符与 UTF-8 字符用本地编码解码会抛
        # UnicodeDecodeError（本机 GBK 控制台实测），那会把"构建失败"变成"解码失败"。
        encoding="utf-8",
        errors="replace",
    )
    if built.returncode != 0:
        print("[环境] maturin build --release 失败，输出如下：", file=sys.stderr)
        print(built.stdout, file=sys.stderr)
        print(built.stderr, file=sys.stderr)
        raise SystemExit(2)
    # wheel 就是 zip，扩展模块的成员路径形如 `<包>/<模块名><后缀>`。后缀**随平台与 ABI
    # 变化**：Windows 是 `<模块>.pyd`，Linux/macOS 的 abi3 产物是 `<模块>.abi3.so`
    # （本机 Windows 与 CI ubuntu 实测不同名——精确比对 `<模块>.so` 会在 Linux 上取不到）。
    # 故按"前缀 + 扩展后缀"匹配，并按**原 basename**落盘：Python 的 EXTENSION_SUFFIXES
    # 认识 `.so` / `.abi3.so` / `.pyd`，原样即可导入，不必改名。
    ext_suffixes = (".so", ".pyd", ".dylib")
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        raise SystemExit(f"[环境] {dist} 里没有 wheel，检查 crate-type 是否 cdylib")
    with zipfile.ZipFile(wheels[0]) as wheel:
        members = [
            name
            for name in wheel.namelist()
            if Path(name).name.startswith(module_name + ".")
            and Path(name).name.endswith(ext_suffixes)
        ]
        if not members:
            raise SystemExit(
                f"[环境] {wheels[0].name} 里没有 {module_name} 的扩展模块，"
                f"成员为 {wheel.namelist()}"
            )
        basename = Path(members[0]).name
        with wheel.open(members[0]) as src, open(staging / basename, "wb") as dst:
            shutil.copyfileobj(src, dst)
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
    # 跨平台：Windows 与部分 CI runner 的控制台编码是 cp1252/cp936，直接 print 中文会抛
    # UnicodeEncodeError（本脚本在 macOS/Windows 的 CI 上就是这样红的）。显式把输出流设为
    # UTF-8 并给一个兜底，保证"能读出结论"而不是让编码问题伪装成契约违规。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

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
