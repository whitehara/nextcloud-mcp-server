"""Unit tests for WebDAV path encoding and XML escaping."""

import httpx
import pytest

from nextcloud_mcp_server.client.webdav import WebDAVClient
from nextcloud_mcp_server.utils.path import sanitize_webdav_path
from nextcloud_mcp_server.utils.xml import escape_xml
from tests.client.conftest import create_mock_response

pytestmark = pytest.mark.unit


def _mock_multistatus() -> httpx.Response:
    return create_mock_response(
        status_code=207,
        content=b'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"></d:multistatus>',
        headers={"content-type": "application/xml"},
    )


# ---------------------------------------------------------------------------
# sanitize_webdav_path
# ---------------------------------------------------------------------------


def test_sanitize_ascii_path():
    assert sanitize_webdav_path("Documents/report.pdf") == "Documents/report.pdf"


def test_sanitize_leading_slash_stripped():
    assert sanitize_webdav_path("/Documents/file.txt") == "Documents/file.txt"


def test_sanitize_japanese_filename():
    result = sanitize_webdav_path("日本語フォルダ/ファイル.txt")
    assert (
        result
        == "%E6%97%A5%E6%9C%AC%E8%AA%9E%E3%83%95%E3%82%A9%E3%83%AB%E3%83%80/%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB.txt"
    )


def test_sanitize_spaces_in_path():
    result = sanitize_webdav_path("My Documents/my file.txt")
    assert result == "My%20Documents/my%20file.txt"


def test_sanitize_mixed_ascii_japanese():
    result = sanitize_webdav_path("Photos/2024年/vacation.jpg")
    assert "Photos" in result
    assert "vacation.jpg" in result
    assert "2024" in result
    assert "%E5%B9%B4" in result  # 年


def test_sanitize_preserves_slashes():
    result = sanitize_webdav_path("a/b/c")
    assert result == "a/b/c"


def test_sanitize_normalizes_double_slashes():
    result = sanitize_webdav_path("a//b")
    assert result == "a/b"


def test_sanitize_traversal_raises():
    with pytest.raises(ValueError, match="Path traversal"):
        sanitize_webdav_path("../etc/passwd")


def test_sanitize_traversal_nested_raises():
    with pytest.raises(ValueError, match="Path traversal"):
        sanitize_webdav_path("Documents/../../etc/shadow")


def test_sanitize_empty_path():
    result = sanitize_webdav_path("")
    assert result == ""


def test_sanitize_root_slash():
    result = sanitize_webdav_path("/")
    assert result == ""


# ---------------------------------------------------------------------------
# escape_xml
# ---------------------------------------------------------------------------


def test_escape_xml_ampersand():
    assert escape_xml("a & b") == "a &amp; b"


def test_escape_xml_less_than():
    assert escape_xml("<script>") == "&lt;script&gt;"


def test_escape_xml_quotes():
    assert escape_xml('"quoted"') == "&quot;quoted&quot;"


def test_escape_xml_single_quote():
    assert escape_xml("it's") == "it&apos;s"


def test_escape_xml_plain_string():
    assert escape_xml("hello world") == "hello world"


def test_escape_xml_japanese():
    # Japanese characters need no XML escaping
    assert escape_xml("日本語") == "日本語"


def test_escape_xml_wildcard_preserved():
    # % wildcards used in SEARCH must pass through unmodified
    assert escape_xml("%.txt") == "%.txt"
    assert escape_xml("%report%") == "%report%"


# ---------------------------------------------------------------------------
# WebDAVClient URL construction
# ---------------------------------------------------------------------------


@pytest.fixture
def webdav_client(mocker):
    mock_http = mocker.AsyncMock(spec=httpx.AsyncClient)
    return WebDAVClient(mock_http, "testuser")


async def test_list_directory_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=_mock_multistatus()
    )

    await webdav_client.list_directory("日本語フォルダ")

    called_path = mock_req.call_args[0][1]
    assert "%E6%97%A5%E6%9C%AC%E8%AA%9E" in called_path
    assert "/remote.php/dav/files/testuser/" in called_path


async def test_read_file_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient,
        "_make_request",
        return_value=create_mock_response(
            200, content=b"content", headers={"content-type": "text/plain"}
        ),
    )

    await webdav_client.read_file("書類/レポート.txt")

    called_path = mock_req.call_args[0][1]
    assert "%E6%9B%B8%E9%A1%9E" in called_path  # 書類
    assert "%E3%83%AC%E3%83%9D%E3%83%BC%E3%83%88" in called_path  # レポート


async def test_write_file_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=create_mock_response(201)
    )

    await webdav_client.write_file("テスト/ファイル.txt", b"data")

    called_path = mock_req.call_args[0][1]
    assert "%E3%83%86%E3%82%B9%E3%83%88" in called_path  # テスト


async def test_create_directory_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=create_mock_response(201)
    )

    await webdav_client.create_directory("新しいフォルダ")

    called_path = mock_req.call_args[0][1]
    assert (
        "%E6%96%B0%E3%81%97%E3%81%84%E3%83%95%E3%82%A9%E3%83%AB%E3%83%80" in called_path
    )


async def test_delete_resource_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=create_mock_response(204)
    )

    await webdav_client.delete_resource("削除対象/ファイル.txt")

    # First call is PROPFIND existence check, second is DELETE
    calls = mock_req.call_args_list
    for call in calls:
        assert "%E5%89%8A%E9%99%A4%E5%AF%BE%E8%B1%A1" in call[0][1]  # 削除対象


async def test_move_resource_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=create_mock_response(201)
    )

    await webdav_client.move_resource("移動元/ファイル.txt", "移動先/ファイル.txt")

    called_path = mock_req.call_args[0][1]
    headers = mock_req.call_args[1]["headers"]
    assert "%E7%A7%BB%E5%8B%95%E5%85%83" in called_path  # 移動元
    assert "%E7%A7%BB%E5%8B%95%E5%85%88" in headers["Destination"]  # 移動先


async def test_copy_resource_encodes_japanese(mocker, webdav_client):
    mock_req = mocker.patch.object(
        WebDAVClient, "_make_request", return_value=create_mock_response(201)
    )

    await webdav_client.copy_resource("コピー元/file.txt", "コピー先/file.txt")

    called_path = mock_req.call_args[0][1]
    headers = mock_req.call_args[1]["headers"]
    assert "%E3%82%B3%E3%83%94%E3%83%BC%E5%85%83" in called_path  # コピー元
    assert "%E3%82%B3%E3%83%94%E3%83%BC%E5%85%88" in headers["Destination"]  # コピー先


async def test_traversal_rejected_in_webdav_client(mocker, webdav_client):
    mocker.patch.object(WebDAVClient, "_make_request")

    with pytest.raises(ValueError, match="Path traversal"):
        await webdav_client.read_file("../etc/passwd")
