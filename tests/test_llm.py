from unittest.mock import patch, MagicMock

import httpx

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

        import pytest
        client = LLMClient(base_url="https://api.example.com", api_key="k", model="m")
        with pytest.raises(httpx.HTTPStatusError):
            client.complete("s", "u")
