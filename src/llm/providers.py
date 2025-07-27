"""
Chinese LLM provider integrations for paper analysis.
Supports Seed, Kimi, DeepSeek, and other Chinese providers.
"""

import os
import httpx
import json
from typing import Dict, List, Optional, AsyncGenerator
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    tokens_used: int
    model: str
    provider: str


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @abstractmethod
    async def analyze_paper(self, title: str, abstract: str) -> LLMResponse:
        """Analyze paper abstract and return insights."""
        pass
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider."""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key, "https://api.deepseek.com/v1", model)
    
    async def analyze_paper(self, title: str, abstract: str) -> LLMResponse:
        """Analyze paper using DeepSeek."""
        prompt = f"""
        Analyze this academic paper:
        
        Title: {title}
        Abstract: {abstract}
        
        Please provide:
        1. Main topic/research area
        2. Key contributions
        3. Novelty score (1-10)
        4. Technical keywords (5-8 terms)
        5. Potential applications
        6. Related research areas
        
        Format as JSON with keys: topic, contributions, novelty_score, keywords, applications, related_areas
        """
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }
        )
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data["usage"]["total_tokens"]
        
        return LLMResponse(content, tokens, self.model, "deepseek")


class KimiProvider(BaseLLMProvider):
    """Kimi (Moonshot) API provider."""
    
    def __init__(self, api_key: str, model: str = "moonshot-v1-8k"):
        super().__init__(api_key, "https://api.moonshot.cn/v1", model)
    
    async def analyze_paper(self, title: str, abstract: str) -> LLMResponse:
        """Analyze paper using Kimi."""
        prompt = f"""
        请分析这篇学术论文：
        
        标题：{title}
        摘要：{abstract}
        
        请提供以下分析（用JSON格式）：
        1. 主要研究领域（topic）
        2. 核心贡献（contributions）
        3. 创新度评分1-10（novelty_score）
        4. 技术关键词5-8个（keywords）
        5. 潜在应用场景（applications）
        6. 相关研究领域（related_areas）
        """
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }
        )
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data["usage"]["total_tokens"]
        
        return LLMResponse(content, tokens, self.model, "kimi")


class SeedProvider(BaseLLMProvider):
    """Seed (Tencent) API provider."""
    
    def __init__(self, api_key: str, model: str = "seed-v1"):
        super().__init__(api_key, "https://api.seed.tencent.com/v1", model)
    
    async def analyze_paper(self, title: str, abstract: str) -> LLMResponse:
        """Analyze paper using Seed."""
        prompt = f"""
        分析以下学术论文：
        
        标题：{title}
        摘要：{abstract}
        
        请以JSON格式返回：
        - topic: 主要研究领域
        - contributions: 核心贡献
        - novelty_score: 创新度(1-10)
        - keywords: 技术关键词列表
        - applications: 潜在应用
        - related_areas: 相关领域
        """
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }
        )
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data["usage"]["total_tokens"]
        
        return LLMResponse(content, tokens, self.model, "seed")


class GLMProvider(BaseLLMProvider):
    """GLM (Zhipu) API provider."""
    
    def __init__(self, api_key: str, model: str = "glm-4"):
        super().__init__(api_key, "https://open.bigmodel.cn/api/paas/v4", model)
    
    async def analyze_paper(self, title: str, abstract: str) -> LLMResponse:
        """Analyze paper using GLM."""
        from zhipuai import ZhipuAI
        
        client = ZhipuAI(api_key=self.api_key)
        
        prompt = f"""
        请分析这篇学术论文：
        
        标题：{title}
        摘要：{abstract}
        
        请提供结构化的分析结果，包括研究领域、创新点、关键词等。
        """
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        tokens = response.usage.total_tokens
        
        return LLMResponse(content, tokens, self.model, "glm")


class LLMManager:
    """Manager for multiple LLM providers."""
    
    def __init__(self):
        self.providers = {}
        self._setup_providers()
    
    def _setup_providers(self):
        """Initialize available providers from environment variables."""
        provider_configs = {
            "deepseek": {
                "api_key": os.getenv("DEEPSEEK_API_KEY"),
                "provider_class": DeepSeekProvider
            },
            "kimi": {
                "api_key": os.getenv("KIMI_API_KEY"),
                "provider_class": KimiProvider
            },
            "seed": {
                "api_key": os.getenv("SEED_API_KEY"),
                "provider_class": SeedProvider
            },
            "glm": {
                "api_key": os.getenv("GLM_API_KEY"),
                "provider_class": GLMProvider
            }
        }
        
        for name, config in provider_configs.items():
            if config["api_key"]:
                self.providers[name] = config["provider_class"](config["api_key"])
    
    async def analyze_paper(self, title: str, abstract: str, provider: str = None) -> LLMResponse:
        """Analyze paper with specified provider or auto-select."""
        if provider:
            if provider not in self.providers:
                raise ValueError(f"Provider {provider} not available")
            return await self.providers[provider].analyze_paper(title, abstract)
        
        # Use first available provider
        if not self.providers:
            raise ValueError("No LLM providers configured")
        
        provider_name = list(self.providers.keys())[0]
        return await self.providers[provider_name].analyze_paper(title, abstract)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self.providers.keys())
    
    async def close_all(self):
        """Close all provider connections."""
        for provider in self.providers.values():
            await provider.close()


# Example usage
if __name__ == "__main__":
    async def main():
        manager = LLMManager()
        
        if manager.get_available_providers():
            response = await manager.analyze_paper(
                "Attention Is All You Need",
                "We propose a new simple network architecture, the Transformer..."
            )
            print(f"Analysis from {response.provider}: {response.content}")
        else:
            print("No LLM providers configured")
        
        await manager.close_all()
    
    asyncio.run(main())