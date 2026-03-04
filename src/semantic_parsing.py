import os
import re
import json
import urllib.request
from textwrap import dedent
from sexpdata import loads, Symbol
from pydantic import create_model, BaseModel
from hyperon import *

special_symbols = [
    ":",
    "->"
]

built_in_ops = [
    "And",
    "Or",
    "Not",
    "Implication",
    "Equivalence",
    "Similarity",
    "STV",
    # "LikelierThan",
    "TemporalBefore",
    "TemporalAfter",
    "TemporalContained",
    "TemporalOverlap",
]

built_in_type_defs = [
    "(: And (-> Type Type Type))",
    "(: Or (-> Type Type Type))",
    "(: Not (-> Type Type))",
    "(: Implication (-> Type Type Type))",
    "(: Equivalence (-> Type Type Type))",
    "(: Similarity (-> Concept Concept Type))",
    "(: STV (-> Number Number TV))",
    # "(: LikelierThan (-> Type Type Type))",
    "(: TemporalBefore (-> Concept Concept Type))",
    "(: TemporalAfter (-> Concept Concept Type))",
    "(: TemporalContained (-> Concept Concept Type))",
    "(: TemporalOverlap (-> Concept Concept Type))",
]

class PLNExprs(BaseModel):
    type_defs: list[str]
    stmts: list[str]

class PLNQueryExprs(BaseModel):
    type_defs: list[str]
    stmts: list[str]
    queries: list[str]

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

expr_format_check_fn = """
(= (expr-format-check $expr)
   (unify $expr (: $x $y) True False))
""".strip()

stmt_format_check_fn = """
(= (stmt-format-check $expr)
   (unify $expr (: $prf $main (STV $s $c)) True False))
""".strip()

query_format_check_fn = """
(= (query-format-check $expr)
   (unify $expr (: $x $y $tv) True False))
""".strip()

metta = MeTTa()
metta.run(expr_format_check_fn)
metta.run(stmt_format_check_fn)
metta.run(query_format_check_fn)

def expr_format_check(expr):
    try:
        rtn = metta.run(f"!(expr-format-check {expr})")[0][0]
        if isinstance(rtn, GroundedAtom) and rtn.get_object().value == True:
            return (True, None)
    except Exception as e:
        print(f"Got an exception in expr_format_check for '{expr}': {e}")
        return (False, e)
    return (False, None)

def type_def_check(expr):
    expr = re.sub(r'\n\s*', ' ', expr)
    match = re.search(r'\(: .+ \(-> (.*)\)\)', expr)
    if not match:
        return False
    return True

def stmt_format_check(expr):
    try:
        rtn = metta.run(f"!(stmt-format-check {expr})")[0][0]
        if isinstance(rtn, GroundedAtom) and rtn.get_object().value == True:
            return (True, None)
    except Exception as e:
        print(f"Got an exception in stmt_format_check for '{expr}': {e}")
        return (False, e)
    return (False, None)

def query_format_check_1(expr):
    try:
        rtn = metta.run(f"!(query-format-check {expr})")[0][0]
        if isinstance(rtn, GroundedAtom) and rtn.get_object().value == True:
            return (True, None)
    except Exception as e:
        print(f"Got an exception in query_format_check_1 for '{expr}': {e}")
        return (False, e)
    return (False, None)

def query_format_check_2(expr):
    try:
        expr = re.sub(r'\n\s*', ' ', expr)
        match = re.search(r'\(: \$.+ \(.+\) \$.+\)', expr)
        if not match:
            return False
    except Exception as e:
        print(f"Got an exception in query_format_check_2 for '{expr}': {e}")
        return False
    return True

def metta_type_check(type_defs, stmt):
    temp_metta = MeTTa()
    try:
        for type_def in type_defs:
            type_def_atom = temp_metta.parse_all(type_def)[0]
            temp_metta.space().add_atom(type_def_atom)

        # try to type-check in MeTTa based on the given type definitions and see if we'll get an error
        rtn1 = temp_metta.run(f"!{stmt}")[0][0]
        rtn2 = temp_metta.run(f"!(car-atom {rtn1})")[0][0]
        if rtn2.get_name() == "Error":
            return (False, None)
        return (True, None)
    except Exception as e:
        print(f"Got an exception in metta_type_check for '{stmt}': {e}")
        return (False, e)

