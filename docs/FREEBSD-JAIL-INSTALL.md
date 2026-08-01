# FreeBSD Jail Installation

## Summary

This runbook installs Safebox Acorn as an independent Python component inside
a FreeBSD jail. It covers a fresh host, jail creation, native build
dependencies, installation from GitHub or a local checkout, wallet
initialization, smoke tests, optional post-quantum support, upgrades, and
troubleshooting.

The initial validated target is:

- FreeBSD `15.1-RELEASE-p1`;
- `arm64`;
- Python `3.11`;
- a ZFS-root host;
- a classic jail using `ip4 = inherit`.

The ordinary Acorn installation does **not** require Open Quantum Safe or
`liboqs`. Install the core component first. Add the `post-quantum` extra only
after the ordinary wallet, record, relay, mint, and ecash paths work.

This guide uses `acorn` as the jail name, service account, and installation
directory. Substitute other names consistently if required.

## Command context

Commands are labelled by execution context:

- **host** — run as `root` on the FreeBSD host;
- **jail-root** — run as `root` inside the jail;
- **acorn** — run as the unprivileged `acorn` user inside the jail.

Jail lifecycle commands such as `service jail start acorn`, `jls`, and
`jexec` are host commands. Package installation and Python setup are performed
inside the jail.

## 1. Validate and protect the host

Run on the **host**:

```sh
freebsd-version
uname -m
zpool list
zpool status
zfs list
ping -c 3 pkg.freebsd.org
```

Confirm that:

- the ZFS pool is `ONLINE`;
- DNS and outbound package access work;
- the architecture and release are the ones expected;
- sufficient disk space is available.

Bootstrap and update the host package catalogue:

```sh
pkg bootstrap -f
pkg update
pkg upgrade
```

Enable jail management:

```sh
sysrc jail_enable=YES
sysrc jail_parallel_start=YES
```

Create a boot-environment rollback point:

```sh
bectl list
bectl create before-acorn-jail
bectl list
```

## 2. Create the jail

These commands assume the host ZFS pool is `zroot`.

Run on the **host**:

```sh
zfs create -p zroot/jails/acorn
bsdinstall jail /zroot/jails/acorn
mkdir -p /etc/jail.conf.d
```

Make `/etc/jail.conf` contain this include directive:

```text
.include "/etc/jail.conf.d/*.conf";
```

The include belongs in `/etc/jail.conf`. It does not belong inside an
`acorn { ... }` block.

Create `/etc/jail.conf.d/acorn.conf`:

```text
exec.clean;
mount.devfs;
allow.raw_sockets = 0;

exec.start = "/bin/sh /etc/rc";
exec.stop = "/bin/sh /etc/rc.shutdown";

acorn {
    host.hostname = "acorn";
    path = "/zroot/jails/acorn";
    ip4 = inherit;
    persist;
}
```

Validate, start, and inspect the jail:

```sh
service jail config acorn
service jail start acorn
jls
jexec acorn freebsd-version
```

Enter the jail:

```sh
jexec acorn /bin/sh
```

With `allow.raw_sockets = 0`, `ping` from inside the jail can fail with
`Operation not permitted`. This does not prove that ordinary TCP, HTTPS, DNS,
or WebSocket access is broken.

## 3. Bootstrap the jail

Run as **jail-root**:

```sh
env ASSUME_ALWAYS_YES=yes pkg bootstrap -f
pkg update
pkg upgrade
```

Verify HTTPS access:

```sh
fetch -qo /dev/null https://pkg.freebsd.org/
```

If DNS fails, exit to the host and copy its resolver configuration into the
jail:

```sh
cp /etc/resolv.conf /zroot/jails/acorn/etc/resolv.conf
```

Then re-enter the jail and retry `pkg update`.

## 4. Install Python and native build dependencies

Run as **jail-root**:

```sh
pkg install -y \
  ca_root_nss git curl bash sudo \
  python311 py311-pip py311-setuptools py311-wheel py311-virtualenv \
  py311-sqlite3 py311-cffi py311-coincurve \
  cmake ninja gmake pkgconf rust llvm \
  autoconf automake libtool openssl sqlite3
```

FreeBSD may not have binary Python wheels for every Acorn dependency on
`arm64`. The compiler, CMake, Ninja, and Rust packages allow packages such as
`cryptography` and `pydantic-core` to build when necessary. The packaged
`py311-coincurve` avoids a particularly fragile source build.

Verify the toolchain:

```sh
python3.11 --version
clang --version
cmake --version
ninja --version
rustc --version
python3.11 -c 'import sqlite3; print(sqlite3.sqlite_version)'
python3.11 -c 'import coincurve; print(coincurve.__version__)'
```

