# ServerDash — Nginx Reverse Proxy

Using Nginx in front of ServerDash provides:
- Public HTTPS on port 443 with proper certificates (Let's Encrypt, etc.)
- HTTP → HTTPS redirect
- WebSocket support for real-time script output streaming

## Prerequisites

- Nginx installed (`sudo apt install nginx`)
- ServerDash running via systemd on port 8443 (see `systemd/README.md`)

## Installation

**1. Copy the config**

```bash
sudo cp serverdash.conf /etc/nginx/sites-available/serverdash
sudo ln -s /etc/nginx/sites-available/serverdash /etc/nginx/sites-enabled/serverdash
```

**2. Edit the config**

- Replace `server_name _;` with your actual domain.
- Update `ssl_certificate` / `ssl_certificate_key` paths for production certs.

**3. (Recommended) Use Let's Encrypt**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d serverdash.example.com
```

Certbot will automatically update the Nginx config with valid certificates and set up auto-renewal.

**4. Test and reload Nginx**

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Notes

- `proxy_read_timeout 600s` is set to allow long-running scripts to stream output without the connection being dropped.
- WebSocket upgrade headers are set globally so the real-time script terminal works correctly.
- Nginx proxies to `https://127.0.0.1:8443` (TLS between Nginx and gunicorn). If you prefer plain HTTP internally, change the backend bind and `proxy_pass` to `http://`.
