"""ShellGuard CLI — policy CRUD, sandbox diagnostics, and user sync."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from typing import Any

import httpx


def get_base_url() -> str:
    return os.environ.get("SHELLGUARD_URL", "http://localhost:8080")


def get_api_key() -> str:
    key = os.environ.get("SHELLGUARD_API_KEY", "")
    if not key:
        print("Error: SHELLGUARD_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    return key


def make_client() -> httpx.Client:
    return httpx.Client(
        base_url=get_base_url(),
        headers={"Authorization": f"Bearer {get_api_key()}"},
        timeout=30.0,
    )


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def print_table(rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    """Print a list of dicts as an aligned table."""
    if not rows:
        print("(no results)")
        return

    if columns is None:
        columns = list(rows[0].keys())

    # Compute column widths
    widths: dict[str, int] = {}
    for col in columns:
        widths[col] = max(
            len(col),
            *(len(str(row.get(col, ""))) for row in rows),
        )

    # Header
    header = "  ".join(col.upper().ljust(widths[col]) for col in columns)
    print(header)
    print("  ".join("-" * widths[col] for col in columns))

    # Rows
    for row in rows:
        line = "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)


def output(data: Any, fmt: str, table_columns: list[str] | None = None) -> None:
    """Route output to JSON or table formatter."""
    if fmt == "json":
        print_json(data)
    else:
        if isinstance(data, list):
            print_table(data, columns=table_columns)
        elif isinstance(data, dict):
            # Single record — print key/value pairs
            max_key = max(len(k) for k in data) if data else 0
            for k, v in data.items():
                print(f"{k.ljust(max_key)}  {v}")
        else:
            print(data)


def api_request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
) -> Any:
    """Perform an HTTP request and return parsed JSON, or exit on error."""
    try:
        response = client.request(method, path, json=json_body)
    except httpx.HTTPError as exc:
        print(f"Error: HTTP request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if response.status_code >= 400:
        print(
            f"Error: {method} {path} returned {response.status_code}",
            file=sys.stderr,
        )
        try:
            detail = response.json()
            print(json.dumps(detail, indent=2), file=sys.stderr)
        except Exception:
            print(response.text, file=sys.stderr)
        sys.exit(1)

    if response.status_code == 204 or not response.content:
        return None

    return response.json()


# ── Policy subcommands ──────────────────────────────────────────────


def cmd_policy_list(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "GET", "/admin/api/policies")
    output(data, args.format, table_columns=["id", "name", "status", "version", "updated_at"])


def cmd_policy_get(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "GET", f"/admin/api/policies/{args.id}")
    output(data, args.format)


def cmd_policy_validate(args: argparse.Namespace) -> None:
    yaml_path = args.yaml_file
    try:
        with open(yaml_path, "r") as f:
            yaml_content = f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: cannot read file: {exc}", file=sys.stderr)
        sys.exit(1)

    with make_client() as client:
        data = api_request(
            client,
            "POST",
            "/admin/api/policies/validate",
            json_body={"yaml": yaml_content},
        )
    output(data, args.format)


def cmd_policy_diff(args: argparse.Namespace) -> None:
    with make_client() as client:
        v1_data = api_request(
            client, "GET", f"/admin/api/policies/{args.id}/versions/{args.v1}"
        )
        v2_data = api_request(
            client, "GET", f"/admin/api/policies/{args.id}/versions/{args.v2}"
        )

    v1_def = v1_data.get("yaml", "")
    v2_def = v2_data.get("yaml", "")

    diff = difflib.unified_diff(
        v1_def.splitlines(keepends=True),
        v2_def.splitlines(keepends=True),
        fromfile=f"version {args.v1}",
        tofile=f"version {args.v2}",
    )
    result = "".join(diff)
    if result:
        print(result)
    else:
        print("No differences found.")


# ── Sandbox subcommands ─────────────────────────────────────────────


def cmd_sandbox_list(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "GET", "/admin/api/sandboxes")
    output(data, args.format, table_columns=["id", "user_id", "status", "image_tag", "created_at"])


def cmd_sandbox_inspect(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "GET", f"/admin/api/sandboxes/{args.id}")
    output(data, args.format)


def cmd_sandbox_suspend(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "POST", f"/admin/api/sandboxes/{args.id}/suspend")
    if data is not None:
        output(data, args.format)
    else:
        print(f"Sandbox {args.id} suspended.")


def cmd_sandbox_destroy(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "DELETE", f"/admin/api/sandboxes/{args.id}")
    if data is not None:
        output(data, args.format)
    else:
        print(f"Sandbox {args.id} destroyed.")


# ── User subcommands ────────────────────────────────────────────────


def cmd_user_sync(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "POST", "/admin/api/users/sync")
    if data is not None:
        output(data, args.format)
    else:
        print("User sync completed.")


def cmd_user_list(args: argparse.Namespace) -> None:
    with make_client() as client:
        data = api_request(client, "GET", "/admin/api/users")
    output(data, args.format, table_columns=["id", "email", "name", "role", "status"])


# ── Argument parser ─────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shellguard-cli",
        description="ShellGuard CLI — manage policies, sandboxes, and users",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Top-level command")

    # ── policy ──
    policy_parser = subparsers.add_parser("policy", help="Manage security policies")
    policy_sub = policy_parser.add_subparsers(dest="subcommand", help="Policy subcommand")

    policy_sub.add_parser("list", help="List all policies")

    p_get = policy_sub.add_parser("get", help="Get a single policy by ID")
    p_get.add_argument("id", help="Policy ID")

    p_validate = policy_sub.add_parser("validate", help="Validate a YAML policy file")
    p_validate.add_argument("yaml_file", help="Path to YAML policy file")

    p_diff = policy_sub.add_parser("diff", help="Diff two versions of a policy")
    p_diff.add_argument("id", help="Policy ID")
    p_diff.add_argument("v1", help="First version number")
    p_diff.add_argument("v2", help="Second version number")

    # ── sandbox ──
    sandbox_parser = subparsers.add_parser("sandbox", help="Manage sandboxes")
    sandbox_sub = sandbox_parser.add_subparsers(dest="subcommand", help="Sandbox subcommand")

    sandbox_sub.add_parser("list", help="List all sandboxes")

    s_inspect = sandbox_sub.add_parser("inspect", help="Inspect a sandbox")
    s_inspect.add_argument("id", help="Sandbox ID")

    s_suspend = sandbox_sub.add_parser("suspend", help="Suspend a sandbox")
    s_suspend.add_argument("id", help="Sandbox ID")

    s_destroy = sandbox_sub.add_parser("destroy", help="Destroy a sandbox")
    s_destroy.add_argument("id", help="Sandbox ID")

    # ── user ──
    user_parser = subparsers.add_parser("user", help="Manage users")
    user_sub = user_parser.add_subparsers(dest="subcommand", help="User subcommand")

    user_sub.add_parser("sync", help="Sync users from Open WebUI")
    user_sub.add_parser("list", help="List all users")

    return parser


# ── Dispatch table ──────────────────────────────────────────────────

DISPATCH = {
    ("policy", "list"): cmd_policy_list,
    ("policy", "get"): cmd_policy_get,
    ("policy", "validate"): cmd_policy_validate,
    ("policy", "diff"): cmd_policy_diff,
    ("sandbox", "list"): cmd_sandbox_list,
    ("sandbox", "inspect"): cmd_sandbox_inspect,
    ("sandbox", "suspend"): cmd_sandbox_suspend,
    ("sandbox", "destroy"): cmd_sandbox_destroy,
    ("user", "sync"): cmd_user_sync,
    ("user", "list"): cmd_user_list,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not args.subcommand:
        # Print help for the specific command group
        parser.parse_args([args.command, "--help"])
        sys.exit(1)

    handler = DISPATCH.get((args.command, args.subcommand))
    if handler is None:
        print(f"Error: unknown command: {args.command} {args.subcommand}", file=sys.stderr)
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
