from unittest.mock import patch, MagicMock

import httpx
import pytest

from src.llm import LLMClient


class TestLLMClientComplete:
    @patch("src.llm.httpx.post")
    def test_complete_returns_response_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }
        mock_post.return_value = mock_response

        client = LLMClient(base_url="https://api.example.com", api_key="test-key", model="test-model")
        result = client.complete("system prompt", "user message")

        assert result == "response text"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://api.example.com/chat/completions" == call_args[0][0]
        assert call_args[1]["json"]["model"] == "test-model"
        assert call_args[1]["json"]["messages"][0]["content"] == "system prompt"
        assert call_args[1]["json"]["messages"][1]["content"] == "user message"

    @patch("src.llm.httpx.post")
    def test_complete_raises_on_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")
        with pytest.raises(httpx.HTTPStatusError):
            client.complete("s", "u")

    @patch("src.llm.time.sleep")
    @patch("src.llm.httpx.post")
    def test_complete_retries_remote_protocol_error_then_succeeds(self, mock_post, mock_sleep):
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }
        mock_post.side_effect = [
            httpx.RemoteProtocolError("Server disconnected without sending a response."),
            success_response,
        ]

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")

        assert client.complete("s", "u", operation="rank_articles") == "response text"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.llm.time.sleep")
    @patch("src.llm.httpx.post")
    def test_complete_retries_http_500_then_succeeds(self, mock_post, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        error_response.headers = {}
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error",
            request=MagicMock(),
            response=error_response,
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }
        mock_post.side_effect = [error_response, success_response]

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")

        assert client.complete("s", "u", operation="rank_articles") == "response text"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.llm.time.sleep")
    @patch("src.llm.httpx.post")
    def test_complete_uses_retry_after_for_http_429(self, mock_post, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.text = "Too Many Requests"
        error_response.headers = {"Retry-After": "7"}
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limited",
            request=MagicMock(),
            response=error_response,
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }
        mock_post.side_effect = [error_response, success_response]

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")

        assert client.complete("s", "u", operation="rank_articles") == "response text"
        mock_sleep.assert_called_once_with(7.0)

    @patch("src.llm.time.sleep")
    @patch("src.llm.httpx.post")
    def test_complete_does_not_retry_http_400(self, mock_post, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Bad Request"
        error_response.headers = {}
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request",
            request=MagicMock(),
            response=error_response,
        )
        mock_post.return_value = error_response

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")

        with pytest.raises(httpx.HTTPStatusError):
            client.complete("s", "u", operation="rank_articles")

        mock_post.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("src.llm.time.sleep")
    @patch("src.llm.httpx.post")
    def test_complete_honors_timeout_and_max_retries_overrides(self, mock_post, mock_sleep):
        mock_post.side_effect = httpx.ReadTimeout("The read operation timed out")

        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")

        with pytest.raises(httpx.ReadTimeout):
            client.complete(
                "s",
                "u",
                operation="rank_articles",
                timeout=12,
                max_retries=1,
            )

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["timeout"] == 12
        mock_sleep.assert_not_called()
