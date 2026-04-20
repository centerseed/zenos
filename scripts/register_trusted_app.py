#!/usr/bin/env python3
"""Admin script: register a trusted application for federation.

Usage:
    python scripts/register_trusted_app.py \\
        --app-name "my-app" \\
        --app-secret "my-secret" \\
        --issuers "https://securetoken.google.com/my-project" \\
        --default-workspace-id "<partner-id>" \\
        --scopes "read,write" \\
        --auto-link-domains "zentropy.app"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()


async def main(
    app_name: str,
    app_secret: str,
    issuers: list[str],
    scopes: list[str],
    default_workspace_id: str,
    auto_link_domains: list[str],
) -> None:
    from zenos.infrastructure.sql_common import get_pool
    from zenos.infrastructure.identity import (
        SqlTrustedAppRepository,
        SqlIdentityLinkRepository,
        SqlPartnerRepository,
        SqlPendingIdentityLinkRepository,
        JwtService,
    )
    from zenos.application.identity.federation_service import FederationService

    pool = await get_pool()
    service = FederationService(
        trusted_app_repo=SqlTrustedAppRepository(pool),
        identity_link_repo=SqlIdentityLinkRepository(pool),
        partner_repo=SqlPartnerRepository(pool),
        jwt_service=JwtService(),
        pending_link_repo=SqlPendingIdentityLinkRepository(pool),
    )

    result = await service.register_trusted_app(
        app_name=app_name,
        app_secret=app_secret,
        allowed_issuers=issuers,
        allowed_scopes=scopes,
        default_workspace_id=default_workspace_id,
        auto_link_email_domains=auto_link_domains,
    )

    if "error" in result:
        print(f"ERROR: {result['error']} — {result.get('message', '')}", file=sys.stderr)
        sys.exit(1)

    print("Trusted app registered successfully:")
    print(f"  app_id:                   {result['app_id']}")
    print(f"  app_name:                 {result['app_name']}")
    print(f"  allowed_issuers:          {result['allowed_issuers']}")
    print(f"  allowed_scopes:           {result['allowed_scopes']}")
    print(f"  default_workspace_id:     {result['default_workspace_id']}")
    print(f"  auto_link_email_domains:  {result['auto_link_email_domains']}")
    print(f"  status:                   {result['status']}")
    print()
    print("IMPORTANT: store the app_secret securely — it cannot be recovered.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a trusted app for ZenOS federation")
    parser.add_argument("--app-name", required=True, help="Unique application name")
    parser.add_argument("--app-secret", required=True, help="Plain-text secret (will be bcrypt-hashed)")
    parser.add_argument("--issuers", required=True, help="Comma-separated list of allowed token issuers")
    parser.add_argument("--default-workspace-id", required=True, help="Workspace partner ID for auto-provisioning")
    parser.add_argument("--scopes", default="read", help="Comma-separated list of allowed scopes (default: read)")
    parser.add_argument("--auto-link-domains", default="", help="Comma-separated list of email domains for auto-link (e.g. zentropy.app)")
    args = parser.parse_args()

    issuers = [i.strip() for i in args.issuers.split(",") if i.strip()]
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    auto_link_domains = [d.strip() for d in args.auto_link_domains.split(",") if d.strip()]

    asyncio.run(main(args.app_name, args.app_secret, issuers, scopes, args.default_workspace_id, auto_link_domains))
