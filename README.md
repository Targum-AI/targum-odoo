# Targum Odoo App

This repo contains 2 things:

- A local odoo instance (/odoo)
- The Targum Odoo app (/odoo_app)

## Setting up a local odoo instance

### 1. Start docker

```bash
cd odoo
docker compose up
```

### 2. Open http://localhost:8069 and do the setup:

```bash
Master Password: secret
Database Name: targum_odoo
Email: admin
Password: admin
Check "Demo Data"
```

### 3. Activate the ecommerce & targum modules

- Open Menu => Apps
- Install "Ecommerce" & "Targum AI"

### 4. Settings

- Click top left menu icon => Settings
- Scroll to the bottom and click "Activate the developer mode"
- Set `Targum Instance URL` to `http://localhost:8000` (or whatever your targum url is)
- Copy the generated `API key`
- Go to Targum Nova, create an `Integration`, paste the `API key` into `Merchant secret`.
- Set `Webhook URL` to `TODO` and save.
- Open the created `Integration`, click the `options` icon and `Generate API token`. Copy that to Odoo settings under `Integration Secret` & save.

### 5. Creating a new product

- Click top left menu icon => Website
- Go to Ecommerce => Products
- Click "New"
- Name it & click "Save manually" icon at the top
