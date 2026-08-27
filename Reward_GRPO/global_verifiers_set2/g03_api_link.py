"""G03: manifest-driven Clang AST contract and trusted caller linkage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from receipt import PolicyReceipt, policy
from sandbox import CommandResult, Limits, result_facts

Execute = Callable[[list[str], Path, Limits, dict[str, str] | None], CommandResult]


def _walk(node: Any, scopes: tuple[str, ...] = ()):
    if isinstance(node, dict):
        kind = node.get("kind")
        name = node.get("name")
        node_scopes = scopes
        if kind in {"NamespaceDecl", "CXXRecordDecl", "ClassTemplateDecl"} and name:
            node_scopes = (*scopes, str(name))
        yield node, scopes
        for child in node.get("inner", []):
            yield from _walk(child, node_scopes)


def _load_contract(workspace: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    api = manifest.get("api", {})
    contract_name = api.get("contract", "public_api.json")
    if not isinstance(contract_name, str):
        return [], "INVALID_API_CONTRACT"
    try:
        contract = json.loads((workspace / contract_name).read_text())
    except (OSError, json.JSONDecodeError):
        return [], "INVALID_API_CONTRACT"
    if contract.get("contract_version") != manifest.get("contract_version"):
        return [], "API_CONTRACT_VERSION_MISMATCH"
    declarations = contract.get("declarations")
    if not isinstance(declarations, list):
        return [], "INVALID_API_CONTRACT"
    return declarations, None


def verify(workspace: Path, manifest: dict[str, Any], objects: list[str], execute: Execute,
           limits: Limits) -> tuple[PolicyReceipt, str | None]:
    api = manifest.get("api", {})
    build = manifest.get("build", {})
    header = api.get("candidate_header")
    caller = api.get("caller")
    required, contract_error = _load_contract(workspace, manifest)
    clang = str(api.get("clang", "clang++"))
    if contract_error:
        return policy("G03", "INVALID", contract_error), None
    if not isinstance(header, str) or not isinstance(caller, str):
        return policy("G03", "INVALID", "INVALID_API_CONTRACT"), None
    ast_command = [clang, f"-std={build.get('standard', 'c++17')}", "-I.",
                   "-Xclang", "-ast-dump=json", "-fsyntax-only", header]
    ast = execute(ast_command, workspace, limits, None)
    if ast.launch_error:
        return policy("G03", "INVALID", "CLANG_UNAVAILABLE", command=result_facts(ast)), None
    if ast.timed_out:
        return policy("G03", "INVALID", "AST_TIMEOUT", command=result_facts(ast)), None
    if ast.returncode != 0:
        return policy("G03", "FAIL", "API_PARSE_FAIL", command=result_facts(ast)), None
    try:
        nodes = list(_walk(json.loads(ast.stdout)))
    except json.JSONDecodeError:
        return policy("G03", "INVALID", "MALFORMED_CLANG_AST"), None
    missing: list[dict[str, str]] = []
    for expected in required:
        if not isinstance(expected, dict) or not isinstance(expected.get("name"), str):
            return policy("G03", "INVALID", "INVALID_API_DECLARATION") , None
        matched = [(node, scopes) for node, scopes in nodes
                   if node.get("name") == expected["name"]
                   and (not expected.get("kind") or node.get("kind") == expected["kind"])]
        namespace = expected.get("namespace", "")
        if not isinstance(namespace, str):
            return policy("G03", "INVALID", "INVALID_API_DECLARATION"), None
        expected_scope = tuple(part for part in namespace.split("::") if part)
        matched = [(node, scopes) for node, scopes in matched if scopes == expected_scope]
        type_fragment = expected.get("type_contains")
        if type_fragment:
            matched = [(node, scopes) for node, scopes in matched
                       if type_fragment in str(node.get("type", {}).get("qualType", ""))]
        if not matched:
            missing.append({key: str(value) for key, value in expected.items()})
    if missing:
        return policy("G03", "FAIL", "API_FAIL", missing_declarations=missing), None
    binary = ".gv2/api_link_test"
    command = [str(build.get("compiler", "g++")), f"-std={build.get('standard', 'c++17')}",
               *(str(value) for value in build.get("flags", [])), "-I.", caller, *objects,
               *(f"-l{value}" for value in build.get("libraries", [])), "-o", binary]
    linked = execute(command, workspace, limits, None)
    if linked.launch_error or linked.timed_out:
        return policy("G03", "INVALID", "LINKER_UNAVAILABLE_OR_TIMEOUT",
                      command=result_facts(linked)), None
    if linked.returncode != 0:
        return policy("G03", "FAIL", "LINK_FAIL", command=result_facts(linked)), None
    return policy("G03", "PASS", "API_LINKED", command=result_facts(linked), binary=binary), binary
