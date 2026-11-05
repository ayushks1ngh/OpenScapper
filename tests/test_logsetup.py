import json
import logging

import pytest

from app import logsetup


@pytest.fixture(autouse=True)
def restore_root():
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    yield
    for h in list(root.handlers):
        if h not in before:
            root.removeHandler(h)
            h.close()
    root.setLevel(level)


def flush():
    for h in logging.getLogger().handlers:
        h.flush()


def test_redact_hides_secrets():
    assert logsetup.redact('proxy http://bob:s3cret@10.0.0.1:8080/x') == 'proxy http://***@10.0.0.1:8080/x'
    assert 'abc123' not in logsetup.redact('cookie li_at=abc123; other=1')
    assert 'other=1' in logsetup.redact('cookie li_at=abc123; other=1')
    assert 'sk-live' not in logsetup.redact('api_key=sk-live-999 next')
    assert 'sk-live' not in logsetup.redact('{"token": "sk-live-999"}')
    assert logsetup.redact('nothing secret here') == 'nothing secret here'


def test_file_log_written_and_secrets_never_reach_it(tmp_path):
    f = tmp_path / 'run.log'
    assert logsetup.setup_logging(log_file=f, json_lines=False) == f
    log = logging.getLogger('test.logsetup')
    log.info('fetching via http://u:pw@proxy:1 ok')
    log.debug('debug hidden when not verbose')
    flush()
    text = f.read_text()
    assert 'fetching via http://***@proxy:1 ok' in text
    assert 'pw' not in text and 'debug hidden' not in text


def test_verbose_enables_debug(tmp_path):
    f = tmp_path / 'v.log'
    logsetup.setup_logging(verbose=True, log_file=f, json_lines=False)
    logging.getLogger('x').debug('details')
    flush()
    assert 'details' in f.read_text()


def test_json_lines(tmp_path):
    f = tmp_path / 'j.log'
    logsetup.setup_logging(log_file=f, json_lines=True)
    logging.getLogger('app.x').warning('boom %s', 'now')
    try:
        raise ValueError('bad li_at=SECRETCOOKIE')
    except ValueError:
        logging.getLogger('app.x').exception('failed')
    flush()
    rows = [json.loads(line) for line in f.read_text().splitlines()]
    assert rows[0]['msg'] == 'boom now' and rows[0]['level'] == 'WARNING' and rows[0]['logger'] == 'app.x'
    assert 'SECRETCOOKIE' not in json.dumps(rows[1]) and 'exc' in rows[1]


def test_idempotent_no_duplicate_handlers(tmp_path):
    f = tmp_path / 'i.log'
    for _ in range(3):
        logsetup.setup_logging(log_file=f, json_lines=False)
    logging.getLogger('dup').info('once')
    flush()
    assert f.read_text().count('once') == 1


def test_unwritable_log_location_falls_back_to_console(tmp_path):
    blocker = tmp_path / 'file'
    blocker.write_text('x')
    assert logsetup.setup_logging(log_file=blocker / 'sub' / 'x.log') is None
