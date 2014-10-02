On a Debian(-based) system, install `cython3 python3-dev python3-flask python3-requests python3-sqlalchemy python3-postgresql python3-greenlet postgresql`

In `pg_hba.conf` (usually at `/etc/postgresql/9.4/main/`), set local access to `trust` (as opposed to the default `peer`)

```bash
git submodule init && git submodule update

sudo psql
> create user outlauth;
> create database outlauth;
> grant all privileges on database outlauth to outlauth;
sudo invoke-rc.d postgresql restart # for pg_hba.conf change
cp config.py.example config.py

python3 db.py init
./outlauth.py
```

Visit http://localhost:8894/

Install `python3-zeroc-ice ice35-slice mumble-server`
