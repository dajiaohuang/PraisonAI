"""Application TypeError must not trigger legacy-signature replay."""
import asyncio

import pytest

from praisonai_bot.gateway.server import GatewaySession, WebSocketGateway
from praisonaiagents.agent.interrupt import InterruptController
from praisonaiagents.gateway import GatewayConfig, SessionConfig


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("legacy", [False, True])
def test_dispatch_selects_signature_before_invoking(
    tmp_path, monkeypatch, asynchronous, legacy
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    calls = []

    class Agent:
        name = "dispatch-test"
        interrupt_controller = None

    if legacy:
        def execute(content):
            calls.append(content)
            return "completed"
    else:
        def execute(content, cancel_token=None):
            calls.append(cancel_token)
            raise TypeError("application failed after starting work")

    if asynchronous:
        if legacy:
            async def achat(self, content):
                return execute(content)
        else:
            async def achat(self, content, cancel_token=None):
                return execute(content, cancel_token=cancel_token)
        Agent.achat = achat
    elif legacy:
        def chat(self, content):
            return execute(content)
        Agent.chat = chat
    else:
        def chat(self, content, cancel_token=None):
            return execute(content, cancel_token=cancel_token)
        Agent.chat = chat

    agent = Agent()
    gateway = WebSocketGateway(config=GatewayConfig(
        host="127.0.0.1",
        auth_token="synthetic-dispatch-test-auth-token-123456",
        session_config=SessionConfig(persist=False),
    ))
    agent_id = gateway.register_agent(agent)
    session = GatewaySession(
        _session_id="dispatch-test", _agent_id=agent_id, _client_id="fixture"
    )
    controller = InterruptController()
    turn = gateway._drive_turn(session, agent, "one operation", controller, 2)

    if legacy:
        assert asyncio.run(turn) == "completed"
        assert agent.interrupt_controller is controller
    else:
        with pytest.raises(TypeError, match="application failed after starting work"):
            asyncio.run(turn)
        assert calls[0] is controller
    assert len(calls) == 1
