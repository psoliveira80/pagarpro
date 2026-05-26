"""Tests for conversation endpoints and ConversationStore."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.agent.conversation_store import ConversationStore
from app.core.agent.tool_interface import ToolResult
from app.core.agent.tool_registry import AgentToolRegistry


class TestConversationStore:
    """Test ConversationStore methods with mocked session."""

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new(self):
        """Creates a new conversation when none exists."""
        session = AsyncMock()

        # Mock: no existing conversation found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        empresa_id = uuid4()
        store = ConversationStore(session, empresa_id)
        conv = await store.get_or_create_conversation(
            channel="whatsapp",
            phone_e164="+5511999887766",
        )

        assert conv.channel == "whatsapp"
        assert conv.phone_e164 == "+5511999887766"
        assert conv.status == "ativa"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self):
        """Returns existing conversation when one matches."""
        session = AsyncMock()

        existing_conv = MagicMock()
        existing_conv.id = uuid4()
        existing_conv.channel = "whatsapp"
        existing_conv.phone_e164 = "+5511999887766"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_conv
        session.execute = AsyncMock(return_value=mock_result)

        store = ConversationStore(session, uuid4())
        conv = await store.get_or_create_conversation(
            channel="whatsapp",
            phone_e164="+5511999887766",
        )

        assert conv.id == existing_conv.id
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_append_message(self):
        """Appends a message and updates conversation."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()

        store = ConversationStore(session, uuid4())

        with patch.object(store, "_publish_message", new_callable=AsyncMock):
            msg = await store.append_message(
                uuid4(),
                role="user",
                content_text="Hello",
                sent_by="customer",
            )

        assert msg.role == "user"
        assert msg.content_text == "Hello"
        assert msg.sent_by == "customer"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_read(self):
        """mark_read sets unread_count to 0."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()

        store = ConversationStore(session, uuid4())
        await store.mark_read(uuid4())

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_agent_active(self):
        """set_agent_active toggles agent flag."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()

        store = ConversationStore(session, uuid4())
        await store.set_agent_active(uuid4(), active=False)

        session.execute.assert_called_once()


