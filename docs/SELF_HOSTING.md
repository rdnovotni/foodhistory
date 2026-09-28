# Private-first self-hosting runbook

This runbook deploys the catalogue on a dedicated Ubuntu or Debian computer using Docker Compose and PostgreSQL 16. The initial deployment is private: PostgreSQL exists only on an internal container network and the web application binds only to `127.0.0.1` on the host. Tailscale can provide authenticated private HTTPS access without router port forwarding.

The same computer and database can later serve the public website. A disabled Compose profile includes Caddy as the public HTTPS reverse proxy, but it must not be enabled until the public domain, security review, restore drill, and publication policy are ready.

## Before installation

Prepare:

- a dedicated computer connected by Ethernet, preferably protected by a UPS;
- a non-root administrative account and SSH key access;
- a static LAN address for the computer;
- an external disk or remote destination for a second copy of every backup;
- a Tailscale account for private access from approved devices.

Do not configure router port forwarding for the private phase. Do not expose PostgreSQL under any circumstance.

## Host preparation

1. Install a supported Ubuntu Server LTS or Debian release and all security updates.
2. Install Docker Engine and the Compose plugin from Docker's official repository.
3. Install Tailscale from its official repository and enroll the host in the private tailnet.
4. Create a `foodhistory` service account, clone this repository to `/opt/foodhistory`, and give that account ownership.
5. Enable automatic security updates. Configure the host firewall to permit SSH only from the trusted administration network or Tailscale.
6. Configure the firmware to start automatically after power is restored.

Docker publishes container ports through its own firewall rules. The production web binding explicitly uses host loopback, and the database has no published port.

## Configure secrets

Copy the example environment file and lock its permissions:

```console
cd /opt/foodhistory
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate two different URL-safe database passwords with `openssl rand -hex 32`. Use one for `POSTGRES_PASSWORD` and the other for `PUBLIC_DATABASE_PASSWORD`. Leave `SITE_BASE_URL=http://127.0.0.1:8000` for the first local verification. The passwords are interpolated into PostgreSQL URLs, so keep them hexadecimal as generated. Never commit `.env.production`; Git ignores it.

## First private deployment

Validate and start the default private stack:

```console
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml up -d --build
docker compose --env-file .env.production -f compose.production.yaml ps
ops/healthcheck.sh http://127.0.0.1:8000
```

The one-shot `setup` container applies only unapplied migrations and loads the canonical taxonomy. Production never sets `LOAD_EXAMPLES`. The catalogue is not reachable from the LAN or internet because port 8000 is bound only to host loopback.

Create the first private wiki owner after the stack is healthy:

```console
docker compose --env-file .env.production -f compose.production.yaml exec web \
  python tools/create_editor.py owner --display-name "Your Name" --role owner
```

The password prompt requires at least 12 characters and does not expose the password in shell history. See `WIKI.md` for roles and review workflow.

## Private HTTPS through Tailscale

On the host, publish the loopback service only to authenticated tailnet devices:

```console
sudo tailscale serve --bg http://127.0.0.1:8000
tailscale serve status
```

Tailscale reports the private `https://...ts.net` address. Put that exact address in `SITE_BASE_URL` and recreate the web service:

```console
docker compose --env-file .env.production -f compose.production.yaml up -d web
```

Test from another approved Tailscale device. Tailnet access policy remains the authorization boundary; do not use Tailscale Funnel, which would make the service public.

## Automatic boot, backups, and health checks

Review the paths and service account in `ops/systemd/*.service`, then install the units:

```console
sudo cp ops/systemd/food-history* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now food-history.service
sudo systemctl enable --now food-history-backup.timer
sudo systemctl enable --now food-history-health.timer
```

Backups are PostgreSQL custom-format archives under `backups/`, retained locally for 14 days by default. Override `BACKUP_DIR` to write directly to a mounted backup disk. A local backup is not sufficient: copy it to encrypted storage outside the computer after each run.

Run and inspect a backup:

```console
ops/backup.sh
systemctl list-timers 'food-history-*'
journalctl -u food-history-backup.service
```

Test restoration before importing irreplaceable records. Restoration first creates a safety backup, stops the web container, replaces database objects from the selected archive, and restarts the web container:

```console
CONFIRM_RESTORE=RESTORE_FOOD_HISTORY ops/restore.sh backups/food_history_TIMESTAMP.dump
```

## Updates and recovery

`ops/update.sh` refuses to run with uncommitted changes, creates a database backup, fast-forwards the checkout, rebuilds images, and recreates the private services. Run the health check afterward. Do not configure unattended application upgrades; review and deploy each release deliberately.

Useful checks:

```console
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs --since 30m web
systemctl status food-history.service
tailscale serve status
df -h
```

For recovery on replacement hardware, install Docker and Tailscale, clone the same application revision, restore `.env.production`, start the stack, copy in the most recent off-machine archive, run the restore command, and complete the private smoke test.

## Private acceptance gate

- The catalogue is reachable through Tailscale from approved devices.
- It is not reachable from an unapproved LAN or internet device.
- PostgreSQL port 5432 and application port 8000 are closed externally.
- `/health`, the homepage, and `/api/docs` work through the private HTTPS address.
- A backup has been copied off the host and restored successfully.
- Reboot and power-loss recovery have been tested.
- No synthetic fixtures or restricted records with incorrect access status are present.
- The Render preview remains available until the private server passes every check.

## Later public website activation

The public path is intentionally dormant. Before launch:

1. Complete the public website, accessibility review, rights review, privacy policy, analytics decision, incident ownership, and content acceptance tests.
2. Obtain the final domain, point its DNS records to the public connection, and confirm whether the ISP permits inbound hosting. Use an outbound tunnel if carrier-grade NAT prevents direct hosting.
3. Replace `PUBLIC_HOST`, `ACME_EMAIL`, and `SITE_BASE_URL` in `.env.production` with the final public values.
4. Forward only TCP 80/443 and UDP 443 to the host. Keep ports 5432 and 8000 closed.
5. Validate the dormant edge before activation:

   ```console
   docker compose --env-file .env.production -f compose.production.yaml --profile public config --quiet
   ```

6. Start the public profile and run the external smoke test:

   ```console
   docker compose --env-file .env.production -f compose.production.yaml --profile public up -d
   python tools/smoke_test.py --base-url https://history.example.com
   ```

Caddy then becomes the only internet-facing container, obtains and renews the HTTPS certificate, and proxies to `public_web`. That process runs with `APP_MODE=public`, so the `/editor/*` routes do not exist; the loopback-bound `web` process remains the private editor. Both use the self-hosted PostgreSQL database, but `public_web` authenticates with the automatically provisioned SELECT-only role. Keep Tailscale for administration and recovery; never expose the database directly.
