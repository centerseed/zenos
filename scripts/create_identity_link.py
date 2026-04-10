#!/usr/bin/env python3
"""Admin script: create an identity link between an external user and a ZenOS principal.

Usage:
    python scripts/create_identity_link.py \\
        --app-id "uuid-of-trusted-app" \\
        --issuer "https://securetoken.google.com/my-project" \\
        --external-user-id "firebase-uid-123" \\
        --principal-id "zenos-partner-uuid" \\
        --email "user@example.com"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()


async def main(
    app_id: str,
    issuer: str,
    external_user_id: str,
    principal_id: str,
    email: str | None,
) -> None:
    from zenos.infrastructure.sql_common import get_pool
    from zenos.infrastructure.identity import SqlTrustedAppRepository, SqlIdentityLinkRepository, SqlPartnerRepository, JwtService
    from zenos.application.identity.federation_service import FederationService

    pool = await get_pool()
    service = FederationService(
        trusted_app_repo=SqlTrustedAppRepository(pool),
        identity_link_repo=SqlIdentityLinkRepository(pool),
        partner_repo=SqlPartnerRepository(pool),
        jwt_service=JwtService(),
    )

    result = await service.create_identity_link(
        app_id=app_id,
        issuer=issuer,
        external_user_id=external_user_id,
        zenos_principal_id=principal_id,
        email=email,
    )

    if "error" in result:
        print(f"ERROR: {result['error']} — {result.get('message', '')}", file=sys.stderr)
        sys.exit(1)

    print("Identity link created successfully:")
    print(f"  id:                 {result['id']}")
    print(f"  app_id:             {result['app_id']}")
    print(f"  issuer:             {result['issuer']}")
    print(f"  external_user_id:   {result['external_user_id']}")
    print(f"  zenos_principal_id: {result['zenos_principal_id']}")
    print(f"  email:              {result['email']}")
    print(f"  status:             {result['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an identity link for ZenOS federation")
    parser.add_argument("--app-id", required=True, help="UUID of the trusted app")
    parser.add_argument("--issuer", required=True, help="Token issuer (e.g. Firebase project URL)")
    parser.add_argument("--external-user-id", required=True, help="External identity provider user ID")
    parser.add_argument("--principal-id", required=True, help="ZenOS partner UUID to link to")
    parser.add_argument("--email", default=None, help="Optional email for reference")
    args = parser.parse_args()

    asyncio.run(main(args.app_id, args.issuer, args.external_user_id, args.principal_id, args.email))
