DEFAULT_DOUBAO_MODEL = "doubao-seed-2-0-mini-260215"


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


def extract_response_text(response):
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            if getattr(content_item, "type", "") == "output_text":
                text = getattr(content_item, "text", "")
                if text:
                    return text.strip()

    return ""
