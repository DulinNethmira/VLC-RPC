import os
import tempfile
import hashlib
import subprocess
import pytest
from unittest.mock import patch, MagicMock

# Import the class we need to test
from vlc_discord_rpc_gui import WebApi

class DummyBackend:
    def __init__(self):
        self.state_data = {}
    def log(self, msg):
        print(f"LOG: {msg}")

@pytest.fixture
def web_api():
    backend = DummyBackend()
    api = WebApi(backend)
    return api

@pytest.fixture
def dummy_exe():
    fd, path = tempfile.mkstemp(suffix=".exe")
    with os.fdopen(fd, "wb") as f:
        f.write(b"MZ dummy executable content for testing.")
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def dummy_exe_hash(dummy_exe):
    sha256 = hashlib.sha256()
    with open(dummy_exe, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest().lower()

@pytest.fixture
def non_exe():
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "wb") as f:
        f.write(b"Hello world")
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def no_mz_exe():
    fd, path = tempfile.mkstemp(suffix=".exe")
    with os.fdopen(fd, "wb") as f:
        f.write(b"Bad magic bytes")
    yield path
    if os.path.exists(path):
        os.remove(path)

# Test 1: missing checksum -> rejected
def test_missing_checksum(web_api, dummy_exe):
    valid, msg = web_api.verify_update_installer(dummy_exe, "")
    assert not valid
    assert "Invalid or missing expected SHA-256 hash" in msg

    valid, msg = web_api.verify_update_installer(dummy_exe, None)
    assert not valid
    assert "Invalid or missing expected SHA-256 hash" in msg

# Test 2: malformed checksum -> rejected
def test_malformed_checksum(web_api, dummy_exe):
    valid, msg = web_api.verify_update_installer(dummy_exe, "1234") # too short
    assert not valid
    assert "Invalid or missing expected SHA-256 hash" in msg

# Test 3: checksum for wrong file -> rejected
def test_checksum_for_wrong_file(web_api, dummy_exe):
    wrong_hash = "a" * 64
    valid, msg = web_api.verify_update_installer(dummy_exe, wrong_hash)
    assert not valid
    assert "SHA-256 hash mismatch" in msg

# Test 4: correct checksum -> accepted (unsigned installer + correct checksum -> accepted)
@patch("subprocess.run")
def test_correct_checksum(mock_run, web_api, dummy_exe, dummy_exe_hash):
    # Mock powershell returning NotSigned
    mock_run.return_value = MagicMock(stdout="NotSigned\n")
    valid, msg = web_api.verify_update_installer(dummy_exe, dummy_exe_hash)
    assert valid
    assert "Verified successfully" in msg

# Test 5: corrupted/tampered installer -> rejected
@patch("subprocess.run")
def test_corrupted_installer(mock_run, web_api, dummy_exe, dummy_exe_hash):
    # Tamper with the file
    with open(dummy_exe, "ab") as f:
        f.write(b"tamper")
    mock_run.return_value = MagicMock(stdout="NotSigned\n")
    valid, msg = web_api.verify_update_installer(dummy_exe, dummy_exe_hash)
    assert not valid
    assert "SHA-256 hash mismatch" in msg

# Test 6: invalid Authenticode signature -> rejected
@patch("subprocess.run")
def test_invalid_authenticode(mock_run, web_api, dummy_exe, dummy_exe_hash):
    # Hash matches, but powershell says signature is corrupted
    mock_run.return_value = MagicMock(stdout="HashMismatch\n")
    valid, msg = web_api.verify_update_installer(dummy_exe, dummy_exe_hash)
    assert not valid
    assert "Invalid Authenticode signature: HashMismatch" in msg

# Additional verification tests (not exe, no mz)
def test_not_an_exe(web_api, non_exe):
    valid, msg = web_api.verify_update_installer(non_exe, "a"*64)
    assert not valid
    assert "not an executable" in msg

def test_no_mz_header(web_api, no_mz_exe):
    valid, msg = web_api.verify_update_installer(no_mz_exe, "a"*64)
    assert not valid
    assert "lacks MZ executable header" in msg

# Test 8: failed verification -> installer never executed
@patch("subprocess.Popen")
@patch("vlc_discord_rpc_gui.WebApi.verify_update_installer")
def test_install_update_failed_verification(mock_verify, mock_popen, web_api, dummy_exe):
    # Simulate a failed verification
    mock_verify.return_value = (False, "Fake security failure")
    web_api._backend.state_data["update_temp_exe"] = dummy_exe
    web_api._backend.state_data["update_expected_sha256"] = "a" * 64
    
    result = web_api.install_update()
    
    # Should not execute
    mock_popen.assert_not_called()
    assert result["success"] is False
    assert "Fake security failure" in result["error"]
    # Temp file should be deleted
    assert not os.path.exists(dummy_exe)
    assert web_api._backend.state_data["update_temp_exe"] is None

@patch("os._exit")
@patch("subprocess.Popen")
@patch("vlc_discord_rpc_gui.WebApi.verify_update_installer")
def test_install_update_success(mock_verify, mock_popen, mock_exit, web_api, dummy_exe):
    # Simulate a successful verification
    mock_verify.return_value = (True, "Verified")
    web_api._backend.state_data["update_temp_exe"] = dummy_exe
    web_api._backend.state_data["update_expected_sha256"] = "a" * 64
    
    # We must patch os._exit otherwise it kills the test runner!
    result = web_api.install_update()
    
    # Should execute
    mock_popen.assert_called_once()
    mock_exit.assert_called_once_with(0)
