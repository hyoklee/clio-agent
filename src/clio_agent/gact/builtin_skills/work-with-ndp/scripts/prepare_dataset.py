"""Prepare a new NDP dataset body from selected receipts/resources; never call an API."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

MAX_JSON_BYTES = 2 * 1024 * 1024


def read_json(path: Path) -> Any:
    """Read a bounded UTF-8 JSON input without modifying it."""
    with path.open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"Input exceeds 2 MiB: {path.name}")
    return json.loads(raw.decode("utf-8-sig"))


def resource_descriptor(value: Any) -> dict[str, Any]:
    """Validate a hosted descriptor, retaining only new-resource catalog fields."""
    if not isinstance(value, dict):
        raise ValueError("Each resource must be a JSON object")
    for field in ("name", "url"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(f"Resource {field} must be a nonempty string")
    url = urlsplit(value["url"])
    if url.scheme not in {"https", "http", "s3", "pelican", "osdf"} or not url.hostname:
        raise ValueError("Resource needs a hosted HTTP, S3 or Pelican location")
    if url.username or url.password:
        raise ValueError("Resource locations must not embed credentials")
    credential_keys = {"token", "access_token", "api_key", "signature", "awsaccesskeyid"}
    if any(
        key.lower() in credential_keys or key.lower().startswith("x-amz-")
        for key, _ in parse_qsl(url.query)
    ):
        raise ValueError("Use a stable resource location without signed/credential query fields")
    result = {"name": value["name"], "url": value["url"]}
    for field in ("format", "mimetype", "description"):
        if field in value:
            if not isinstance(value[field], str):
                raise ValueError(f"Resource {field} must be a string")
            result[field] = value[field]
    if "size" in value:
        if type(value["size"]) is not int or value["size"] < 0:
            raise ValueError("Resource size must be a nonnegative integer")
        result["size"] = value["size"]
    return result


def verified_upload(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract a descriptor and provenance only from a complete verified upload receipt."""
    if not isinstance(value, dict) or value.get("state") != "verified":
        raise ValueError("Upload receipts must have state=verified")
    for field in ("id", "artifact_id", "endpoint_id", "bucket", "key"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(f"Upload receipt is missing {field}")
    if not isinstance(value.get("sha256"), str) or not re.fullmatch(
        r"[a-fA-F0-9]{64}", value["sha256"]
    ):
        raise ValueError("Upload receipt needs its SHA-256")
    resource = resource_descriptor(value.get("resource"))
    if type(value.get("size")) is not int or value["size"] < 0:
        raise ValueError("Upload receipt needs its nonnegative byte size")
    expected_url = f"s3://{value['bucket']}/{quote(value['key'], safe='/')}"
    if resource["url"] != expected_url or resource.get("size") != value["size"]:
        raise ValueError("Upload receipt location/size disagrees with its resource descriptor")
    provenance = {
        field: value[field] for field in ("id", "artifact_id", "endpoint_id", "sha256", "size")
    }
    provenance["url"] = resource["url"]
    return resource, provenance


def prepare_dataset(
    *,
    name: str,
    title: str,
    organization: str,
    receipts: list[Any],
    resources: list[Any],
    private: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    """Assemble one requested new collection, separating its body from local evidence."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,99}", name):
        raise ValueError("Use a 2-100 character lowercase dataset slug")
    if not title.strip() or not organization.strip():
        raise ValueError("A title and resolved organization are required")
    descriptors, uploads = [], []
    for receipt in receipts:
        descriptor, provenance = verified_upload(receipt)
        descriptors.append(descriptor)
        uploads.append(provenance)
    descriptors.extend(resource_descriptor(resource) for resource in resources)
    if not descriptors:
        raise ValueError("Select at least one resource or verified upload receipt")
    locations = [resource["url"] for resource in descriptors]
    if len(locations) != len(set(locations)):
        raise ValueError("Duplicate resource locations: resolve the selection before creating")
    return {
        "dataset": {
            "name": name,
            "title": title,
            "owner_org": organization,
            "notes": notes,
            "private": private,
            "resources": descriptors,
        },
        "evidence": {
            "state": "prepared_only",
            "uploads": uploads,
            "external_resources_not_checked": len(resources),
        },
    }


def main() -> None:
    """Print prepared JSON to stdout; CLI failures produce no partial request body."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--organization", required=True, help="Resolved catalog publisher ID/name")
    parser.add_argument("--receipt", type=Path, action="append", default=[])
    parser.add_argument("--resources", type=Path, help="JSON array of already hosted descriptors")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--public", action="store_true", help="Use only for requested public visibility"
    )
    args = parser.parse_args()
    try:
        resources = read_json(args.resources) if args.resources else []
        if not isinstance(resources, list):
            raise ValueError("--resources must contain a JSON array")
        result = prepare_dataset(
            name=args.name,
            title=args.title,
            organization=args.organization,
            receipts=[read_json(path) for path in args.receipt],
            resources=resources,
            private=not args.public,
            notes=args.notes,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f"Cannot prepare dataset: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