On a small ARM host, also check swap from the **host**:

```sh
swapinfo -h
```

A compiler process that disappears without a useful diagnostic is often a
memory-pressure problem. Add swap or reduce build parallelism before assuming
the source package is broken.

## 5. Create the Acorn account and virtual environment

Run as **jail-root**:

```sh
pw groupadd acorn
pw useradd acorn -g acorn -d /home/acorn -m -s /bin/sh
install -d -o acorn -g acorn /usr/local/acorn
install -d -o acorn -g acorn /usr/local/src/safebox-acorn
```

If the group or user already exists, do not recreate it. Confirm ownership:

```sh
id acorn
ls -ld /home/acorn /usr/local/acorn /usr/local/src/safebox-acorn
```

Open a shell as the **acorn** user from the host:

```sh
jexec -U acorn acorn /bin/sh
```

Create a virtual environment that can see compatible native modules installed
by FreeBSD packages:

```sh
python3.11 -m venv --system-site-packages /usr/local/acorn/.venv
/usr/local/acorn/.venv/bin/python -m pip install --upgrade pip setuptools wheel
```

The `--system-site-packages` option is intentional. Without it, `pip` may
ignore `py311-coincurve` and attempt to compile another version from source.

## 6. Install Acorn

Choose one installation path.

### Path A: Install directly from GitHub

Run as **acorn**:

```sh
/usr/local/acorn/.venv/bin/pip install \
  "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git"
```

For a release candidate, pin a tag or commit instead of installing a moving
default branch:

```sh
/usr/local/acorn/.venv/bin/pip install \
  "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git@<tag-or-commit>"
```

### Path B: Editable checkout for development

The destination directory created earlier must be empty. Run as **acorn**:

```sh
git clone https://github.com/trbouma/safebox-acorn.git \
  /usr/local/src/safebox-acorn

/usr/local/acorn/.venv/bin/pip install --editable \
  /usr/local/src/safebox-acorn
```

An editable installation immediately reflects Python source changes in the
checkout. Dependency or packaging changes still require another `pip install
--editable` invocation.

Add the virtual environment to the interactive path:

```sh
echo 'PATH=/usr/local/acorn/.venv/bin:$PATH; export PATH' >> /home/acorn/.profile
. /home/acorn/.profile
```

Verify the installation:

```sh
python -c 'from acorn import Acorn; print(Acorn)'
acorn --help
acorn info
python -m pip check
```

An ordinary installation should not require or import `oqs`.

## 7. Initialize a wallet

Remain logged in as **acorn**. Protect files created during initialization:

```sh
umask 077
acorn init
```

The command:

- warns before disconnecting an existing wallet;
- offers to display existing recovery material;
- prompts for an `nsec`, home relay, and home mint;
- generates a new key when the `nsec` is left blank;
- optionally accepts externally generated 256-bit entropy through a hidden
  prompt and creates a recoverable 24-word BIP39 phrase;
- normalizes a relay without a scheme to `wss://`;
- normalizes a mint without a scheme to `https://`.

For an explicit new configuration:

```sh
acorn init \
  --homerelay wss://relay.example.com \
  --mint https://mint.example.com
```

Do not put a real `nsec` directly in shell history. Enter it at the prompt or
use a root-readable provisioning mechanism appropriate to the deployment.

To initialize from entropy produced by an external CSPRNG or hardware device:

```sh
acorn init --entropy \
  --homerelay wss://relay.example.com \
  --mint https://mint.example.com
```

Enter the 64-character hexadecimal value twice at the hidden prompt. Do not put
it directly in a shell command, environment variable, jail configuration, or
image-building log. Acorn converts it into a recoverable 24-word BIP39 phrase;
back up that phrase and the home relay before funding the wallet. See
[External Entropy Initialization](EXTERNAL-ENTROPY-INITIALIZATION.md) for the
complete derivation and security contract.

The default configuration is:

```text
/home/acorn/.acorn/config.yml
```

Confirm its permissions:

```sh
chmod 700 /home/acorn/.acorn
chmod 600 /home/acorn/.acorn/config.yml
ls -ld /home/acorn/.acorn
ls -l /home/acorn/.acorn/config.yml
```

Back up the recovery material securely:

```sh
acorn set --show-recovery
```

This command displays sensitive material and asks for confirmation.

## 8. Core smoke test

First confirm wallet and infrastructure information:

```sh
acorn info
acorn set --show-mint
acorn balance
acorn check-proofs
```

Use a disposable label to exercise encrypted relay-backed records:

```sh
acorn put "FreeBSD smoke test" "Acorn record write succeeded"
acorn get "FreeBSD smoke test"
acorn get_user_records --labels
acorn delete "FreeBSD smoke test"
```