def unused_preds_check(type_defs, stmts):
    preds_used = list(set(sum([re.findall(r'\((.+?) ', re.sub(r'\n\s*', ' ', expr)) for expr in stmts], [])))
    preds_defined = list(set([re.search(r'\(: (.+?) \(-> ', re.sub(r'\n\s*', ' ', type_def)).group(1) for type_def in type_defs]))
    filtered_preds_used = [item for item in preds_used if item not in (built_in_ops + special_symbols) and not item.startswith('$')]
    filtered_preds_defined = [item for item in preds_defined if item not in (built_in_ops + special_symbols)]
    preds_defined_not_used = [item for item in filtered_preds_defined if item not in filtered_preds_used]
    if preds_defined_not_used:
        return (False, preds_defined_not_used)
    else:
        return (True, [])

def undefined_preds_check(type_defs, stmts):
    preds_used = list(set(sum([re.findall(r'\((.+?) ', re.sub(r'\n\s*', ' ', expr)) for expr in stmts], [])))
    preds_defined = list(set([re.search(r'\(: (.+?) \(-> ', re.sub(r'\n\s*', ' ', type_def)).group(1) for type_def in type_defs]))
    filtered_preds_used = [item for item in preds_used if item not in (built_in_ops + special_symbols) and not item.startswith('$')]
    filtered_preds_defined = [item for item in preds_defined if item not in (built_in_ops + special_symbols)]
    preds_used_not_defined = [item for item in filtered_preds_used if item not in filtered_preds_defined]
    if preds_used_not_defined:
        return (False, preds_used_not_defined)
    else:
        return (True, [])

def connectivity_check(stmts):
    def extract_elements(sexp):
        """
        Extract elements that are not predicates, also ignore:
        - strings
        - numbers
        - proof_names
        - variables
        """
        if sexp[0] == Symbol(":"):
            # ignore proof_names
            return extract_elements(sexp[1:])

        ele_lst = []
        # ignore predicates
        for ele in sexp[1:]:
            if isinstance(ele, list):
                ele_lst += extract_elements(ele)
            # ignore strings, numbers, etc that are not parsed as Symbols
            elif isinstance(ele, Symbol):
                # ignoring variables, assuming expressions should not be connected via a variable with the same name globally
                if not str(ele).startswith("$"):
                    ele_lst.append(str(ele))
        return ele_lst

    stmt_sexprs = [loads(stmt) for stmt in stmts]
    stmt_ele_lst = [extract_elements(sexpr) for sexpr in stmt_sexprs]

    # there could be exprs has no elements extracted, like an Implication rule with only predicates and variables, they can be excluded from connectivity check
    filtered_stmt_ele_lst = list(filter(lambda x: len(x) > 0, stmt_ele_lst))
    # print(f"Extracted elements (filtered): {filtered_stmt_ele_lst}")

    if len(filtered_stmt_ele_lst) <= 1:
        return True

    connected = {0}
    while True:
        new_connections = set()
        for i in connected:
            for j, other_list in enumerate(filtered_stmt_ele_lst):
                if j not in connected and set(filtered_stmt_ele_lst[i]) & set(other_list):
                    new_connections.add(j)
        if not new_connections:
            break
        connected.update(new_connections)

    return True if len(connected) == len(filtered_stmt_ele_lst) else False

