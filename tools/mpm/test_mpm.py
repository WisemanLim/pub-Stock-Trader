"""MPM Procfile 생성기 시험 — 표준 라이브러리 기반(임의 uv 환경 pytest 로 실행)."""
import mpm


def test_render_all_groups_default_env():
    text = mpm.render_procfile()
    names = [ln.split(":")[0] for ln in text.splitlines() if not ln.startswith("#")]
    assert names == ["ingest", "analysis", "rag", "agents", "risk", "web"]  # 레지스트리 순서
    assert "APP_ENV=local" in text


def test_env_substitution():
    text = mpm.render_procfile(env="prod")
    assert "APP_ENV=prod" in text
    assert ". ./.env.prod" in text          # rust 서비스 env 파일
    assert "APP_ENV=local" not in text


def test_group_filter_py_only():
    text = mpm.render_procfile(groups=["py"])
    names = [ln.split(":")[0] for ln in text.splitlines() if not ln.startswith("#")]
    assert names == ["ingest", "analysis", "rag", "agents"]
    assert "risk:" not in text and "web:" not in text


def test_group_filter_multiple():
    text = mpm.render_procfile(groups=["rust", "web"])
    names = [ln.split(":")[0] for ln in text.splitlines() if not ln.startswith("#")]
    assert names == ["risk", "web"]


def test_unknown_group_raises():
    import pytest
    with pytest.raises(ValueError):
        mpm.render_procfile(groups=["nope"])


def test_services_for_all():
    assert len(mpm.services_for()) == len(mpm.SERVICES)


def test_validate_accepts_generated():
    assert mpm.validate(mpm.render_procfile(env="prod")) is True


def test_validate_rejects_empty():
    assert mpm.validate("# only comment\n") is False


def test_validate_rejects_malformed():
    assert mpm.validate("this is not a procfile line\n") is False


def test_cli_check_ok():
    assert mpm.main(["--check", "--env", "dev"]) == 0


def test_cli_unknown_group_exit2():
    assert mpm.main(["--group", "bogus"]) == 2


def test_cli_check_group_subset():
    assert mpm.main(["--check", "--group", "py", "--group", "rust"]) == 0


# ── 차수25: 백그라운드 관리자(supervisor) ──

import os


def test_pid_alive_self():
    assert mpm.pid_alive(os.getpid()) is True


def test_pid_alive_dead():
    assert mpm.pid_alive(2_000_000_000) is False   # 존재하지 않는 pid
    assert mpm.pid_alive(None) is False
    assert mpm.pid_alive(0) is False


def test_state_paths_under_mpm_dir():
    assert mpm.pidfile_path().startswith(mpm.MPM_DIR)
    assert mpm.logfile_path().startswith(mpm.MPM_DIR)
    assert mpm.procfile_path().startswith(mpm.MPM_DIR)


def test_status_stopped_when_no_pidfile(tmp_path, monkeypatch):
    monkeypatch.setattr(mpm, "MPM_DIR", str(tmp_path / "none"))
    assert mpm.status() == 0          # 미실행 → stopped, exit 0
    assert mpm.read_pid() is None


def test_stop_noop_when_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(mpm, "MPM_DIR", str(tmp_path / "none"))
    assert mpm.stop() == 0            # 미실행 종료 → no-op, exit 0
