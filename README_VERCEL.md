# Hyper A D2C Meta Ads Audit Engine — Vercel Deployment Guide

This is the cloud-hosted, Postgres-backed version of the Audit Engine. It's
built for [Vercel](https://vercel.com) and stores its data in a real
Postgres database (via Vercel's built-in Storage integration) instead of a
local SQLite file, so your team can share one live link.

No coding experience required — just follow the steps in order.

## 1. Create a free Vercel account

Go to https://vercel.com/signup and sign up (GitHub, GitLab, or email all
work fine).

## 2. Install the Vercel CLI and deploy

You'll need Node.js installed on your computer (https://nodejs.org — the
"LTS" version). Then, open a terminal, navigate into this folder
(`d2c-audit-engine-vercel/`), and run:

```
npx vercel --prod
```

The first time you run this it will:
- Ask you to log in (opens a browser window)
- Ask "Set up and deploy?" → yes
- Ask which scope/team → pick your account
- Ask to link to an existing project → no (create a new one)
- Ask for a project name → accept the default or type your own, e.g. `d2c-audit-engine`
- Ask about build settings → accept the defaults (it will pick up `vercel.json` automatically)

When it finishes, it prints a live URL like:
`https://d2c-audit-engine.vercel.app`

At this point the site is deployed, but it has no database connected yet —
visiting it will show an error. That's expected; the next step fixes it.

## 3. Add a Postgres database

1. Go to https://vercel.com/dashboard and open your new project.
2. Click the **Storage** tab.
3. Click **Create Database** → choose **Postgres** (Neon or Vercel Postgres,
   whichever is offered — both work identically here).
4. Give it a name (e.g. `d2c-audit-db`) and create it.
5. On the database's page, click **Connect** (or "Connect Project") and
   select the `d2c-audit-engine` project you just deployed. This
   automatically adds the right environment variables
   (`DATABASE_URL` / `POSTGRES_URL` / `POSTGRES_URL_NON_POOLING` /
   `POSTGRES_PRISMA_URL` — the app checks all of these, in that order) to
   your project.

## 4. Redeploy so the new environment variables take effect

Environment variables only apply to new deployments. Redeploy with:

```
npx vercel --prod
```

(Or, in the Vercel dashboard: Deployments tab → "..." menu on the latest
deployment → Redeploy.)

## 5. Verify it worked

Visit `https://<your-project>.vercel.app/api/health` in your browser. You
should see something like:

```
{"status":"ok","companies":200,"database_url_set":true}
```

`"companies":200` means the app connected to Postgres, created its schema,
and auto-seeded all 200 companies from `api/prospect_source.json` on that
first request. If you see `"status":"error"`, the error message will name
the problem — almost always it means the database wasn't connected to the
project yet (repeat step 3) or the redeploy in step 4 hasn't happened.

## 6. Use the app

Visit `https://<your-project>.vercel.app/` — you'll see the same Table /
Pipeline / Segmentation / Scoring / Workflow tabs as the local version, now
backed by a shared Postgres database that every teammate who has the link
can read and edit.

## Notes

- This is a **separate deployment and a separate hosting link** from the
  local (SQLite) version of this app — they do not share data.
- The data in `api/prospect_source.json` is loaded once, the first time the
  `companies` table is empty. If you ever want to reset to the original 200
  companies, delete all rows from the `companies` table in the Vercel
  Storage dashboard's query console (`DELETE FROM companies;`) — the app
  will reseed automatically on the next request.
- No contact detail is ever fabricated: `business_email` and
  `business_phone` are stored and shown exactly as `"Unavailable"` for
  every company where the underlying audit didn't find one.
