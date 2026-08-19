from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from libs.funcs import HelperFunction as hlp
from aiocache import cached, Cache
import logging
from openai import AsyncOpenAI
import re

CACHE_CONFIG_LONG = {"cache": Cache.MEMORY, "ttl": 3600*24*30}

class AIHelperService:
    def __init__(self, ai_key: str, ai_url: str, ai_project: str, ai_model: str):
        self._ai_key = ai_key
        self._ai_url = ai_url
        self._ai_project = ai_project
        self._ai_model = ai_model
        self._aiclient = self.connect_to_ai()
        
    def connect_to_ai(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self._ai_key,
            base_url=self._ai_url,
            project=self._ai_project
        )

    async def getAiRequest(self, messages: list) -> str:
        try:
            response = await self._aiclient.chat.completions.create(
                model=self._ai_model,
                messages=messages,
                max_tokens=5000,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error calling AI API: {e}")
            raise

    async def clean_json_response(self, messages: list) -> str:        
        response = await self.getAiRequest(messages)
        response = response.strip()
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response)
        if match:
            return match.group(1).strip()
        json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
        match = re.search(json_pattern, response)
        
        if match:
            return match.group(1).strip()

        return "{}"

    @cached(**CACHE_CONFIG_LONG)
    async def get_categories(self, categories, key_words_categories: list | None = None):
        found = []
        for category in categories:
            title = category.get("title", "")
            for keyword in key_words_categories:
                if keyword in title:
                    found.append(category)
        return found

    @cached(**CACHE_CONFIG_LONG)
    async def get_users(self, arguments: list | None = None):
        return []

    @cached(**CACHE_CONFIG_LONG)
    async def get_services(self, services, key_words_services: list | None = None):
        found = []
        for service in services:
            title = service.get("title", "")
            for keyword in key_words_services:
                if keyword in title:
                    found.append(service)
        return found