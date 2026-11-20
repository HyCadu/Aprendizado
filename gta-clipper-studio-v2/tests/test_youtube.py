"""Testes offline da integração YouTube; todos os clientes remotos são simulados."""
import json
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.integrations.base import PublishRequest
from studio.integrations.models import (DuplicatePublication, IntegrationError, UploadCancelled,
                                        UploadOutcomeUnknown)
from studio.integrations.youtube.auth import SCOPES, YouTubeAuth
from studio.integrations.youtube.client import YouTubeClient
from studio.integrations.youtube.validators import (parse_post_metadata, validate_publish_request,
                                                     probe_video, video_resource)
from studio.services.publication_service import PublicationService, remote_publication_status
from studio.services.publication_storage import PublicationStorage


class MemoryVault:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)

    def get_json(self, key):
        value = self.data.get(key)
        return json.loads(value) if value else None

    def set_json(self, key, value):
        self.data[key] = json.dumps(value)


class OAuthTests(unittest.TestCase):
    def test_import_only_accepts_desktop_oauth_client(self):
        valid = {"installed": {"client_id": "client", "client_secret": "secret",
                                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                "token_uri": "https://oauth2.googleapis.com/token"}}
        self.assertEqual(YouTubeAuth.validate_client_config(valid), valid)
        with self.assertRaises(IntegrationError):
            YouTubeAuth.validate_client_config({"web": valid["installed"]})

    def test_login_uses_pkce_and_rejects_invalid_state(self):
        vault = MemoryVault()
        vault.set_json("oauth_client", {"installed": {"client_id": "client", "client_secret": "secret",
                                                      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                                      "token_uri": "https://oauth2.googleapis.com/token"}})

        class Credentials:
            token = "access-token"

            @staticmethod
            def to_json():
                return json.dumps({"token": "access-token", "refresh_token": "refresh-token", "scopes": SCOPES})

        class Flow:
            instance = None

            @classmethod
            def from_client_config(cls, config, scopes, **kwargs):
                self = cls()
                self.scopes = scopes
                self.pkce_enabled = kwargs.get("autogenerate_code_verifier")
                self.credentials = Credentials()
                cls.instance = self
                return self

            def authorization_url(self, state, **kwargs):
                self.expected_state = state
                self.authorization_options = kwargs
                return f"https://accounts.google.com/o/oauth2/auth?state={state}", state

            def fetch_token(self, code):
                self.received_code = code

        def open_browser(url):
            expected = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["state"][0]
            callback = Flow.instance.redirect_uri

            def send_callbacks():
                for state, code in (("bad-state", "attacker-code"), (expected, "authorized-code")):
                    target = callback + "?" + urllib.parse.urlencode({"state": state, "code": code})
                    try:
                        urllib.request.urlopen(target, timeout=4).read()
                    except Exception:
                        pass

            threading.Thread(target=send_callbacks, daemon=True).start()
            return True

        auth = YouTubeAuth(vault=vault, flow_class=Flow, browser_open=open_browser)
        auth.connect()
        self.assertTrue(Flow.instance.pkce_enabled)
        self.assertEqual(Flow.instance.scopes, SCOPES)
        self.assertIn("127.0.0.1:", Flow.instance.redirect_uri)
        self.assertEqual(Flow.instance.received_code, "authorized-code")
        self.assertEqual(vault.get_json("oauth_token")["refresh_token"], "refresh-token")

    def test_expired_access_token_is_refreshed_and_persisted(self):
        vault = MemoryVault()
        vault.set_json("oauth_token", {"token": "old", "refresh_token": "refresh", "scopes": SCOPES})

        class Credentials:
            @classmethod
            def from_authorized_user_info(cls, data, scopes):
                self = cls()
                self.expired, self.valid, self.refresh_token = True, False, "refresh"
                return self

            def refresh(self, request):
                self.refreshed_with = request
                self.token, self.expired, self.valid = "new-access", False, True

            def to_json(self):
                return json.dumps({"token": self.token, "refresh_token": self.refresh_token, "scopes": SCOPES})

        auth = YouTubeAuth(vault=vault, credentials_class=Credentials, request_factory=lambda: "mock request")
        credentials = auth.credentials()
        self.assertEqual(credentials.token, "new-access")
        self.assertEqual(vault.get_json("oauth_token")["token"], "new-access")

    def test_revoked_refresh_token_is_removed(self):
        vault = MemoryVault()
        vault.set_json("oauth_token", {"token": "old", "refresh_token": "refresh", "scopes": SCOPES})

        class Credentials:
            @classmethod
            def from_authorized_user_info(cls, data, scopes):
                self = cls()
                self.expired, self.valid, self.refresh_token = True, False, "refresh"
                return self

            def refresh(self, request):
                raise ValueError("invalid_grant: Token has been expired or revoked")

        auth = YouTubeAuth(vault=vault, credentials_class=Credentials, request_factory=lambda: object())
        with self.assertRaisesRegex(IntegrationError, "expirou ou foi revogada"):
            auth.credentials()
        self.assertIsNone(vault.get("oauth_token"))

    def test_disconnect_revokes_refresh_token_with_google(self):
        vault = MemoryVault()
        vault.set_json("oauth_token", {"token": "access", "refresh_token": "refresh-token"})
        auth = YouTubeAuth(vault=vault)

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("studio.integrations.youtube.auth.urllib.request.urlopen", return_value=Response()) as opened:
            auth.disconnect()
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://oauth2.googleapis.com/revoke")
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())["token"], ["refresh-token"])
        self.assertIsNone(vault.get("oauth_token"))


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeChannels:
    def list(self, **kwargs):
        self.kwargs = kwargs
        return FakeRequest({"items": [{"id": "channel-real", "snippet": {
            "title": "Canal real", "customUrl": "@canal", "thumbnails": {"high": {"url": "https://img.test/a"}}},
            "statistics": {"subscriberCount": "128", "videoCount": "36", "viewCount": "24800"}}]})


