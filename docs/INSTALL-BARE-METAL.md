# Install without Docker

The one-command install runs Unpress in containers, which is the right default:
it pins the versions, and there is exactly one thing to remove when you are
done. This page is for the other case — your own server, your own packages,
your own supervision.

> Run on a clean Ubuntu 24.04 and 26.04 VM (1 vCPU, 2 GB, 20 GB) before being
> written down. Everything below is what actually happened, including the four
> places where the obvious command is the wrong one.

**In a hurry?** [`install-bare-metal.sh`](../install-bare-metal.sh) runs
everything below and checks your prerequisites first:

```bash
curl -fsSL https://raw.githubusercontent.com/neoserviceai/unpress/main/install-bare-metal.sh | bash
```

The rest of this page is the same thing step by step, for when you want to see
or change what it does.

Unpress is a Frappe bench with four apps on it. If you have run a Frappe app
before, nothing below will surprise you.

---

## What it needs

| | Version | Why |
|---|---|---|
| Python | **3.14 exactly** | frappe declares `requires-python = ">=3.14,<3.15"`. 26.04 ships it; 24.04 does not |
| Node | **24+** | `frappe-framework` declares `"node": ">=24"` and yarn enforces it |
| Yarn | **1.22** | the editor's lockfile is v1 |
| MariaDB | 10.6+ | Frappe does not support MySQL 8 defaults |
| Redis | 6+ | cache and queue |
| wkhtmltopdf | 0.12.6 **with patched qt** | PDF output. The plain build lays PDFs out wrong |
| uv | any | `bench init` builds the virtualenv with it |
| git, a C toolchain | — | building python wheels |

```bash
sudo apt install -y git curl build-essential pkg-config \
  python3-dev python3-venv python3-pip pipx \
  redis-server mariadb-server libmariadb-dev \
  nodejs npm xvfb libfontconfig
```

### Four places where the obvious command is wrong

**`pip install frappe-bench` is refused.** The system python is externally
managed (PEP 668) on both releases: *"error: externally-managed-environment"*.
Use `pipx install frappe-bench`.

**`bench init` needs `uv`, and nothing says so.** With bench 5.31 it clones
frappe, then dies on `FileNotFoundError: [Errno 2] No such file or directory:
'uv'` and offers to roll back. `curl -LsSf https://astral.sh/uv/install.sh | sh`.

