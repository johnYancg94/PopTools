DEFAULT_DOUBAO_MODEL = "doubao-seed-2-0-mini-260215"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


def _read_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _content_to_text(content):
    if not content:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", "") or item.get("content", ""))
            else:
                parts.append(getattr(item, "text", "") or getattr(item, "content", ""))
        return "".join(parts).strip()

    return str(content).strip()


def build_translation_input(system_prompt, user_text):
    return [
        {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": system_prompt,
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": user_text,
                }
            ],
        },
    ]


def build_chat_messages(system_prompt, user_text):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]


def extract_response_text(response):
    output_text = _read_value(response, "output_text", None)
    if output_text:
        return _content_to_text(output_text)

    for output_item in _read_value(response, "output", []) or []:
        output_type = _read_value(output_item, "type", "")
        if output_type == "message" or _read_value(output_item, "content", None):
            for content_item in _read_value(output_item, "content", []) or []:
                content_type = _read_value(content_item, "type", "")
                if content_type in {"output_text", "text"}:
                    text = _read_value(content_item, "text", "")
                    if text:
                        return _content_to_text(text)

        if output_type in {"output_text", "text"}:
            text = _read_value(output_item, "text", "")
            if text:
                return _content_to_text(text)

    choices = _read_value(response, "choices", None)
    if choices:
        return extract_chat_completion_text(response)

    data = _read_value(response, "data", None)
    if isinstance(data, dict):
        text = extract_response_text(data)
        if text:
            return text

    return ""


def summarize_response(response):
    output_text = _content_to_text(_read_value(response, "output_text", None))[:120]
    output = _read_value(response, "output", []) or []
    output_summary = []
    for output_item in output[:3]:
        output_type = _read_value(output_item, "type", "")
        content = _read_value(output_item, "content", []) or []
        content_summary = []
        for content_item in content[:3]:
            content_type = _read_value(content_item, "type", "")
            text = _content_to_text(_read_value(content_item, "text", ""))[:80]
            content_summary.append(f"{content_type}:{text}")
        output_summary.append(f"{output_type}[{'; '.join(content_summary)}]")

    choices = _read_value(response, "choices", []) or []
    choices_summary = ""
    if choices:
        choice_text = extract_chat_completion_text(response)[:120]
        choices_summary = f", choices_text='{choice_text}'"

    return f"output_text='{output_text}', output={output_summary}{choices_summary}"


def extract_chat_completion_text(response):
    choices = _read_value(response, "choices", []) or []
    if not choices:
        return ""

    first_choice = choices[0]
    message = _read_value(first_choice, "message", None)
    if not message:
        delta = _read_value(first_choice, "delta", None)
        if not delta:
            return ""
        text = _content_to_text(_read_value(delta, "content", ""))
        if text:
            return text
        return ""

    text = _content_to_text(_read_value(message, "content", ""))
    if text:
        return text

    return ""


def summarize_chat_completion_response(response):
    choices = _read_value(response, "choices", []) or []
    if not choices:
        return "choices=[]"

    first_choice = choices[0]
    message = _read_value(first_choice, "message", None)
    finish_reason = _read_value(first_choice, "finish_reason", None)
    if not message:
        return f"finish_reason={finish_reason}, message=None"

    content = _read_value(message, "content", None)
    reasoning_content = _read_value(message, "reasoning_content", None)
    content_preview = _content_to_text(content)[:120]
    reasoning_preview = _content_to_text(reasoning_content)[:120]
    return (
        f"finish_reason={finish_reason}, "
        f"content_type={type(content).__name__}, content_preview='{content_preview}', "
        f"reasoning_preview='{reasoning_preview}'"
    )
