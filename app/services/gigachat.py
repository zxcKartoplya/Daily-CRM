from base64 import b64encode
from uuid import uuid4
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings


class GigaChatClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.gigachat_base_url or "").rstrip("/")
        self.oauth_url = (settings.gigachat_oauth_url or "").rstrip("/")
        self.client_id = settings.gigachat_client_id
        self.client_secret = settings.gigachat_client_secret
        self.scope = settings.gigachat_scope
        self.model = settings.gigachat_model
        self.verify_ssl = settings.gigachat_verify_ssl
        self.token = token or settings.gigachat_api_pers

        if not self.base_url:
            raise ValueError("GIGACHAT_BASE_URL is required")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }

    def _get_access_token(self) -> str:
        if self.token:
            return self.token
        if not self.oauth_url:
            raise ValueError("GIGACHAT_OAUTH_URL is required when no token is provided")
        if not self.client_id or not self.client_secret:
            raise ValueError("GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET are required")

        basic = b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("ascii")
        headers = {
            "Authorization": f"Basic {basic}",
            "RqUID": str(uuid4()),
            "Accept": "application/json",
        }
        data = {"scope": self.scope, "grant_type": "client_credentials"}
        with httpx.Client(timeout=30.0, verify=self.verify_ssl) as client:
            response = client.post(self.oauth_url, headers=headers, data=data)
            response.raise_for_status()
            payload = response.json()

        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("Failed to get access_token from GigaChat")
        return access_token

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=timeout, verify=self.verify_ssl) as client:
            response = client.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def chat(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        return self.request("POST", "/chat/completions", json=payload)
