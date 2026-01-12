from urllib.parse import urlparse

def canonicalize_repo_url(raw: str) -> str:
    """
    Canonical GitHub repo URL:
    - forces https
    - strips trailing '/'
    - strips '.git'
    - keeps only github.com/<owner>/<repo>
    """
    s = raw.strip()

    # If user passes without scheme, assume https
    if "://" not in s:
        s = "https://" + s

    u = urlparse(s)
    host = (u.netloc or "").lower()
    path = (u.path or "").strip()

    # normalize path: remove trailing / and .git
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]

    # keep only first two segments: /owner/repo
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        path = "/" + parts[0] + "/" + parts[1]
    else:
        path = "/" + "/".join(parts)

    return f"https://{host}{path}"