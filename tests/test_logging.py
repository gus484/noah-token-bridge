import logging

from noah_bridge.logging_setup import RedactFilter


def test_secrets_are_masked():
    f = RedactFilter(["TOKEN123", "SN9"])
    rec = logging.LogRecord("x", logging.INFO, "", 0, "auth %s for %s", ("TOKEN123", "SN9"), None)
    f.filter(rec)
    assert "TOKEN123" not in rec.getMessage() and "SN9" not in rec.getMessage()
