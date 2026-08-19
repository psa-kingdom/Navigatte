#!/usr/bin/env python3
"""
Remote deployment smoke test script.
Verifies CORS preflights, cross-origin authentication, and API contract between
a Vercel Preview/Production frontend URL and a Railway/Deployed backend URL.

Usage:
  python scripts/smoke_test_deployment.py --frontend https://preview.vercel.app --backend https://backend.up.railway.app
"""

import argparse
import sys
import urllib.error
import urllib.request


def test_cors_preflight(backend_url: str, frontend_origin: str, path: str = "/api/auth/login") -> bool:
    target_url = f"{backend_url.rstrip('/')}{path}"
    headers = {
        "Origin": frontend_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    }
    req = urllib.request.Request(target_url, headers=headers, method="OPTIONS")
    print(f"\n[1] Testing OPTIONS Preflight: {target_url} from {frontend_origin}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            allow_origin = resp.headers.get("access-control-allow-origin")
            allow_creds = resp.headers.get("access-control-allow-credentials")
            print(f"    Status: {resp.status}")
            print(f"    Access-Control-Allow-Origin: {allow_origin}")
            print(f"    Access-Control-Allow-Credentials: {allow_creds}")

            if allow_origin == frontend_origin and allow_creds == "true":
                print("    -> PASS: Allowed origin and credentials returned.")
                return True
            else:
                print(f"    -> FAIL: Origin '{allow_origin}' != '{frontend_origin}' or creds != 'true'")
                return False
    except urllib.error.HTTPError as e:
        allow_origin = e.headers.get("access-control-allow-origin")
        print(f"    HTTPError: {e.code} ({e.reason})")
        print(f"    Access-Control-Allow-Origin: {allow_origin}")
        print("    -> FAIL: Preflight request was rejected by server.")
        return False
    except Exception as ex:
        print(f"    -> ERROR: {ex}")
        return False


def test_untrusted_origin_rejection(backend_url: str, untrusted_origin: str = "https://attacker.com") -> bool:
    target_url = f"{backend_url.rstrip('/')}/api/auth/login"
    headers = {
        "Origin": untrusted_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    req = urllib.request.Request(target_url, headers=headers, method="OPTIONS")
    print(f"\n[2] Testing Untrusted Origin Rejection: {untrusted_origin}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            allow_origin = resp.headers.get("access-control-allow-origin")
            if allow_origin != untrusted_origin:
                print(f"    Status: {resp.status} (Allow-Origin: {allow_origin})")
                print("    -> PASS: Untrusted origin was NOT allowed.")
                return True
            else:
                print("    -> FAIL: Untrusted origin was permitted in Allow-Origin!")
                return False
    except urllib.error.HTTPError as e:
        allow_origin = e.headers.get("access-control-allow-origin")
        if allow_origin != untrusted_origin:
            print(f"    HTTP {e.code} (Allow-Origin: {allow_origin})")
            print("    -> PASS: Untrusted origin was rejected.")
            return True
        else:
            print("    -> FAIL: Untrusted origin was permitted!")
            return False
    except Exception as ex:
        print(f"    -> ERROR: {ex}")
        return False


def test_api_status(backend_url: str) -> bool:
    target_url = f"{backend_url.rstrip('/')}/api/"
    print(f"\n[3] Testing Backend Root Status: {target_url}")
    try:
        with urllib.request.urlopen(target_url, timeout=10) as resp:
            body = resp.read().decode()
            print(f"    Status: {resp.status} | Body: {body.strip()}")
            return resp.status == 200
    except Exception as ex:
        print(f"    -> ERROR: {ex}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Navigatte Deployment Smoke Test")
    parser.add_argument(
        "--frontend",
        default="https://navigatte-website-9wrbgnni9-psumanassociates-9980s-projects.vercel.app",
        help="Frontend Preview/Production origin",
    )
    parser.add_argument(
        "--backend",
        default="https://navigatte-website-production.up.railway.app",
        help="Backend Railway/Production URL",
    )
    args = parser.parse_args()

    print(f"=== NAVIGATTE DEPLOYMENT SMOKE TEST ===")
    print(f"Frontend Origin: {args.frontend}")
    print(f"Backend URL:     {args.backend}")

    results = [
        test_api_status(args.backend),
        test_cors_preflight(args.backend, args.frontend),
        test_untrusted_origin_rejection(args.backend),
    ]

    all_passed = all(results)
    print("\n" + "=" * 45)
    if all_passed:
        print("ALL DEPLOYMENT SMOKE CHECKS PASSED.")
        sys.exit(0)
    else:
        print("SOME SMOKE CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
