import post_tiktok as pt


class R:
    def __init__(self, code=200, data=None):
        self.status_code, self._d, self.ok, self.text = code, data or {}, code < 400, ""

    def json(self):
        return self._d


def test_github_hosting_creates_release_and_uploads(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.delenv("VIDEO_HOST", raising=False)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    calls = []

    def get(url, **k):
        calls.append(("GET", url))
        return R(404)

    def post(url, **k):
        calls.append(("POST", url))
        if url.endswith("/releases"):
            return R(201, {"upload_url": "https://uploads.github.com/repos/o/r/releases/1/assets{?name,label}", "assets": []})
        return R(201, {"browser_download_url": "https://github.com/o/r/releases/download/video-s/video.mp4"})

    monkeypatch.setattr(pt.requests, "get", get)
    monkeypatch.setattr(pt.requests, "post", post)
    url = pt.host_video(f, "tidalfolio/s")
    assert url.endswith("/video-s/video.mp4")
    assert calls[0][1].endswith("/releases/tags/video-s")
    assert "uploads.github.com" in calls[-1][1]
