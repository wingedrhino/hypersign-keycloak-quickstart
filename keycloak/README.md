# Hypersign Installer for Keycloak

## Pre-requisites

### Keycloak

You should have Keycloak v9.0 or newer.

### Local Install

Local install refers to when you'd like to deploy the Hypersign Keycloak plugin
on an instance of Keycloak that's installed locally on your machine, obtained
from the [official downloads page](https://www.keycloak.org/downloads.html).

This needs Python >= 3.6 to be installed on your system.

My assumption is that you are either on Linux with system Python or on any
other platform with Anaconda Python. If it's `System Python`, I assume you are
on RHEL 8, CentOS 8, Ubuntu 18.04 or Debian 10 if it's a server deployment; all
of these support Python 3.6. Newer Linux distros should have Python 3.7 or
3.8. Anaconda Python is currently at 3.7 and it is available on Linux,
Windows 10 and macOS 10.15.

I'm uninterested in supporting any other platform!

### Docker Install

I will assume you are using a "current" version of Docker (stable or edge) while
running the dockerized version of this script. Please make sure you have
[docker-compose](https://docs.docker.com/compose/install/) installed for a less
painful install experience!

Our `Dockerfile` derives from the official `jboss/keycloak` image on Docker
Hub. Click [here](https://hub.docker.com/r/jboss/keycloak/dockerfile) to see
the image's Dockerfile.

## Execution (local install)

After cloning this repository to your machine, edit the `defaults.env` file
where you will make changes per your own requirements (the file is nicely
commented) and then run `entrypoint.py`.

## Development

For developing this script locally, you need a recent Python (>= 3.6) and then
install `mypy` for performing type checks.

### IDE: PyCharm Community

[PyCharm Community Edition](https://www.jetbrains.com/pycharm/download) is the
IDE I recommend to develop on this project. If you're on Linux, you might want
to [install it via Snapcraft](https://snapcraft.io/pycharm-community.

Install the Markdown, Docker, and mypy plugins there.

### Python: Anaconda

I recommend downloading Anaconda for a hassle-free experience with Python,
since some of you would be on Windows and OSX instead of Linux. While these
platforms are nowhere close to Linux, you'll atleast get a semblance of a
generally familiar environment!

After you install Anaconda, run `conda install mypy`.

If you are on Linux, you can instead do `pip3 install mypy` from your system
Python, which is hopefully v3.6 or newer!

### Windows 10: Local Install

Windows is a little _too_ different from Linux for it to be developer friendly.

But you can use this installer for a "local" install of Keycloak. Keycloak,
IntelliJ PyCharm Community, and the Anaconda Python Distribution are all
available on Windows.

Our Dockerized installer might work if you use Windows 10 Professional. Docker
does not support Windows 10 Home because it doesn't ship with Hyper-V, on which
Docker depends.
