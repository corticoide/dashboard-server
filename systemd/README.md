# ServerDash — systemd Installation

## Prerequisites

- Python 3.11+
- ServerDash deployed to `/opt/serverdash`
- TLS certificate at `/opt/serverdash/certs/cert.pem` (run `deploy-prod.sh` first)

## Steps

**1. Create a dedicated system user (optional but recommended)**

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin serverdash
sudo chown -R serverdash:serverdash /opt/serverdash
```

**2. Edit the unit file**

Replace `<USER>` with the system user:

```bash
sed -i 's/<USER>/serverdash/' serverdash.service
```

**3. Install the unit**

```bash
sudo cp serverdash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable serverdash
sudo systemctl start serverdash
```

**4. Check status**

```bash
sudo systemctl status serverdash
sudo journalctl -u serverdash -f
```

## Updating

```bash
cd /opt/serverdash
git pull
.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && npm install --silent && npm run build && cd ..
sudo systemctl restart serverdash
```