def format_check_correct(openai_outputs, chat_history, output_format, max_back_forth=10, related_exprs={}):
    while True:
        attempts = int((len(chat_history)-1)/2)
        print(f"[attempts = {attempts}]")

        type_defs = openai_outputs["type_defs"]
        stmts = openai_outputs["stmts"] if "stmts" in openai_outputs else openai_outputs["rules"]
        queries = openai_outputs["queries"] if "queries" in openai_outputs else []

        if attempts > max_back_forth:
            print(f"Maximum back-and-forth's ({max_back_forth} times) with the LLM has reached!")
            return None

        print(f"Format checking for:\n```\ntype_defs = {type_defs}\nstmts = {stmts}\nqueries = {queries}\n```\n")

        type_def_check_pass = True
        for type_def in type_defs:
            expr_check_result, expr_check_exception = expr_format_check(type_def)
            e = "" if expr_check_exception == None else f"{expr_check_exception}".strip()
            if not (expr_check_result and type_def_check(type_def)):
                print(f"... retrying type_def_check for type_def '{type_def}'\n")
                openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"One of your type_defs ('{type_def}') doesn't pass the format check" + (f" with an exception '{e}', " if e else ", ") + "please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
                type_def_check_pass = False
                break
        if not type_def_check_pass:
            continue

        stmts_check_pass = True
        for stmt in stmts:
            stmt_check_result, stmt_check_exception = stmt_format_check(stmt)
            e = "" if stmt_check_exception == None else f"{stmt_check_exception}".strip()
            if not stmt_check_result:
                print(f"... retrying stmt_format_check for stmt '{stmt}'\n")
                openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"One of your stmts ('{stmt}') doesn't pass the format check" + (f" with an exception '{e}', " if e else ", ") + "please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
                stmts_check_pass = False
                break
        if not stmts_check_pass:
            continue

        query_check_pass = True
        for query in queries:
            query_check_result, query_check_exception = query_format_check_1(query)
            e = "" if query_check_exception == None else f"{query_check_exception}".strip()
            if not query_check_result:
                print(f"... retrying query_format_check_1 for query '{query}'\n")
                openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"One of your queries ('{query}') doesn't pass the format check" + (f" with an exception '{e}', " if e else ", ") + "please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
                query_check_pass = False
                break
            if not query_format_check_2(query):
                print(f"... retrying query_format_check_2 for query '{query}'\n")
                openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"Make sure the proof name and the truth value of your query '{query}' are variables in order to make it a valid query. Please make the improvement and regenerate all the output fields."), output_format=output_format, history=chat_history)
                query_check_pass = False
                break
        if not query_check_pass:
            continue

        # # TODO: temporarily disable type-checking to reduce LLM calls as we're not strictly using it at the moment
        # metta_type_check_pass = True
        # for expr in stmts + queries:
        #     check_result, check_exception = metta_type_check(type_defs + built_in_type_defs, expr)
        #     e = "" if check_exception == None else f"{check_exception}".strip()
        #     if not check_result:
        #         print(f"... retrying metta_type_check for: {expr} | {type_defs}\n")
        #         openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"One of your PLN expressions ('{expr}') doesn't pass type checking in the system based on your type_defs ({type_defs})" + (f" with an exception '{e}', " if e else ", ") + "please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
        #         metta_type_check_pass = False
        #         break
        # if not metta_type_check_pass:
        #     continue

        rtn = unused_preds_check(
            type_defs + (related_exprs["type_defs"] if related_exprs else []),
            stmts + queries + ((related_exprs["stmts"] + related_exprs["queries"]) if related_exprs else [])
        )
        if not rtn[0]:
            print(f"... retrying for unused_preds: {rtn[1]}\n")
            openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"You have defined one or more predicates but left unused:\n{rtn[1]}\n\nPlease make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
            continue

        rtn = undefined_preds_check(
            type_defs + (related_exprs["type_defs"] if related_exprs else []),
            stmts + queries + ((related_exprs["stmts"] + related_exprs["queries"]) if related_exprs else [])
        )
        if not rtn[0]:
            print(f"... retrying for undefined_preds: {rtn[1]}\n")
            openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"You have used one or more predicates that are not defined:\n{rtn[1]}\n\nPlease make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
            continue

        if not connectivity_check(stmts + (related_exprs["stmts"] if related_exprs else [])):
            print(f"... retrying for connectivity_check for: {stmts}\n")
            openai_outputs = to_openrouter(create_nl2pln_correction_prompt(f"Some of your 'stmts' are disconnected from the rest. Please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
            continue

        print(f"PASSED FORMAT CHECK!!\n")
        break

    return (type_defs, stmts, queries)

def nl2pln(system_prompt, context, input_text, mode="parsing", max_back_forth=10):
    output_format = PLNQueryExprs if mode == "querying" else PLNExprs

    if input_text == "(@ none)":
        return ""

    print(f'\n... parsing "{input_text}" | context: {context}\n')

    chat_history = [{
        "role": "system",
        "content": system_prompt
    }]

    llm_outputs = to_openrouter(create_nl2pln_parsing_prompt(input_text, context), output_format=output_format, history=chat_history)

    if mode == "querying":
        while (len(chat_history)-1)/2 > max_back_forth:
            if (not llm_outputs["queries"]):
                llm_outputs = to_openrouter(create_nl2pln_correction_prompt(f"Make sure you structure one or more queries from the `input_question` and return it in the 'queries' output field. Please make the correction and regenerate all the output fields."), output_format=output_format, history=chat_history)
                continue
            break

    type_defs, stmts, queries = format_check_correct(llm_outputs, chat_history, output_format, max_back_forth=max_back_forth)

    # TODO
    # sent_links = [f'(SentenceLink {re.search(r'\(: (.+?) \(.+\)\)', re.sub(r'\n\s*', ' ', stmt)).group(1)} "{input_text}")' for stmt in stmts]

    print(f"### {input_text} ###\n```", *(type_defs + stmts + queries), "```\n", sep="\n")

    # TODO
    # return (type_defs, stmts, queries, sent_links)
    return (type_defs, stmts, queries)