The `put` and `delete` operations ask for confirmation. A successful write
reports the event ID and relay readback. Deletion is a signed Nostr deletion
request and remains advisory; a relay is not guaranteed to erase stored data.

At this point, the core Acorn component is installed. Do not fund the wallet
until the recovery material has been backed up and the intended relay and mint
have been verified.

## 9. Run pytest from a development checkout

The runtime package does not need to include the test suite. To test inside the
jail, use the editable checkout from Path B and install the development test
dependencies:

```sh
cd /usr/local/src/safebox-acorn
python -m pip install pytest pytest-asyncio python-dotenv
pytest -m "not live" -v
```

The non-live suite does not require funded wallets or live infrastructure.

Live tests write relay events and may move sats. Configure them only after the
non-live suite succeeds:

```sh
cp .env.example .env
chmod 600 .env
```

Edit `.env` without placing private keys in shell history. To test only a
third-party relay:

```dotenv
ACORN_SOURCE_CONFIG=/home/acorn/.acorn/config.yml
ACORN_THIRD_PARTY_RELAY=wss://relay.example.com
ACORN_RELAY_SCENARIO=third-party
ACORN_TEST_AMOUNT=1
ACORN_TEST_TIMEOUT=60
```

Leave `ACORN_TEST_TRANSFER_RELAY` unset so the third-party scenario uses
`ACORN_THIRD_PARTY_RELAY` for transfer events.

Run:

```sh
pytest -m live -v -s -rs
```

The source wallet provides test funding; disposable wallets perform most test
operations. Begin with a small balance and `ACORN_TEST_AMOUNT=1`.

## 10. Optional post-quantum support

Post-quantum support is experimental and is not used by ordinary Acorn wallet,
record, relay, mint, or ecash operations.

First, as **jail-root**, inspect the FreeBSD repository:

```sh
pkg search -x 'liboqs|py311-liboqs-python'
```

When available, install the native shared library:

```sh
pkg install -y liboqs
ldconfig -r | grep liboqs
ls -l /usr/local/lib/liboqs.so*
```

Then reinstall Acorn with the extra as the **acorn** user.

For GitHub:

```sh
/usr/local/acorn/.venv/bin/pip install --upgrade \
  "safebox-acorn[post-quantum] @ git+https://github.com/trbouma/safebox-acorn.git"
```

For an editable checkout:

```sh
/usr/local/acorn/.venv/bin/pip install --editable \
  '/usr/local/src/safebox-acorn[post-quantum]'
```

Verify both layers with the exact virtual-environment interpreter:

```sh
python -c 'import oqs; print("liboqs", oqs.oqs_version())'
python -c 'from acorn.post_quantum import PQEvent; print(PQEvent)'
```

For a development checkout:

```sh
pytest tests/unit/test_optional_post_quantum.py -v
```

The native `liboqs` library and `liboqs-python` wrapper are separate versioned
components. Record both versions when diagnosing a mismatch:

```sh
python -c \
  'import importlib.metadata, oqs; print("wrapper", importlib.metadata.version("liboqs-python")); print("native", oqs.oqs_version())'
```

A version warning should not be hidden. Confirm that the required algorithms
and Acorn tests work, or install a compatible pair before treating the
post-quantum extra as operational.

## 11. Create a successful-install snapshot

After the core smoke test succeeds, exit to the **host**:

```sh
exit
service jail stop acorn
zfs snapshot zroot/jails/acorn@acorn-core-installed
service jail start acorn
zfs list -t snapshot | grep acorn
```

If post-quantum support is installed and verified, create a separate snapshot:

```sh
service jail stop acorn
zfs snapshot zroot/jails/acorn@acorn-with-post-quantum
service jail start acorn
```

Snapshots make local rollback convenient but are not off-host backups. Protect
the wallet recovery material separately.

## 12. Upgrade and rollback

Before upgrading, run on the **host**:

```sh
service jail stop acorn
zfs snapshot zroot/jails/acorn@before-acorn-upgrade
service jail start acorn
```

For a GitHub installation, run as **acorn** inside the jail:

```sh
pip install --upgrade \
  "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git@<tag-or-commit>"
python -m pip check
acorn --help
acorn info
```

For an editable checkout:

```sh
cd /usr/local/src/safebox-acorn
git pull --ff-only
pip install --editable .
pytest -m "not live" -v
```

If an upgrade corrupts the jail, stop it before ZFS rollback:

```sh
service jail stop acorn
zfs rollback zroot/jails/acorn@before-acorn-upgrade
service jail start acorn
```

## Troubleshooting

### `pkg` exists but is only the bootstrap stub

Run as **jail-root**:

