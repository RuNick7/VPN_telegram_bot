"""
The daily database dump.

Its whole job is to run unattended, so the two things worth pinning are that
it can actually connect and that the password never reaches a place somebody
else can read it.
"""

import pytest

from app.scheduler.jobs.subscription_db_backup import _scrub, pg_env

URL = "postgresql://tgvpn:s3cr3t@postgres:5432/tgvpn"


def test_the_url_is_split_into_the_variables_libpq_reads():
    """
    `PGDATABASE=<the whole URL>` is what broke it: that variable is the
    database *name* and is never expanded as a URI, so libpq looked for a
    database literally called `postgresql://...`, had no host, and fell back to
    a local socket that does not exist in the container.
    """
    assert pg_env(URL) == {
        "PGHOST": "postgres",
        "PGPORT": "5432",
        "PGUSER": "tgvpn",
        "PGPASSWORD": "s3cr3t",
        "PGDATABASE": "tgvpn",
    }


def test_sslmode_is_carried_over():
    assert pg_env(URL + "?sslmode=require")["PGSSLMODE"] == "require"


def test_percent_encoded_credentials_are_decoded():
    """A password with an `@` or a `/` must be encoded in the URL, and must not
    reach libpq still encoded."""
    env = pg_env("postgresql://us%40er:p%40ss%2Fword@host:5432/db")
    assert env["PGUSER"] == "us@er"
    assert env["PGPASSWORD"] == "p@ss/word"


@pytest.mark.parametrize(
    "url, missing",
    [
        ("postgresql://host/db", "PGPASSWORD"),
        ("postgresql://user@host/db", "PGPASSWORD"),
        ("postgresql://user:pw@host/db", "PGPORT"),
        ("postgresql://user:pw@host:5432/", "PGDATABASE"),
    ],
)
def test_absent_parts_are_left_to_libqp_defaults(url, missing):
    """An empty PG* variable is not the same as an unset one."""
    assert missing not in pg_env(url)


def test_the_password_never_reaches_the_command_line():
    """
    Which is the reason any of this exists: a process's arguments are readable
    by every local user, and this ran once a day.
    """
    assert "s3cr3t" not in " ".join(pg_env(URL).keys())


def test_a_failure_message_is_stripped_of_the_password():
    """pg_dump echoes what it was given, and this text is logged and mailed."""
    noisy = f'connection to "{URL}" failed: password "s3cr3t" rejected'
    cleaned = _scrub(noisy, URL)
    assert "s3cr3t" not in cleaned
    assert URL not in cleaned
