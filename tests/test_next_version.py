"""scripts/next_version.py 的单元测试（变更 fix-release-version-continuity / #82）.

版本计算从 release.yml 的内嵌 bash 抽到仓内脚本，正是为了这些用例能存在——
分叉事故（main=0.9.0 而 dev 连发 0.8.3b0/0.8.4b0）在 bash 内嵌形态下无法被测覆盖。
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "next_version.py"
_spec = importlib.util.spec_from_file_location("next_version", _SCRIPT)
assert _spec is not None and _spec.loader is not None
nv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nv)


class TestBumpSemantics:
    """与历史 bash 逐一对应的递增语义（dev=patch+beta / main=minor）."""

    def test_dev_patch_beta(self):
        assert nv.bump("0.9.1-beta", "patch", "beta") == "0.9.2-beta"

    def test_dev_from_backmerged_stable_declaration(self):
        # back-merge 落地后 dev 声明等于 main（无 -beta），下一次 bump 回到 beta 线
        assert nv.bump("0.9.0", "patch", "beta") == "0.9.1-beta"

    def test_main_minor(self):
        assert nv.bump("0.9.0", "minor", "stable") == "0.10.0"

    def test_invalid_version_shape(self):
        with pytest.raises(ValueError, match=r"X\.Y\.Z"):
            nv.bump("0.9", "patch", "beta")


class TestFloorLift:
    """下限抬升：分叉时沿 main 线续算，正常节奏不介入."""

    def test_forked_dev_is_lifted_to_main_line(self):
        """事故复现：main=0.9.0 后 dev 声明还是 0.8.4-beta，候选 0.8.5-beta 必须抬升."""
        assert nv.next_version("0.8.4-beta", "patch", "beta", floor="0.9.0") == "0.9.1-beta"

    def test_candidate_above_floor_kept(self):
        """正常节奏：dev 领先 main，floor 不介入."""
        assert nv.next_version("0.9.1-beta", "patch", "beta", floor="0.9.0") == "0.9.2-beta"

    def test_candidate_equal_floor_kept(self):
        assert nv.next_version("0.9.0", "patch", "beta", floor="0.9.1-beta") == "0.9.1-beta"

    def test_main_no_floor_needed(self):
        assert nv.next_version("0.9.1", "minor", "stable") == "0.10.0"


class TestCli:
    def test_cli_prints_result(self, capsys):
        assert (
            nv.main(
                [
                    "--current",
                    "0.8.4-beta",
                    "--type",
                    "patch",
                    "--release",
                    "beta",
                    "--floor",
                    "0.9.0",
                ]
            )
            == 0
        )
        assert capsys.readouterr().out.strip() == "0.9.1-beta"
