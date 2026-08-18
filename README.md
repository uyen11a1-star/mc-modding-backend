# Minecraft Modding Community — Backend

FastAPI backend with email/password login and Google + GitHub OAuth.

## 1. Run it in Termux (for testing)

```bash
pkg install python -y
cd mc-modding-backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env
```

Edit `.env` and fill in `SECRET_KEY` (generate one with the command in the
file's comment). Leave the Google/GitHub keys empty for now if you just
want to test email/password signup first.

Start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000` in a browser on the same device — you should
see `{"status":"ok",...}`. Interactive API docs are at `/docs`.

> Note: this is fine for local testing, but Termux should not be your
> production server (network drops, phone sleep, changing IP). Deploy to
> Railway or Render for a real public API — see step 4.

## 2. Get Google OAuth credentials

1. Go to <https://console.cloud.google.com/apis/credentials>.
2. Create a project (or pick an existing one).
3. Click **Create Credentials → OAuth client ID**.
4. Application type: **Web application**.
5. Under **Authorized redirect URIs**, add:
   `https://YOUR-BACKEND-URL/auth/google/callback`
   (use `http://localhost:8000/auth/google/callback` while testing locally)
6. Copy the **Client ID** and **Client Secret** into `.env` as
   `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

## 3. Get GitHub OAuth credentials

1. Go to <https://github.com/settings/developers> → **New OAuth App**.
2. Homepage URL: your frontend URL (e.g. your GitHub Pages link).
3. Authorization callback URL:
   `https://YOUR-BACKEND-URL/auth/github/callback`
   (use `http://localhost:8000/auth/github/callback` while testing locally)
4. After creating, copy the **Client ID**, then generate a **Client secret**.
5. Put both into `.env` as `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

## 4. Deploy so it has a real public URL

Termux can't stay online as a public server, so deploy to a free host:

**Railway** (recommended, simplest):
1. Push this folder to a GitHub repo.
2. Go to <https://railway.app>, "New Project" → "Deploy from GitHub repo".
3. Select the repo. Railway auto-detects Python and installs
   `requirements.txt`.
4. In the project's **Variables** tab, add every value from your `.env`
   file (SECRET_KEY, GOOGLE_CLIENT_ID, etc.) plus `FRONTEND_URL` set to
   your GitHub Pages link.
5. Set the **Start command** to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Railway gives you a public URL like `https://your-app.up.railway.app`.
   Use that as `YOUR-BACKEND-URL` in the Google/GitHub redirect URIs above
   (you'll need to update those once you know the real URL).

**Render** works the same way — "New Web Service" → connect the repo →
same start command → add the same environment variables.

## 5. Connect the frontend (index.html)

In your `index.html`, point the OAuth buttons and the email/password form
at your deployed backend, e.g.:

```html
<a href="https://your-app.up.railway.app/auth/google/login">Continue with Google</a>
<a href="https://your-app.up.railway.app/auth/github/login">Continue with GitHub</a>
```

For email/password, the frontend needs a small `fetch()` call to
`POST /auth/signup` or `POST /auth/login` with `{ "email": ..., "password": ... }`
— ask for this next if you want it wired in.

After a successful login, the backend redirects back to `FRONTEND_URL`
with `?token=...` in the URL — the frontend should read that token from
the URL and store it (e.g. in memory / a cookie) to know the user is
logged in.

## Project structure

```
mc-modding-backend/
├── app/
│   ├── main.py          FastAPI app, CORS, session middleware
│   ├── database.py      SQLAlchemy engine/session
│   ├── models.py        User table
│   ├── schemas.py       Request/response shapes
│   ├── auth.py          Password hashing, JWT creation/verification
│   ├── oauth.py         Google + GitHub client registration
│   └── routers/
│       └── auth.py      /auth/signup, /auth/login, OAuth routes
├── requirements.txt
├── .env.example
└── README.md
```
