import pytest

from sciagent.core.errors import AuthenticationError, ValidationFailed
from sciagent.core.security import ApiKeyAuthenticator, Principal


def test_authenticates_known_key():
    auth = ApiKeyAuthenticator("k1:alice:researcher:imaging|clinical,k2:root:admin:*")
    p = auth.authenticate("k1")
    assert p == Principal("alice", "researcher", frozenset({"imaging", "clinical"}))
    assert p.in_group("imaging") and not p.in_group("genomics")
    assert auth.authenticate("k2").is_admin
    assert auth.authenticate("k2").in_group("anything")


@pytest.mark.parametrize("key", [None, "", "nope"])
def test_rejects_missing_or_unknown_key(key):
    with pytest.raises(AuthenticationError):
        ApiKeyAuthenticator("k1:alice:researcher:imaging").authenticate(key)


@pytest.mark.parametrize("spec", ["k1:alice:researcher", "k1:alice:superuser:imaging"])
def test_rejects_malformed_spec(spec):
    with pytest.raises(ValidationFailed):
        ApiKeyAuthenticator(spec)
