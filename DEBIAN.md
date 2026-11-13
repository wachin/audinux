# Getting Audinux into Debian

This directory of work follows **Debian Policy 4.7.4.1** (the current version,
released 2026-03-31) and the current `debhelper`/`pybuild`/`autopkgtest` tooling.
Everything below was built and checked on Debian 13 (trixie).

## What is already in place

| Requirement | Where |
| --- | --- |
| Source format `3.0 (quilt)` | `debian/source/format` |
| `Standards-Version: 4.7.4.1` | `debian/control` |
| No `Priority` field (Policy 4.7.3: omit when it is the default) | `debian/control` |
| Build with `dh` + `pybuild`/pyproject | `debian/rules` |
| `Rules-Requires-Root: no` | `debian/control` |
| Machine-readable copyright, GPL-3.0-only | `debian/copyright` |
| Manual page (Policy 12.1) | `debian/audinux.1` + `debian/manpages` |
| Desktop entry, validated with `desktop-file-validate` | `packaging/audinux.desktop` |
| Icons: 16, 22, 24, 32, 48, 64, 128, 256, 512 px + scalable SVG | `packaging/icons/hicolor/`, `packaging/audinux.svg` |
| Upstream `debian/watch` (uscan format 4) | `debian/watch` |
| `debian/upstream/metadata` | `debian/upstream/metadata` |
| Autopkgtest smoke test | `debian/tests/` |

The icons, the desktop entry and the `data-files` entries in `pyproject.toml`
are upstream files, so `dh_auto_install` (pybuild) installs them into
`/usr/share/icons/hicolor/...` and `/usr/share/applications/`. There is no
`debian/install` file because nothing needs to be moved by hand.

`debian/rules` disables `dh_auto_test` on purpose: upstream has no test suite,
so the package is exercised by the autopkgtest instead.

## 1. Cut an upstream release first

`debian/watch` and `dpkg-source` expect `audinux_<version>.orig.tar.gz` to be the
real upstream release. Upstream `0.6.2` is tagged as `v0.6.2` and
`debian/changelog` is at `0.6.2-1`; for later releases, tag the new version,
push the tag and add a changelog entry, then let `uscan` fetch the tarball:

```bash
git tag -a v0.6.3 -m "audinux 0.6.3"
git push origin v0.6.3
dch -v 0.6.3-1 "New upstream release."
uscan --download-current-version     # writes ../audinux_0.6.3.orig.tar.gz
```

`debian/watch` matches the `vX.Y.Z` tags of
<https://github.com/wachin/audinux/tags>.

The watch file uses `version=4`, the format supported by every `devscripts`
release (the newer rfc822-style `Version: 5` format of `debian-watch(5)` only
arrived in devscripts 2.26, which trixie does not have yet).

## 2. Build and check

```bash
sudo apt install devscripts debhelper dh-python pybuild-plugin-pyproject lintian
sudo apt build-dep .
dpkg-buildpackage -b -uc -us          # binary package, unsigned
lintian --tag-display-limit 0 ../audinux_0.6.2-1_amd64.changes
```

Both builds were verified here:

- `dpkg-buildpackage -b -uc -us` → `audinux_0.6.2-1_all.deb`
- `dpkg-buildpackage -S -uc -us` → source package (`.dsc`, `.debian.tar.xz`)

Optional extra QA, all of which is expected to pass:

```bash
sudo apt install piuparts reprotest
piuparts ../audinux_0.6.2-1_all.deb
reprotest 'dpkg-buildpackage -b -uc -us' ../audinux_0.6.2-1_all.deb
```

The smoke test can be run directly from the source tree:

```bash
./debian/tests/smoke
```

## 3. File the ITP bug

Every new package needs an "Intent To Package" bug. Check the WNPP list first
(<https://www.debian.org/devel/wnpp/> or `querybts wnpp`) and that the name is
free (`apt-cache search audinux`), then:

```bash
reportbug wnpp
# choose: ITP — Intent to package
# subject: ITP: audinux -- long-audio player with multi-line waveform and markers
```

Use the description from `debian/control` and the homepage in the body, and
mention the license (GPL-3.0-only). Then record the bug number:

```bash
dch --close 1234567 "Initial Debian release (Closes: #1234567)."
dpkg-buildpackage -b -uc -us
lintian --tag-display-limit 0 ../audinux_0.6.2-1_amd64.changes
```

Until that bug number exists, lintian reports one warning,
`initial-upload-closes-no-bugs`. It disappears once `Closes: #NNNNNN` is in the
changelog — it is the only finding left on this package.

## 4. Publish the packaging and upload to mentors

```bash
# A Salsa repository is expected (personal or a team such as Debian Multimedia)
git remote add salsa git@salsa.debian.org:wachin/audinux.git
git push salsa main --tags
```

Build a signed upload — the first upload must include the orig tarball:

```bash
dpkg-buildpackage -sa -k"$YOUR_GPG_KEYID"
dput mentors ../audinux_0.6.2-1_amd64.changes
```

`mentors.debian.net` needs a GPG key in the Debian keyring and a
`~/.dput.cf` entry:

```ini
[mentors]
fqdn = mentors.debian.net
incoming = /upload
method = https
allow_unsigned_uploads = 0
```

## 5. Ask for a sponsor

```bash
reportbug sponsorship-requests
```

The RFS (Request For Sponsorship) template requires: package name, version,
the mentors.debian.net URL, a short description, the license, and why the
package is useful. Mention the ITP number and that lintian is clean.

## 6. What happens next

1. The sponsor reviews and uploads to `unstable`; the package waits in the NEW
   queue for ftp-master review.
2. Answer any REJECT/QUESTIONS mail on the ITP bug (do not open new bugs).
3. After acceptance it appears on <https://tracker.debian.org/pkg/audinux> and,
   once built for each architecture, on <https://packages.debian.org/audinux>.
   Migration to `testing` takes the usual 2–10 days.
4. Keep the ITP bug subscribed; `uscan` cron sends new upstream releases.

Do not upload to `stable`, and do not ask for a freeze exception: a new package
always enters through `unstable`.

## Notes on the two lintian warnings you may still see locally

With the `lintian 2.122.0` that ships in trixie (policy data from early 2025)
the source package also shows:

- `newer-standards-version 4.7.4.1 (current is 4.7.2)` — trixie's lintian does
  not know 4.7.3/4.7.4.1 yet; 4.7.4.1 is the current Policy version, and
  unstable's lintian accepts it.
- `recommended-field Priority` — Policy 4.7.3 stopped recommending `Priority`
  in source packages; older lintian data still asks for it. The field is
  deliberately omitted.

Neither will be reported by the lintian in unstable.
