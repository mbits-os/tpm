# Third Party Modules

[![MIT License](https://img.shields.io/github/license/mbits-os/tpm.svg)](LICENSE)
[![Release](https://img.shields.io/github/release/mbits-os/tpm.svg)](https://github.com/mbits-os/tpm/releases/latest)

The goal of this project is to provide an automated enviroment for building project dependencies. A software project using TPM would require packages in a fashion similar to RPM and if package repo contains needed packages, it would get them and install them in a separated environment.

TPM consists of three components: builder - one for every platform; server - static HTTP server allowing to get the packages; and client - set of scripts downloading and installing required packages.

## Builder

One python script is used to build a package from a recipe on any supported platform.

    python scripts/buildall.py

To force build of a single recipe:

    python scripts/build.py <recipe>

### Artifacts

Products of the builders are either contents of `packages` or only `packages/<platform>` directory.

## Repository server

Once all packages are built and moved to a single location, the repo index must be rebuilt with

    python scripts/buildrepo.py

This command will pick all archives in `packages` directory and re-create the `repo.xml`. Now, contents of `packages` may serve as repo server.

### Artifacts

Products of repo builder is entire `packages` directory.

## Client

_TODO_
