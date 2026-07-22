from uuid import uuid4

from wingman_ai.conversation.models import ConversationTurn
from wingman_ai.repositories import conversation_repository as repository


class ConversationService:
    def start_conversation(self, user=None, metadata=None):
        return repository.create_conversation(user=user, metadata=metadata)

    def continue_conversation(self, conversation_id, user=None):
        conversation = repository.get_conversation(conversation_id, user=user)
        if conversation:
            return conversation
        return repository.create_conversation(user=user, conversation_id=conversation_id)

    def end_conversation(self, conversation_id, user=None):
        return repository.end_conversation(conversation_id, user=user)

    def clear_conversation(self, conversation_id, user=None):
        return repository.clear_conversation(conversation_id, user=user)

    def list_conversations(self, user=None):
        return repository.list_conversations(user=user)

    def get_history(self, conversation_id, user=None, limit=50):
        return repository.get_history(conversation_id, user=user, limit=limit)

    def start_turn(self, message, user=None, context=None, conversation_id=None):
        conversation_id = conversation_id or (context or {}).get("conversation_id") or uuid4().hex
        self.continue_conversation(conversation_id, user=user)
        turn = ConversationTurn(
            message=message,
            user=user,
            conversation_id=conversation_id,
            context=context or {},
        )
        repository.append_message(conversation_id, "user", message, user=user)
        return turn

    def complete_turn(self, turn, response):
        turn.response = response or {}
        turn.intent = response.get("intent") if isinstance(response, dict) else None
        repository.append_message(
            turn.conversation_id,
            "assistant",
            response.get("message", ""),
            user=turn.user,
            metadata={
                "intent": turn.intent,
                "intent_result": response.get("intent_details"),
                "correlation_id": response.get("correlation_id"),
            },
        )
        return turn