class TestToolRegistry:
    """Test AgentToolRegistry behavior."""

    @pytest.mark.asyncio
    async def test_register_and_list(self):
        """Tools are registered and listable."""
        from app.core.agent.tool_interface import ToolDefinition

        registry = AgentToolRegistry()

        async def handler(**kw: Any) -> ToolResult:
            return ToolResult(data="ok")

        registry.register(
            ToolDefinition(
                name="my_tool",
                description="Test",
                parameters_schema={"type": "object"},
                handler=handler,
            )
        )

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "my_tool"

    @pytest.mark.asyncio
    async def test_get_tools_for_llm_format(self):
        """get_tools_for_llm returns OpenAI function-calling format."""
        from app.core.agent.tool_interface import ToolDefinition

        registry = AgentToolRegistry()
        registry.register(
            ToolDefinition(
                name="fn1",
                description="Desc1",
                parameters_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
            )
        )

        llm_tools = registry.get_tools_for_llm()
        assert len(llm_tools) == 1
        assert llm_tools[0]["name"] == "fn1"
        assert llm_tools[0]["description"] == "Desc1"
        assert "properties" in llm_tools[0]["parameters"]

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Executing a nonexistent tool returns error."""
        registry = AgentToolRegistry()
        result = await registry.execute_tool("nope", {})
        assert result.error is not None
        assert "not found" in result.error


class TestPixReceiptClassifier:
    """Test the Pix receipt classifier."""

    def test_classifies_pix_receipt(self):
        """Detects a valid Pix receipt from OCR text."""
        from app.infrastructure.parsing.pix_receipt_classifier import classify_receipt

        ocr_text = """
        Comprovante de Pagamento
        Pix enviado com sucesso
        Valor: R$ 1.250,00
        E2E ID: E12345678901234567890
        Data: 15/05/2026
        Banco: Nubank
        """

        result = classify_receipt(ocr_text)
        assert result.is_receipt is True
        assert result.confidence >= 0.66
        assert result.amount is not None
        assert float(result.amount) == 1250.0
        assert result.transaction_id == "E12345678901234567890"
        assert result.date_str == "15/05/2026"
        assert result.bank_name == "Nubank"

    def test_rejects_non_receipt(self):
        """Non-receipt text is not classified as receipt."""
        from app.infrastructure.parsing.pix_receipt_classifier import classify_receipt

        result = classify_receipt("Hello, how are you? This is a normal message.")
        assert result.is_receipt is False

    def test_partial_receipt_low_confidence(self):
        """Partial match has lower confidence."""
        from app.infrastructure.parsing.pix_receipt_classifier import classify_receipt

        result = classify_receipt("Pix payment something R$ 100,00")
        # Only 1 pattern match, not enough
        assert result.is_receipt is False


class TestWhatsAppAdapters:
    """Test WhatsApp adapter webhook parsing."""

    @pytest.mark.asyncio
    async def test_zapi_parse_inbound_text(self):
        """ZapiAdapter parses inbound text message."""
        from app.infrastructure.adapters.whatsapp.zapi_adapter import ZapiAdapter

        adapter = ZapiAdapter(instance_id="test", token="test")
        payload = {
            "phone": "5511999999999",
            "text": {"message": "Ola, quero pagar"},
            "messageId": "msg_123",
            "isStatusReply": False,
        }

        result = await adapter.parse_webhook({}, payload)

        from app.domain.ports.whatsapp_gateway import ReceivedMessage

        assert isinstance(result, ReceivedMessage)
        assert result.sender_phone == "5511999999999"
        assert result.text == "Ola, quero pagar"
        assert result.external_id == "msg_123"

    @pytest.mark.asyncio
    async def test_evolution_api_parse_inbound(self):
        """EvolutionApiAdapter parses messages.upsert event."""
        from app.infrastructure.adapters.whatsapp.evolution_api_adapter import EvolutionApiAdapter

        adapter = EvolutionApiAdapter(base_url="http://localhost:8080", api_key="test")
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"id": "ev_msg_1", "remoteJid": "5511888888888@s.whatsapp.net", "fromMe": False},
                "message": {"conversation": "Preciso de ajuda"},
                "messageTimestamp": "1715000000",
            },
        }

        result = await adapter.parse_webhook({"apikey": "test"}, payload)

        from app.domain.ports.whatsapp_gateway import ReceivedMessage

        assert isinstance(result, ReceivedMessage)
        assert result.sender_phone == "5511888888888"
        assert result.text == "Preciso de ajuda"


class TestLlmAdapters:
    """Test LLM adapter response parsing."""

    def test_llm_factory_creates_openai(self):
        """LLM factory creates OpenAI adapter from settings."""
        from app.infrastructure.adapters.llm.llm_factory import _create_adapter
        from app.infrastructure.adapters.llm.openai_adapter import OpenAiAdapter

        adapter = _create_adapter("openai", "sk-test", "gpt-4o")
        assert isinstance(adapter, OpenAiAdapter)

    def test_llm_factory_creates_anthropic(self):
        """LLM factory creates Anthropic adapter."""
        from app.infrastructure.adapters.llm.llm_factory import _create_adapter
        from app.infrastructure.adapters.llm.anthropic_adapter import AnthropicAdapter

        adapter = _create_adapter("anthropic", "sk-test", "claude-sonnet-4-20250514")
        assert isinstance(adapter, AnthropicAdapter)

    def test_llm_factory_creates_ollama(self):
        """LLM factory creates Ollama adapter without API key."""
        from app.infrastructure.adapters.llm.llm_factory import _create_adapter
        from app.infrastructure.adapters.llm.ollama_adapter import OllamaAdapter

        adapter = _create_adapter("ollama", "", "llama3.1")
        assert isinstance(adapter, OllamaAdapter)

    def test_llm_factory_unknown_raises(self):
        """LLM factory raises for unknown provider."""
        from app.infrastructure.adapters.llm.llm_factory import _create_adapter

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _create_adapter("unknown_provider", "key", "model")


class TestScoreCalculator:
    """Test customer score calculation pure logic."""

    def test_score_weights_sum_to_one(self):
        """Default weights sum to 1.0."""
        from app.application.agent.score_calculator import DEFAULT_WEIGHTS

        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestAudioTranscriber:
    """Test audio transcription adapters."""

    @pytest.mark.asyncio
    async def test_console_transcriber_returns_placeholder(self):
        """ConsoleTranscriberAdapter returns placeholder text."""
        from app.infrastructure.adapters.whisper_api_adapter import ConsoleTranscriberAdapter

        adapter = ConsoleTranscriberAdapter()
        result = await adapter.transcribe(b"fake_audio_data")

        assert "[DEV]" in result.text
        assert result.confidence == 0.5