class YouTubeClientTests(unittest.TestCase):
    def test_channels_list_uses_authenticated_channel_and_real_api_fields(self):
        channels = FakeChannels()
        api = SimpleNamespace(channels=lambda: channels)
        auth = SimpleNamespace(credentials=lambda: object())
        client = YouTubeClient(auth=auth, service_builder=lambda *a, **kw: api)
        account = client.get_channel()
        self.assertEqual(channels.kwargs, {"part": "snippet,statistics", "mine": True, "maxResults": 1})
        self.assertEqual(account["id"], "channel-real")
        self.assertEqual(account["subscribers"], "128")
        self.assertEqual(account["videos"], "36")
        self.assertEqual(account["url"], "https://www.youtube.com/channel/channel-real")


class FakeUploadStatus:
    def __init__(self, progress):
        self.resumable_progress = progress


class FakeInsert:
    def __init__(self, api, outcomes):
        self.api = api
        self.outcomes = list(outcomes)
        self.calls = 0

    def next_chunk(self, num_retries=0):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeVideos:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.insert_calls = 0
        self.body = None
        self.part = None

    def insert(self, part, body, media_body):
        self.insert_calls += 1
        self.part, self.body, self.media_body = part, body, media_body
        return FakeInsert(self, self.outcomes)

    def list(self, **kwargs):
        return FakeRequest({"items": [{"id": "video-123", "status": {
            "uploadStatus": "processed", "privacyStatus": self.body["status"]["privacyStatus"],
            "publishAt": self.body["status"].get("publishAt")},
            "processingDetails": {"processingStatus": "succeeded"}}]})


class FakeAPI:
    def __init__(self, outcomes):
        self.video_api = FakeVideos(outcomes)

    def videos(self):
        return self.video_api


