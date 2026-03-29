# TLS / Reverse Proxy Configuration

Open Terminal Orchestrator listens on port 8080 (HTTP) by default. In production, place a reverse proxy in front to handle TLS termination. Below are sample configurations for three popular reverse proxies.

## nginx

```nginx
upstream oto {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    server_name oto.example.com;

    ssl_certificate     /etc/letsencrypt/live/oto.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/oto.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Proxy API and admin UI
    location / {
        proxy_pass http://oto;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket upgrade for terminal connections
    location /admin/api/sandboxes/ {
        proxy_pass http://oto;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }
}

server {
    listen 80;
    server_name oto.example.com;
    return 301 https://$host$request_uri;
}
```

### Certificate setup with certbot

```bash
sudo certbot --nginx -d oto.example.com
```

## Caddy

Caddy provides automatic HTTPS via Let's Encrypt with zero configuration:

```Caddyfile
oto.example.com {
    reverse_proxy localhost:8080
}
```

Caddy automatically:
- Obtains and renews TLS certificates
- Handles WebSocket upgrade headers
- Redirects HTTP to HTTPS

## Traefik

For standalone Docker or K3s deployments:

```yaml
# traefik dynamic config (file provider)
http:
  routers:
    oto:
      rule: "Host(`oto.example.com`)"
      entryPoints:
        - websecure
      service: oto
      tls:
        certResolver: letsencrypt

  services:
    oto:
      loadBalancer:
        servers:
          - url: "http://oto:8080"
```

### K3s IngressRoute (Traefik CRD)

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: oto
  namespace: oto
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`oto.example.com`)
      kind: Rule
      services:
        - name: oto
          port: 8080
  tls:
    certResolver: letsencrypt
```

## Verification

After configuring your reverse proxy, verify:

1. **HTTPS works**: `curl -I https://oto.example.com/health`
2. **WebSocket works**: Connect to `wss://oto.example.com/admin/api/sandboxes/{id}/terminal`
3. **Redirect works**: `curl -I http://oto.example.com` should return 301
4. **Headers forwarded**: Check that `X-Forwarded-For` appears in audit logs
