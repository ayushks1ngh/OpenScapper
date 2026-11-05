import os

import pytest

from app import config


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in list(os.environ):
        if k.startswith(('OPENSCRAPPER_', 'SCOUT_')):
            monkeypatch.delenv(k)


def test_new_prefix_wins_then_legacy_then_default(monkeypatch):
    assert config.env('PROXY', 'none') == 'none'
    monkeypatch.setenv('SCOUT_PROXY', 'old')
    assert config.env('PROXY') == 'old'
    monkeypatch.setenv('OPENSCRAPPER_PROXY', 'new')
    assert config.env('PROXY') == 'new'


def test_empty_value_counts_as_unset(monkeypatch):
    monkeypatch.setenv('OPENSCRAPPER_PROXY', '')
    monkeypatch.setenv('SCOUT_PROXY', 'legacy')
    assert config.env('PROXY') == 'legacy'


def test_flag_and_number(monkeypatch):
    assert not config.flag('FREE_PROXY')
    monkeypatch.setenv('SCOUT_FREE_PROXY', 'Yes')
    assert config.flag('FREE_PROXY')
    assert config.number('DELAY_MIN', 1.5) == 1.5
    monkeypatch.setenv('OPENSCRAPPER_DELAY_MIN', '2.25')
    assert config.number('DELAY_MIN', 1.5) == 2.25
    monkeypatch.setenv('OPENSCRAPPER_DELAY_MIN', 'abc')
    assert config.number('DELAY_MIN', 1.5) == 1.5


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / '.env'
    f.write_text('# c\nOPENSCRAPPER_A=1\nOPENSCRAPPER_B = two \n\nbad line\n')
    monkeypatch.setenv('OPENSCRAPPER_A', 'keep')
    config.load_dotenv(f)
    assert os.environ['OPENSCRAPPER_A'] == 'keep'
    assert os.environ['OPENSCRAPPER_B'] == 'two'
    config.load_dotenv(tmp_path / 'missing')  # no error


def test_update_env_file_migrates_legacy_key(tmp_path, monkeypatch):
    f = tmp_path / '.env'
    f.write_text('# keep me\nSCOUT_PROXY=http://old\nOTHER=1')
    monkeypatch.setenv('SCOUT_PROXY', 'http://old')
    config.update_env_file(f, 'PROXY', 'http://new')
    text = f.read_text()
    assert 'OPENSCRAPPER_PROXY=http://new' in text
    assert 'SCOUT_PROXY' not in text and '# keep me' in text and 'OTHER=1' in text
    assert config.env('PROXY') == 'http://new' and 'SCOUT_PROXY' not in os.environ
    config.update_env_file(f, 'PROXY', '')          # clearing replaces, never duplicates
    assert f.read_text().count('OPENSCRAPPER_PROXY=') == 1
    assert config.env('PROXY', 'unset') == 'unset'


def test_home_respects_override(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENSCRAPPER_HOME', str(tmp_path / 'h'))
    assert config.home() == tmp_path / 'h' and (tmp_path / 'h').is_dir()