**`apt install wkhtmltopdf` installs nothing.** It is in the archives of
neither release — `apt-cache policy` answers `Candidate: (none)`. Take the
patched-qt package from
[wkhtmltopdf/packaging](https://github.com/wkhtmltopdf/packaging/releases);
there is no build past *jammy*, and the jammy one runs on both:

```bash
curl -fsSLO https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb
sudo apt install -y ./wkhtmltox_0.12.6.1-3.jammy_amd64.deb
```

**`yarn` is not yarn.** Ubuntu packages yarn **4** under the name `yarnpkg`,
and the editor's lockfile is yarn 1 — it resolves differently. Take yarn 1
from npm and leave the distribution's alone:
`sudo npm install -g yarn@1.22.22`.

**24.04's python is too old, and no PPA is needed.** frappe 16.31 wants python
3.14 and noble has 3.12.3, so `uv pip install -e apps/frappe` refuses outright:
*"the current Python version (3.12.3) does not satisfy Python>=3.14,<3.15"*.
`uv` — already required for `bench init` — fetches a standalone one, and the
machine's own python is left alone:

```bash
uv python install 3.14
bench init --frappe-branch version-16 --python "$(uv python find 3.14)" unpress-bench
```

26.04 ships 3.14 and needs none of this.

**No Ubuntu ships a node new enough.** 24.04 has 18, 26.04 has 22, and frappe
wants 24 — `bench init` clones frappe and then stops on *"The engine node is
incompatible with this module. Expected version >=24. Got 22.22.1"*. NodeSource
is not an optimisation here, it is the only way through:

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs     # not `nodejs npm` — NodeSource brings its own
```

> `lsb_release` is not a reliable way to tell which release you are on. The
> Infomaniak 26.04 image answers `Ubuntu 24.04.4 LTS` to `lsb_release -ds`
> while `/etc/os-release` correctly says `VERSION_ID="26.04"`. Read the file.

MariaDB needs Frappe's collation, or site creation fails on the first
non-ASCII character:

```ini
# /etc/mysql/mariadb.conf.d/50-server.cnf
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

A fresh MariaDB authenticates root through the unix socket, which bench cannot
use — give root a password:

```bash
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('<choose one>'); FLUSH PRIVILEGES;"
```

## Build the bench

```bash
pipx install frappe-bench
bench init --frappe-branch version-16 unpress-bench
cd unpress-bench
```

## Add the apps

Two are ordinary repositories:

```bash
bench get-app https://github.com/neoserviceai/builder --branch unpress
bench get-app https://github.com/neoserviceai/blog --branch version-16
```

The other two live inside this repository rather than each having their own, so
clone it once and point bench at the directories — `bench get-app` takes a path
as readily as a URL:

```bash
git clone https://github.com/neoserviceai/unpress
bench get-app ./unpress/apps/unpress_core
bench get-app ./unpress/apps/wp_migrator
```

The editor's front end is not committed, so build it once:

```bash
cd apps/builder/frontend && yarn install && yarn build && cd -
```

## Create the site

```bash
bench new-site your.site --admin-password '<choose one>'
bench --site your.site install-app builder
bench --site your.site install-app wp_migrator
bench --site your.site install-app unpress_core
bench --site your.site install-app blog
bench use your.site
```

`blog` is a plugin: installed so it exists, on or off from **Réglages →
Extensions**. See [PLUGINS.md](PLUGINS.md) for why "off" is a switch and never
an uninstall.

## Tell the site where it is published

This is the step people skip, and it is the one that costs the most.

Frappe builds every absolute URL — canonical tags, the sitemap, `og:url`, links
inside mail — from the request it happens to see. Behind a reverse proxy that
request is plain HTTP on an internal port, so without this your sitemap
advertises `http://your.site:8000/contact`: wrong scheme, and a port that
answers to nobody on the internet.

```bash
bench --site your.site execute unpress_core.site_url.apply_public_url \
  --kwargs "{'public_url': 'https://your.site'}"
```

Run it again whenever the public address changes. It is idempotent, and it also
writes a `robots.txt` naming your sitemap — but only if you have not written
one yourself.

## Serve it

For a real deployment, let bench write the nginx and supervisor configuration:

```bash
sudo bench setup production $USER
bench setup nginx
sudo service nginx reload
```

TLS with certbot:

```bash
sudo bench setup lets-encrypt your.site
```

Point **both** `your.site` and `www.your.site` at the machine. If you terminate
TLS somewhere else — Caddy, Traefik, a load balancer — the only thing Unpress
needs from you is the `apply_public_url` call above and a proxy that preserves
the `Host` header.

## How small a machine

Tested on 1 vCPU / 2 GB / 20 GB, the size of a cheap VPS, on Ubuntu 24.04 and
26.04.

> **Give it swap.** The image is built with 2 GB of RAM and no swap by default
> on most providers, and the install has two peaks that do not fit: `bench init`
> resolving python wheels, and the editor's `yarn build`. Four gigabytes of swap
> costs nothing on a 20 GB disk:
>
> ```bash
> sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
> sudo mkswap /swapfile && sudo swapon /swapfile
> echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
> ```
>
> Swap alone is not enough for the editor's build: node sizes its heap from the
> memory it *sees*, caps itself near 1 GB on a 2 GB machine, and aborts with
> `Ineffective mark-compacts near heap limit` without ever spilling. Raise the
> cap so it can:
>
> ```bash
> NODE_OPTIONS=--max-old-space-size=4096 yarn build
> ```

Two things that will look like your mistake and are not:

**apt is busy for the first minutes of a machine's life.** Cloud images run
`unattended-upgrades` at boot, and `apt-get` does not queue — it exits 100 with
*"Unable to acquire the dpkg frontend lock"*. The installer waits; if you run
the steps by hand, wait too.

**The install is slow on one core, and that is all it is.** Cloning frappe,
compiling wheels and building the editor are minutes each. Watch
`tail -f install.log` rather than assuming it has hung.

## Keeping it current

```bash
cd unpress-bench
bench update --reset                       # frappe + builder + blog
git -C ../unpress pull                     # this repository
bench --site your.site migrate
bench restart
```

The image does the equivalent on every boot. Doing it by hand is the price of
choosing your own packages.
