from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.application.ai_assistant import generate_ai_response
from wingman_ai.knowledge import build_fast_context_answer
from wingman_ai.prompts import get_prompt
from wingman_ai.services.document_summary import get_current_record_response, get_explicit_record_response


class GeneralCapability(Capability):
    name = "general"

    def handle(self, message, context, intent):
        prompt = get_prompt("base")
        if is_sis_operations_request(message):
            return CapabilityResult(
                message=build_sis_operations_response(),
                actions=get_sis_quick_actions(),
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    "response_mode": "sis_operations",
                },
            )

        conversation_response = build_conversation_response(context, intent)
        if conversation_response:
            return CapabilityResult(
                message=conversation_response,
                actions=get_conversation_actions(intent),
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    "response_mode": "conversation",
                },
            )

        record_response = get_explicit_record_response(message, context, intent=intent)
        if record_response:
            return CapabilityResult(
                message=record_response["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    **record_response["data"],
                },
            )

        current_record_response = get_current_record_response(message, context, intent=intent)
        if current_record_response:
            return CapabilityResult(
                message=current_record_response["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    **current_record_response["data"],
                },
            )

        fast_answer = build_fast_context_answer(message, context)
        if fast_answer:
            return CapabilityResult(
                message=fast_answer["message"],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    "response_mode": fast_answer["source"],
                },
            )

        ai_response = generate_ai_response(message=message, context=context, purpose="general assistance")
        if ai_response and ai_response.get("success"):
            return CapabilityResult(
                message=ai_response["response_text"],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    "ai": {
                        "provider": ai_response.get("provider"),
                        "model": ai_response.get("model"),
                        "latency": ai_response.get("latency"),
                    },
                },
            )

        fallback_lines = [
            "Ready",
            "I am ready for your next Talisma OneCampus task.",
            "",
            "Try Asking",
            '- "open Liam Patel"',
            '- "create a curriculum version for Certificate in Paralegal Studies"',
            '- "show enrollment for student Liam Patel"',
        ]
        if ai_response and not ai_response.get("success"):
            fallback_lines.extend(["", "Current Status", "- The local AI model did not respond within the fast-response window."])

        return CapabilityResult(
            message="\n".join(fallback_lines),
            data={
                "pipeline": "orchestrator",
                "prompt_version": prompt["version"],
                "ai": ai_response if ai_response else {"success": False, "error": "AI provider not configured."},
            },
        )


def build_conversation_response(context, intent):
    category = ((getattr(intent, "structured_intent", None) or {}).get("intent_category") or "").lower()
    if should_suppress_implicit_context(context) and category == "conversation":
        return "\n".join(
            [
                "Ready",
                "Conversation completed. I am ready for the next Talisma OneCampus task.",
            ]
        )

    if category == "greeting":
        return "\n".join(
            [
                "Hello",
                "Hello, I'm Talisma Wingman AI, your AI Work Partner for Talisma OneCampus.",
                "",
                "Current Context",
                context.get("summary") or "You are currently in Talisma OneCampus.",
                "",
                "How I Can Help",
                "I can help with admissions, student records, programs, attendance, assessments, fees, and academic operations.",
                "",
                "Try Asking",
                '- "open students"',
                '- "show student attendance"',
                '- "open assessment results"',
                "",
                "What would you like to do next?",
            ]
        )

    if category == "goodbye":
        return "\n".join(
            [
                "Goodbye",
                "Glad to help. I will be here when you need Talisma OneCampus support again.",
            ]
        )

    if category == "help":
        return "\n".join(
            [
                "Help",
                "I can help you work across Talisma OneCampus from the page you are currently viewing.",
                "",
                "Try Asking",
                '- "open students"',
                '- "tell me about this student"',
                '- "summarize attendance and assessment results"',
                '- "open program enrollments"',
            ]
        )

    if category == "conversation":
        return "\n".join(
            [
                "Got It",
                "I am ready for the next Talisma OneCampus task.",
                "",
                "Current Context",
                context.get("summary") or "You are currently in Talisma OneCampus.",
            ]
        )

    return None


def should_suppress_implicit_context(context):
    state = (context or {}).get("conversation_state") or {}
    return bool(state.get("suppress_implicit_context"))


def is_sis_operations_request(message):
    text = " ".join(str(message or "").strip().lower().split())
    return text in {
        "sis operations",
        "show sis operations",
        "show operations",
        "student operations",
        "what can you do in the sis",
        "what can you do in sis",
    }


def build_sis_operations_response():
    return "\n".join(
        [
            "Talisma OneCampus Operations",
            "Tell me the SIS outcome you need; I will find the right records and keep protected changes behind confirmation.",
            "",
            "Student 360",
            '- "Tell me about Jackson Moore"',
            '- "Show account balance for Jackson Moore"',
            "",
            "Enrollment & Courses",
            '- "Show enrollment for Jackson Moore"',
            '- "Summarize courses and grades for Marcus Green"',
            "",
            "Admissions",
            '- "Open student applications"',
            '- "Show applications awaiting review"',
            "",
            "Attendance & Assessment",
            '- "Open student attendance"',
            '- "Open assessment results"',
            "",
            "Student Finance",
            '- "Show account balance for Jackson Moore"',
            '- "Open student billing"',
            "",
            "Safe Changes",
            "For create, update, enrollment, status, grade, attendance, or finance changes, I prepare a review first and execute only after your confirmation and permission checks.",
        ]
    )


def get_conversation_actions(intent):
    category = ((getattr(intent, "structured_intent", None) or {}).get("intent_category") or "").lower()
    return get_sis_quick_actions() if category in {"greeting", "help"} else []


def get_sis_quick_actions():
    return [
        student_action("Student 360", "Which student would you like me to review?", "Tell me about student {student}"),
        student_action("Enrollment", "Which student's enrollment should I show?", "Show enrollment for student {student}"),
        student_action("Courses & Grades", "Which student's courses and grades should I summarize?", "Summarize courses and grades for student {student}"),
        student_action("Account Balance", "Which student's account balance should I show?", "Show account balance for student {student}"),
        quick_action("Applications", "Open student applications"),
        quick_action("Attendance", "Open student attendance"),
    ]


def quick_action(label, message):
    return {
        "type": "send_message",
        "label": label,
        "payload": {"message": message},
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def student_action(label, question, message_template):
    return {
        "type": "collect_student",
        "label": label,
        "description": question,
        "payload": {
            "question": question,
            "message_template": message_template,
            "placeholder": "Type student name…",
        },
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }
