On a Debian(-based) system, install `cython3 python3-dev python3-flask python3-zeroc-ice ice35-slice mumble-server`

```bash
git submodule init && git submodule update
cd gevent.git && CYTHON=cython3 python3 ./setup.py build
# make sure the gevent symlink points to something valid.
./outlauth.py
```

Visit http://localhost:8894/
