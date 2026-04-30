"""
tests/e2e/test_profile_persistence.py

Regression tests for the StealthRole core flow stabilization:

  K1 — `location` is no longer a phantom field. The PATCH and apply-import
       paths must store location inside `global_context` (no DB column).
  K3 — `apply-import` writes a single normalized `education` block (no
       duplicate overwrite).
  K4 — `apply-import` no longer issues an explicit double-commit; the
       request-scope session commit must still persist all changes.
"""

import json
import uuid

import httpx


def _create_profile(headers, base_url):
    r = httpx.post(
        f"{base_url}/api/v1/profiles",
        headers=headers,
        json={"headline": ""},
        timeout=10,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


class TestProfilePersistence:
    def test_patch_round_trips_location_inside_global_context(self, auth_headers, base_url):
        pid = _create_profile(auth_headers, base_url)
        ctx = {"location": "Dubai", "full_name": "Round-trip User", "skills": ["a", "b"]}
        r = httpx.patch(
            f"{base_url}/api/v1/profiles/{pid}",
            headers=auth_headers,
            json={"headline": "VP Ops", "global_context": json.dumps(ctx)},
            timeout=10,
        )
        assert r.status_code == 200, r.text

        r = httpx.get(f"{base_url}/api/v1/profiles/{pid}", headers=auth_headers, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()

        # K1: top-level `location` field is gone from the response schema.
        assert "location" not in body, "Response must not expose phantom top-level `location`"

        # `global_context` must round-trip exactly.
        round_tripped = json.loads(body["global_context"])
        assert round_tripped["location"] == "Dubai"
        assert round_tripped["full_name"] == "Round-trip User"
        assert round_tripped["skills"] == ["a", "b"]
        assert body["headline"] == "VP Ops"

    def test_apply_import_persists_location_skills_and_experiences(
        self, auth_headers, base_url
    ):
        pid = _create_profile(auth_headers, base_url)
        payload = {
            "imported": {
                "full_name": "Imported User",
                "headline": "Imported Headline",
                "location": "Riyadh",
                "email": "i@example.com",
                "summary": "summary",
                "skills": ["x", "y"],
                "languages": ["en"],
                "education": [
                    {"degree": "MBA", "institution": "INSEAD", "year": "2015"}
                ],
                "experiences": [
                    {
                        "role_title": "COO",
                        "company_name": "Acme",
                        "start_date": "2020",
                        "end_date": "2023",
                    }
                ],
            },
            "overwrite_existing": True,
        }
        r = httpx.post(
            f"{base_url}/api/v1/profiles/{pid}/apply-import",
            headers=auth_headers,
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["experiences_added"] == 1

        # K4: removed the explicit `await db.commit()` — request-scope commit
        # in get_db_session must still persist everything.
        r = httpx.get(f"{base_url}/api/v1/profiles/{pid}", headers=auth_headers, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        ctx = json.loads(body["global_context"] or "{}")

        assert body["headline"] == "Imported Headline"
        assert ctx["location"] == "Riyadh", "K1: location must be stored inside global_context"
        assert ctx["full_name"] == "Imported User"
        assert ctx["skills"] == ["x", "y"]

        # K3: a single, normalized education entry — not the unnormalized form
        # from the (deleted) duplicate `if imp.education:` block.
        assert len(ctx["education"]) == 1
        edu = ctx["education"][0]
        assert isinstance(edu, dict), "education must be a dict, not a Pydantic model dump artifact"
        assert edu["degree"] == "MBA"
        assert edu["institution"] == "INSEAD"

        # Experience persisted via the request-scope commit (K4).
        assert len(body["experiences"]) == 1
        assert body["experiences"][0]["role_title"] == "COO"
        assert body["experiences"][0]["company_name"] == "Acme"

    def test_patch_with_unknown_top_level_location_is_silently_ignored(
        self, auth_headers, base_url
    ):
        """
        Frontend may still send `location` at the PATCH top level (legacy
        client). Backend must accept the request without error and ignore it
        — the field is no longer in CandidateProfileUpdate.
        """
        pid = _create_profile(auth_headers, base_url)
        r = httpx.patch(
            f"{base_url}/api/v1/profiles/{pid}",
            headers=auth_headers,
            json={
                "headline": "H",
                "location": "should-be-ignored",
                "global_context": json.dumps({"location": "Real Location"}),
            },
            timeout=10,
        )
        assert r.status_code == 200, r.text

        r = httpx.get(f"{base_url}/api/v1/profiles/{pid}", headers=auth_headers, timeout=10)
        body = r.json()
        ctx = json.loads(body["global_context"])
        assert ctx["location"] == "Real Location"
        assert "location" not in body