class FakeYouTube:
    def __init__(self, api):
        self.api = api

    def service(self):
        return self.api

    def get_channel(self, api=None):
        return {"id": "channel-real", "title": "Canal real"}

    def list_videos(self, ids):
        items = self.api.videos().list(part="status", id=",".join(ids)).execute()["items"]
        return {item["id"]: item for item in items}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "clip.mp4"
        self.video.write_bytes(b"a representative video payload")
        self.db = PublicationStorage(self.root / "publications.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **overrides):
        values = {"clip_path": str(self.video), "platform": "youtube", "title": "Corte do GTA",
                  "description": "Momento incrível", "hashtags": ["#gta", "#shorts"], "tags": ["gta", "gameplay"],
                  "made_for_kids": False, "privacy_status": "private", "rights_confirmed": True,
                  "channel_id": "channel-real", "clip_id": "clip-1"}
        values.update(overrides)
        return PublishRequest(**values)

    def service(self, outcomes, sleeps=None):
        api = FakeAPI(outcomes)
        client = FakeYouTube(api)
        service = PublicationService(client, self.db, media_upload_factory=lambda *a, **kw: object(),
                                     sleep=(sleeps.append if sleeps is not None else lambda _x: None))
        return service, api

    def test_private_resumable_upload_calls_official_videos_insert_and_records_id(self):
        service, api = self.service([(FakeUploadStatus(10), None),
                                     (FakeUploadStatus(30), {"id": "video-123"})])
        progress = []
        record = service.publish(self.request(), progress=lambda *args: progress.append(args))
        self.assertEqual(api.video_api.part, "snippet,status")
        self.assertEqual(api.video_api.body["status"]["privacyStatus"], "private")
        self.assertEqual(api.video_api.body["status"]["selfDeclaredMadeForKids"], False)
        self.assertEqual(api.video_api.body["status"]["containsSyntheticMedia"], False)
        self.assertEqual(record["video_id"], "video-123")
        self.assertEqual(record["url"], "https://www.youtube.com/watch?v=video-123")
        self.assertEqual(record["status"], "private")
        self.assertEqual(progress[-1][0], self.video.stat().st_size)

    def test_schedule_uses_private_and_converts_local_offset_to_utc(self):
        req = self.request(scheduled_for="2030-01-02T10:00:00-03:00", privacy_status="public")
        _, scheduled = validate_publish_request(req, now=datetime(2029, 1, 1, tzinfo=timezone.utc))
        resource = video_resource(req, scheduled)
        self.assertEqual(resource["status"]["privacyStatus"], "private")
        self.assertEqual(resource["status"]["publishAt"], "2030-01-02T13:00:00Z")

    def test_user_must_choose_audience_and_confirm_rights(self):
        with self.assertRaisesRegex(IntegrationError, "Escolha se"):
            validate_publish_request(self.request(made_for_kids=None))
        with self.assertRaisesRegex(IntegrationError, "autorização"):
            validate_publish_request(self.request(rights_confirmed=False))

    def test_title_and_description_limits_are_validated(self):
        with self.assertRaisesRegex(IntegrationError, "100 caracteres"):
            validate_publish_request(self.request(title="x" * 101))
        with self.assertRaisesRegex(IntegrationError, "5.000"):
            validate_publish_request(self.request(description="x" * 5001))

    def test_automatic_retries_use_exponential_backoff_for_transient_http_errors(self):
        failure = Exception("transient server response")
        failure.resp = SimpleNamespace(status=503)
        sleeps = []
        service, _ = self.service([failure, (FakeUploadStatus(30), {"id": "video-123"})], sleeps)
        record = service.publish(self.request())
        self.assertEqual(record["video_id"], "video-123")
        self.assertEqual(sleeps, [0.1] * 10)  # primeiro intervalo exponencial: 1s

    def test_unknown_upload_result_is_not_retried_as_a_duplicate(self):
        service, api = self.service([OSError("connection lost after request")])
        with self.assertRaises(UploadOutcomeUnknown):
            service.publish(self.request())
        self.assertEqual(self.db.list_recent()[0]["status"], "unknown")
        with self.assertRaises(DuplicatePublication):
            service.publish(self.request())
        self.assertEqual(api.video_api.insert_calls, 1)

    def test_cancel_stops_between_resumable_chunks_and_records_cancelled_status(self):
        service, api = self.service([(FakeUploadStatus(10), None),
                                     (FakeUploadStatus(30), {"id": "video-123"})])
        cancelled = {"value": False}

        def progress(sent, total, stage):
            if stage == "Enviando vídeo":
                cancelled["value"] = True

        with self.assertRaises(UploadCancelled):
            service.publish(self.request(), progress=progress, cancelled=lambda: cancelled["value"])
        self.assertEqual(self.db.list_recent()[0]["status"], "cancelled")
        self.assertEqual(api.video_api.insert_calls, 1)

    def test_reconcile_maps_remote_statuses(self):
        self.assertEqual(remote_publication_status({"status": {"publishAt": "2030-01-01T00:00:00Z"}}), "scheduled")
        self.assertEqual(remote_publication_status({"status": {"uploadStatus": "processed", "privacyStatus": "unlisted"},
                                                    "processingDetails": {"processingStatus": "succeeded"}}), "unlisted")
        self.assertEqual(remote_publication_status({"status": {"uploadStatus": "failed"}}), "failed")

    def test_post_md_values_are_read_as_defaults_without_modifying_file(self):
        post = self.root / "post.md"
        post.write_text("## YouTube\nTítulo: Voo no GTA\nDescrição: Olha esse corte\n#shorts #gta\n", encoding="utf-8")
        before = post.read_bytes()
        result = parse_post_metadata(post, {"title": "fallback", "description": "desc", "hashtags": []})
        self.assertEqual(result["title"], "Voo no GTA")
        self.assertIn("Olha esse corte", result["description"])
        self.assertEqual(result["hashtags"], ["#shorts", "#gta"])
        self.assertEqual(post.read_bytes(), before)

    def test_missing_ffprobe_metadata_does_not_block_review(self):
        result = probe_video(self.root / "not-created.mp4")
        self.assertEqual(result["short"], "unknown")


if __name__ == "__main__":
    unittest.main()
