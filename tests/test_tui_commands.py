import pytest
import os
import asyncio

from zeronet.tui import FilePathSuggester, ZeroNetTUI


class TestFormatFileSize:
    """Test the _format_file_size static method."""

    def test_bytes(self):
        assert ZeroNetTUI._format_file_size(512) == "512 B"

    def test_zero_bytes(self):
        assert ZeroNetTUI._format_file_size(0) == "0 B"

    def test_kilobytes(self):
        result = ZeroNetTUI._format_file_size(2048)
        assert "KB" in result
        assert "2.0" in result

    def test_megabytes(self):
        result = ZeroNetTUI._format_file_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = ZeroNetTUI._format_file_size(2 * 1024 * 1024 * 1024)
        assert "GB" in result


def _run_async(coro):
    """Helper to run an async function synchronously."""
    return asyncio.run(coro)


class TestFilePathSuggester:
    """Test the FilePathSuggester class."""

    def test_non_file_command_returns_none(self):
        s = FilePathSuggester()
        result = _run_async(s.get_suggestion("hello world"))
        assert result is None

    def test_file_empty_path_returns_tilde(self):
        s = FilePathSuggester()
        result = _run_async(s.get_suggestion("/file "))
        assert result == "/file ~/"

    def test_file_tilde_returns_home(self):
        s = FilePathSuggester()
        result = _run_async(s.get_suggestion("/file ~"))
        assert result == "/file ~/"

    def test_file_existing_dir(self):
        s = FilePathSuggester()
        # /tmp should exist on macOS/Linux
        result = _run_async(s.get_suggestion("/file /tmp/"))
        # Should return a suggestion starting with /file /tmp/
        if result is not None:
            assert result.startswith("/file /tmp/")

    def test_file_nonexistent_returns_none(self):
        s = FilePathSuggester()
        result = _run_async(s.get_suggestion("/file /this/path/does/not/exist/ever/xyz123"))
        assert result is None
