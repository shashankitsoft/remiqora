from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.config import RemoteModelEndpoint
from app import features, remote_engine


class RemoteEngineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.endpoints = patch.dict(
            remote_engine.REMOTE_MODEL_ENDPOINTS,
            {
                "test_model": RemoteModelEndpoint(
                    label="Test Model",
                    url="https://model.example/",
                    token="secret",
                    health_path="ready",
                )
            },
            clear=True,
        )
        self.endpoints.start()

    def tearDown(self) -> None:
        self.endpoints.stop()

    def test_enabled_and_auth_headers_are_model_specific(self) -> None:
        self.assertTrue(remote_engine.enabled("test_model"))
        self.assertFalse(remote_engine.enabled("other_model"))
        self.assertEqual(
            remote_engine.auth_headers("test_model"),
            {"Authorization": "Bearer secret"},
        )
        self.assertEqual(remote_engine.auth_headers("other_model"), {})

    def test_remote_stable_audio_does_not_require_local_installation(self) -> None:
        remote_engine.REMOTE_MODEL_ENDPOINTS["stable_audio"] = RemoteModelEndpoint(
            label="Stable Audio 3",
            url="https://stable.example",
        )
        with patch("app.features.has_local_stable_audio_env", return_value=False), patch(
            "app.features.local_stable_audio_models",
            return_value=[],
        ):
            self.assertTrue(features.has_stable_audio_env())
            self.assertFalse(features.has_local_stable_audio_env())
            self.assertTrue(features.has_stable_audio())
            self.assertEqual(
                features.stable_audio_models(),
                list(features.STABLE_AUDIO_MODELS),
            )

    async def test_health_check_uses_configured_endpoint_and_token(self) -> None:
        response = Mock()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = response

        with patch("app.remote_engine.httpx.AsyncClient", return_value=client) as client_class:
            await remote_engine.check_health("test_model")

        client_class.assert_called_once_with(timeout=5)
        client.get.assert_awaited_once_with(
            "https://model.example/ready",
            headers={"Authorization": "Bearer secret"},
        )
        response.raise_for_status.assert_called_once_with()

    async def test_health_check_reports_the_remote_model(self) -> None:
        response = Mock()
        response.raise_for_status.side_effect = httpx.ConnectError("connection refused")
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = response

        with patch("app.remote_engine.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(
                RuntimeError,
                "Remote Test Model API is unavailable",
            ):
                await remote_engine.check_health("test_model")

    async def test_health_check_rejects_unconfigured_model(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "no remote endpoint configured for model 'other_model'",
        ):
            await remote_engine.check_health("other_model")


if __name__ == "__main__":
    unittest.main()
