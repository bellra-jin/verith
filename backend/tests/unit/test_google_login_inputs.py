"""Fake-key files only: never inspect the user's backend/.env or start services."""

import pytest

from scripts.google_login_inputs import GoogleInputError, read_google_inputs


def test_selects_only_two_literal_google_keys_without_env_fallback(
    tmp_path, monkeypatch
):
    path = tmp_path / "fake-input.txt"
    path.write_text(
        'DATABASE_URL=must-not-export\nOTHER_SECRET=unrelated-fake-secret\nGOOGLE_CLIENT_ID="fake.apps.googleusercontent.com"\nexport GOOGLE_CLIENT_SECRET=\'fake-only-secret\'\nUNRELATED_VALID="ignored"\n'
    )
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "must-not-use-process-value")
    original = path.read_bytes()
    inputs = read_google_inputs(path)
    assert inputs.backend_environment() == {
        "GOOGLE_CLIENT_ID": "fake.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "fake-only-secret",
    }
    assert not any(
        word in repr(inputs)
        for word in ["fake-only-secret", "fake.apps", "must-not-export", "unrelated"]
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "text",
    [
        "GOOGLE_CLIENT_ID=fake\n",
        "GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=\n",
        "GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=fake-one\nGOOGLE_CLIENT_SECRET=fake-two\n",
        'GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET="fake-not-closed\n',
        "GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=${OTHER_SECRET}\n",
        'GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET="fake\x00value"\n',
    ],
)
def test_bad_inputs_fail_without_raw_value_path_or_other_secret(tmp_path, text):
    path = tmp_path / "fake-only-input.txt"
    path.write_text(text)
    with pytest.raises(GoogleInputError) as caught:
        read_google_inputs(path)
    assert str(path) not in str(caught.value)
    assert "fake" not in str(caught.value)
    assert "${" not in str(caught.value)


def test_missing_file_and_symlink_fail_safely(tmp_path):
    path = tmp_path / "missing.txt"
    with pytest.raises(GoogleInputError):
        read_google_inputs(path)
    target = tmp_path / "fake-target.txt"
    target.write_text("GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=fake\n")
    path.symlink_to(target)
    with pytest.raises(GoogleInputError):
        read_google_inputs(path)


def test_non_google_assignments_never_enter_dotenv_parser(tmp_path, monkeypatch):
    import scripts.google_login_inputs as module

    path = tmp_path / "fake-selective.txt"
    path.write_text(
        "DATABASE_URL=fake-unrelated-db\nUNRELATED=fake-other-secret\nGOOGLE_CLIENT_ID=fake-client\nGOOGLE_CLIENT_SECRET=fake-secret\n"
    )
    parsed = []
    original = module.parse_stream

    def record(stream):
        line = stream.getvalue()
        parsed.append(line)
        return original(stream)

    monkeypatch.setattr(module, "parse_stream", record)
    module.read_google_inputs(path)
    assert len(parsed) == 2
    assert all(line.startswith("GOOGLE_CLIENT_") for line in parsed)
    assert not any("DATABASE_URL" in line or "UNRELATED" in line for line in parsed)


@pytest.mark.parametrize(
    "text",
    [
        "OTHER='open\nGOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=fake\n'\n",
        'OTHER="open\nGOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=fake\n"\n',
        "GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET=fake\n'GOOGLE_CLIENT_SECRET'=duplicate\n",
        "'GOOGLE_CLIENT_ID'=fake\nGOOGLE_CLIENT_SECRET=fake\n",
        'GOOGLE_CLIENT_ID=fake\nGOOGLE_CLIENT_SECRET="   "\n',
        'GOOGLE_CLIENT_ID=" \t "\nGOOGLE_CLIENT_SECRET=fake\n',
    ],
)
def test_multiline_quoted_key_and_whitespace_regressions(tmp_path, text):
    path = tmp_path / "fake-regression.txt"
    path.write_text(text)
    with pytest.raises(GoogleInputError) as caught:
        read_google_inputs(path)
    assert "fake" not in str(caught.value) and "duplicate" not in str(caught.value)