```sh
env ASSUME_ALWAYS_YES=yes pkg bootstrap -f
pkg update
```

### `ping: ssend socket: Operation not permitted`

This is expected when the jail has `allow.raw_sockets = 0`. Test DNS and HTTPS
with `pkg update` or `fetch` instead.

### Poetry or pip tries to downgrade `coincurve`

Acorn permits `coincurve >=20,<22`, and FreeBSD 15 arm64 has been exercised
with the packaged 21.x module. Confirm:

```sh
pkg info py311-coincurve
python3.11 -c 'import coincurve; print(coincurve.__version__)'
/usr/local/acorn/.venv/bin/python -c \
  'import coincurve; print(coincurve.__version__)'
```

If the virtual environment cannot see the packaged module, recreate it with
`--system-site-packages` and reinstall Acorn. Do not reintroduce an exact
20.0.0 pin merely to satisfy an old lock file.

### `Use build.verbose instead of cmake.verbose`

This error has occurred while building an older `coincurve` through
`scikit-build-core`. Prefer `py311-coincurve`, keep Acorn's `>=20,<22`
constraint, recreate the virtual environment with system site packages, and
retry.

### A wheel build takes a long time

On FreeBSD arm64, a wheel may be compiled locally because PyPI has no matching
binary wheel. Processes such as `rustc`, `cargo`, `clang`, `cc`, `c++`,
`cmake`, and `ninja` consuming CPU indicate progress.

Inspect from the **host**:

```sh
jexec acorn top -aSH
swapinfo -h
dmesg | tail -50
```

Do not repeatedly restart a healthy native build.

### `No module named '_sqlite3'`

```sh
pkg install -y py311-sqlite3
```

Recreate the virtual environment if it was created before the package was
installed and does not use system site packages.

### `liboqs.so` cannot be opened

Only relevant to the optional `post-quantum` extra:

```sh
pkg info liboqs
ls -l /usr/local/lib/liboqs.so*
ldconfig -r | grep liboqs
ldconfig -m /usr/local/lib
/usr/local/acorn/.venv/bin/python -c 'import oqs; print(oqs.oqs_version())'
```

### Illegal instruction while loading `liboqs` on ARM

Do not copy an optimized library from another ARM machine. Install the FreeBSD
package for the jail architecture or rebuild `liboqs` with a distribution-safe
configuration such as `-DOQS_DIST_BUILD=ON`.

### Jail stop reports an invalid configuration

Run these commands on the **host**, not inside the jail:

```sh
hostname
jls
cat /etc/jail.conf
cat /etc/jail.conf.d/acorn.conf
service jail config acorn
```

The most common cause is a missing include in `/etc/jail.conf`:

```text
.include "/etc/jail.conf.d/*.conf";
```

### The wallet cannot read its bootstrap data

Confirm that:

- the configured relay URL is correct;
- a missing relay scheme normalized to `wss://`;
- the relay accepts and returns Acorn's addressable encrypted events;
- outbound WebSocket connections are allowed;
- the same `nsec` and home relay are in `/home/acorn/.acorn/config.yml`.

Use a relay already shown as suitable in
[Relay Suitability Ledger](./RELAY-SUITABILITY-LEDGER.md), or run the
third-party relay test before trusting a new relay with meaningful funds.

## Installation acceptance checklist

- [ ] Host release, architecture, ZFS health, and rollback point recorded.
- [ ] `service jail config acorn` succeeds.
- [ ] Jail starts and appears in `jls`.
- [ ] DNS, HTTPS, and package installation work inside the jail.
- [ ] Python 3.11, Clang, Rust, CMake, and Ninja are available.
- [ ] The virtual environment uses the intended interpreter.
- [ ] `python -m pip check` succeeds.
- [ ] `from acorn import Acorn` succeeds.
- [ ] `acorn --help` and `acorn info` succeed.
- [ ] Recovery material is backed up outside the jail.
- [ ] `acorn balance` and `acorn check-proofs` succeed.
- [ ] Private record put, get, list, and delete succeed.
- [ ] The non-live pytest suite passes for a development checkout.
- [ ] Live testing uses only a small test balance.
- [ ] Optional post-quantum support is tested separately, if installed.
- [ ] A successful-install ZFS snapshot exists.

## References

- [FreeBSD Handbook: Jails and Containers](https://docs.freebsd.org/en/books/handbook/jails/)
- [Open Quantum Safe: liboqs](https://github.com/open-quantum-safe/liboqs)
- [Roadmap to Releasability](./ROADMAP-TO-RELEASABILITY.md)
- [Recovery Specification](./RECOVERY-SPEC.md)
- [Relay Suitability Ledger](./RELAY-SUITABILITY-LEDGER.md)
