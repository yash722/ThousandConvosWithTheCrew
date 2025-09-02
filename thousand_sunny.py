import os
import uuid
import json
import asyncio
from dotenv import load_dotenv
from typing import List

from autogen_core import (
    DefaultTopicId, MessageContext,
    RoutedAgent, SingleThreadedAgentRuntime, TopicId, TypeSubscription,
    message_handler
)
from autogen_core.models import (
    SystemMessage, UserMessage, AssistantMessage, LLMMessage, ChatCompletionClient
)
from autogen_ext.models.openai import OpenAIChatCompletionClient
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown

console = Console()
load_dotenv()

# ------------------ Messages ------------------
class GroupChatMessage(BaseModel):
    body: UserMessage

class RequestToSpeak(BaseModel):
    pass

# ------------------ Straw Hat Agent ------------------
class StrawHatAgent(RoutedAgent):
    def __init__(self, description: str, group_chat_topic_type: str,
                 model_client: ChatCompletionClient, system_message: str):
        super().__init__(description=description)
        self._group_chat_topic_type = group_chat_topic_type
        self._model_client = model_client
        self._system_message = SystemMessage(content=system_message)
        self._chat_history: List[LLMMessage] = []

    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        self._chat_history.extend(
            [UserMessage(content=f"Transferred to {message.body.source}", source="system"),
             message.body]
        )

    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        console.print(Markdown(f"### {self.id.type}: "))
        self._chat_history.append(
            UserMessage(content=f"Transferred to {self.id.type}, adopt persona immediately.", source="system")
        )
        completion = await self._model_client.create([self._system_message] + self._chat_history)
        assert isinstance(completion.content, str)
        self._chat_history.append(AssistantMessage(content=completion.content, source=self.id.type))
        console.print(Markdown(completion.content))
        await self.publish_message(
            GroupChatMessage(body=UserMessage(content=completion.content, source=self.id.type)),
            DefaultTopicId(type=self._group_chat_topic_type),
        )

# ------------------ User Agent ------------------
class UserAgent(RoutedAgent):
    def __init__(self, description: str, group_chat_topic_type: str):
        super().__init__(description=description)
        self._group_chat_topic_type = group_chat_topic_type

    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        user_input = input("💬 Enter your message, type 'APPROVE' to finish: ")
        console.print(Markdown(f"### You:\n{user_input}"))
        await self.publish_message(
            GroupChatMessage(body=UserMessage(content=user_input, source="User")),
            DefaultTopicId(type=self._group_chat_topic_type),
        )

# ------------------ Group Chat Manager ------------------
class GroupChatManager(RoutedAgent):
    def __init__(self, participant_topic_types, model_client, participant_descriptions):
        super().__init__("Group chat manager")
        self._participant_topic_types = participant_topic_types
        self._participant_descriptions = participant_descriptions
        self._model_client = model_client
        self._chat_history: list[UserMessage] = []
        self._previous_speaker = None
        self._first_turn = True
        self._turn_count = 0  # track turns

    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        self._chat_history.append(message.body)

        # Build history and roles
        history = "\n".join(f"{m.source}: {m.content}" for m in self._chat_history if isinstance(m.content, str))
        roles = "\n".join(
            f"{role}: {desc}"
            for role, desc in zip(self._participant_topic_types, self._participant_descriptions)
            if role != self._previous_speaker
        )

        selector_prompt = f"""You are orchestrating a Straw Hat group chat.
These are the participants:
{roles}

Conversation so far:
{history}

Choose the NEXT role to speak from {self._participant_topic_types}.
Return only the role name.
"""

        completion = await self._model_client.create([SystemMessage(content=selector_prompt)])
        choice = completion.content.strip()

        # Match LLM choice to a known participant (case-insensitive)
        for topic_type in self._participant_topic_types:
            if topic_type.lower() in choice.lower():
                self._previous_speaker = topic_type
                await self.publish_message(RequestToSpeak(), DefaultTopicId(type=topic_type))
                return

        # fallback: round-robin
        idx = (self._participant_topic_types.index(self._previous_speaker) + 1) % len(self._participant_topic_types)
        fallback = self._participant_topic_types[idx]
        console.print(f"⚠️ Invalid choice, falling back to {fallback}")
        self._previous_speaker = fallback
        await self.publish_message(RequestToSpeak(), DefaultTopicId(type=fallback))


# ------------------ Main ------------------
async def main():
    with open("strawhat_personalities.json", "r", encoding="utf-8") as f:
        crew = json.load(f)
    for member in crew:
        print(f"Name: {member.get('name')!r}, Summary len: {len(member.get('summary',''))}")
    runtime = SingleThreadedAgentRuntime()
    group_chat_topic_type = "strawhat_chat"
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY")
    )
    participant_topics = []
    participant_desc = []
    for c in crew:
        name = c['name']
        summary = c['summary']
        trait = c['trait']
        agent_type = await StrawHatAgent.register(
            runtime,
            name,
            lambda: StrawHatAgent(
                description=f"{name} - {summary[:100]}",
                group_chat_topic_type=group_chat_topic_type,
                model_client=model_client,
                system_message=f"""You are {name}. Speak like {name} using the personality described here : {summary[:150]}. 
                                    Make sure to be very casual when speaking like talking to a very close friend and make sure not use any honorifics.
                                    Build upon the previous conversations and makes jokes, banter with other agents and show the human side of {name}."""
            )
        )
        await runtime.add_subscription(TypeSubscription(topic_type=name, agent_type=agent_type.type))
        await runtime.add_subscription(TypeSubscription(topic_type=group_chat_topic_type, agent_type=agent_type.type))
        participant_topics.append(name)
        participant_desc.append(trait)
    
    manager_type = await GroupChatManager.register(
        runtime,
        "group_chat_manager",
        lambda: GroupChatManager(
            participant_topics, model_client, participant_desc
        )
    )
    await runtime.add_subscription(TypeSubscription(topic_type=group_chat_topic_type, agent_type=manager_type.type))
    print(participant_desc, participant_topics)
    
    user_agent_type = await UserAgent.register(
        runtime,
        "User",
        lambda: UserAgent(
            description="The human aboard the Thousand Sunny",
            group_chat_topic_type=group_chat_topic_type
        ),
    )
    await runtime.add_subscription(TypeSubscription(topic_type="User", agent_type=user_agent_type.type))
    await runtime.add_subscription(TypeSubscription(topic_type=group_chat_topic_type, agent_type=user_agent_type.type))
    print("Registered User Agent")
    
    runtime.start()
    session_id = str(uuid.uuid4())

    await runtime.publish_message(
        GroupChatMessage(
            body=UserMessage(content="Guys Zoro is lost on an island again :(", source="User")
        ),
        TopicId(type=group_chat_topic_type, source=session_id),
    )
    await runtime.stop_when_idle()
    await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
