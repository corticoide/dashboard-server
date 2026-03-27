from backend.services.crontab_service import (
    _parse_raw_with_envvars,
    _entries_and_envs_to_text,
    _parse_raw,
)


def test_env_vars_collected_separately():
    raw = 'MAILTO=""\nSHELL=/bin/bash\n* * * * * /usr/bin/true\n'
    entries, envvars = _parse_raw_with_envvars(raw)
    assert len(entries) == 1
    assert entries[0].command == "/usr/bin/true"
    assert 'MAILTO=""' in envvars
    assert "SHELL=/bin/bash" in envvars


def test_env_vars_preserved_in_output():
    raw = 'MAILTO=""\nSHELL=/bin/bash\n* * * * * /usr/bin/true\n'
    entries, envvars = _parse_raw_with_envvars(raw)
    output = _entries_and_envs_to_text(entries, envvars)
    assert 'MAILTO=""' in output
    assert "SHELL=/bin/bash" in output
    assert "* * * * * /usr/bin/true" in output


def test_env_vars_appear_before_jobs():
    raw = 'MAILTO=""\n* * * * * /usr/bin/true\n'
    entries, envvars = _parse_raw_with_envvars(raw)
    output = _entries_and_envs_to_text(entries, envvars)
    mailto_pos = output.index('MAILTO=""')
    job_pos = output.index("* * * * *")
    assert mailto_pos < job_pos


def test_no_env_vars_still_works():
    raw = "* * * * * /usr/bin/true\n"
    entries, envvars = _parse_raw_with_envvars(raw)
    assert envvars == []
    output = _entries_and_envs_to_text(entries, envvars)
    assert "* * * * * /usr/bin/true" in output


def test_parse_raw_shim_returns_entries_only():
    raw = 'MAILTO=""\n* * * * * /usr/bin/true\n'
    entries = _parse_raw(raw)
    assert len(entries) == 1
    assert entries[0].command == "/usr/bin/true"
