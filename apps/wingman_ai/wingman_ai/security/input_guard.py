MAX_MESSAGE_LENGTH = 4000


class InputValidationError(ValueError):
    pass


def validate_user_message(message):
    text = (message or "").strip()
    if not text:
        raise InputValidationError("Please enter a message for Wingman.")

    if len(text) > MAX_MESSAGE_LENGTH:
        raise InputValidationError("Your message is too long. Please shorten it and try again.")

    return text

