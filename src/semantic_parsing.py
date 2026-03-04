import os
import re
import json
import urllib.request
from textwrap import dedent
from pydantic import create_model, BaseModel

class PLNExprs(BaseModel):
    type_defs: list[str]
    stmts: list[str]

class PLNQueryExprs(BaseModel):
    type_defs: list[str]
    stmts: list[str]
    queries: list[str]

def to_openrouter(prompt, model = "openai/gpt-5.2", effort = "high", history = [], output_format = create_model('StrResp', response=(str, ...))):
    history.append({"role": "user", "content": prompt})
    key = os.environ.get('OPENROUTER_API_KEY', '')
    schema = output_format.model_json_schema()
    data = json.dumps({
        'model': model,
        'messages': history,
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': schema.get('title', 'response'),
                'strict': True,
                'schema': schema
            }
        },
        'reasoning': {'effort': effort}
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data,
        {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    )
    content = json.loads(urllib.request.urlopen(req).read())['choices'][0]['message']['content']
    history.append({"role": "assistant", "content": content})
    return json.loads(content)

def create_nl2pln_parsing_prompt(text, context):
    return dedent(f"""
        <context>
        {context.strip()}
        </context>

        <input_text>
        {text}
        </input_text>
        """).strip()

def create_nl2pln_querying_prompt(text, context):
    return dedent(f"""
        <context>
        {context.strip()}
        </context>

        <input_question>
        {text}
        </input_question>
        """).strip()

def create_nl2pln_correction_prompt(correction):
    return dedent(f"""
        <correction_comments>
        {correction}
        </correction_comments>
        """).strip()

def nl2pln(system_prompt, context, input_text, mode="parsing", max_back_forth=10):
    output_format = PLNQueryExprs if mode == "querying" else PLNExprs

    print(f'\n... parsing "{input_text}" | context: {context}')

    chat_history = [{
        "role": "system",
        "content": system_prompt
    }]

    llm_outputs = to_openrouter(create_nl2pln_parsing_prompt(input_text, context), output_format=output_format, history=chat_history)

    if mode == "querying":
        while (len(chat_history)-1)/2 > max_back_forth:
            if (not llm_outputs["queries"]):
                llm_outputs = to_openai(create_nl2pln_correction_prompt(f"Make sure you structure one or more queries from the `input_question` and return it in the 'queries' output field. Please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
                continue
            break

    # TODO: re-enable later
    # type_defs, stmts, queries = format_check_correct(llm_outputs, chat_history, output_format, max_back_forth=max_back_forth)
    type_defs, stmts, queries = llm_outputs["type_defs"], llm_outputs["stmts"], (llm_outputs["queries"] if mode == "querying" else [])

    sent_links = [f'(SentenceLink {re.search(r'\(: (.+?) \(.+\)\)', re.sub(r'\n\s*', ' ', stmt)).group(1)} "{input_text}")' for stmt in stmts]

    return (type_defs, stmts, queries, sent_links)
