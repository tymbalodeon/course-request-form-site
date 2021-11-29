# Course Request Form

A site for managing the requesting and creating of Canvas sites in Penn's main Canvas instance. Built with [Django](https://www.djangoproject.com/) and [Django Rest Framework](https://www.django-rest-framework.org/).

Production instance: [reqform01.library.upenn.int/](http://reqform01.library.upenn.int/)  
Development instance: [reqform-dev.library.upenn.int/](http://reqform-dev.library.upenn.int/)  
Server configuration: [https://gitlab.library.upenn.edu/course-request/crf2_config](https://gitlab.library.upenn.edu/course-request/crf2_config)

## Makefile

A Makefile is provided with aliases to common commands.

_This README uses these aliases. Actual commands can be seen in the Makefile itself._

- To install "make" on MacOS: `xcode-select --install`

## Local Development

### Access Requirements

- [GlobalProtect VPN](https://www.isc.upenn.edu/how-to/university-vpn-getting-started-guide) (required to connect to the Data Warehouse)

### Installation

1. Install Python 3.6.5 (version management with [pyenv](https://github.com/pyenv/pyenv) recommended: `pyenv install 3.6.5`)
2. Create a [virtual environment](https://docs.python.org/3/tutorial/venv.html) (for example: `pyenv virtualenv 3.6.5 crf2`)
3. Install project dependencies: `make install`
4. Install [Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html) for your platform
5. Create a "tnsnames.ora" file in your Oracle Instant Client's `network/admin` directory, using the appropriate values for Penn's Data Warehouse.
6. Create a config file at `config/config.ini` using `config/config.ini.sample` as a guide and add the appropriate values.

### Commands

- To get started for the first time: `make start` (you will be prompted to create a superuser)
- To populate a local database with real data (must be on GlobalProtect VPN): `make populate` (You may get "locked for overuse"--if so, simply wait and try again later.)
  _For more information, see the files in course/management/commands/_
- To run the application: `make run`
  - To run the application with live reloading (recommended): `make live` in one terminal and `make run` in another
- If you make changes to your models (in `models.py`) file, you will need to run: `make migrations`
- To run a project-aware interactive python shell: `make shell`

To log in as an admin: [http://localhost:8000/admin/](http://localhost:8000/admin/)  
To log in as a non-admin user: [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/)

### Pre-Commit

Tests are included in the pre-commit hooks. Because some of these tests are for the Data Warehouse connection, _you must be on the GlobalProtect VPN to make a commit, but WireGuard to push to GitLab_! (You can also use `git commit --no-verify` to bypass testing for quick fixes)

## Server

### Access Requirements

- WireGuard VPN (must be set up through [Penn IT Help Desk](https://ithelp.library.upenn.edu/support/home))
- SSH access to the production and development domains
- Permissions to "switch user" to user "django" (`sudo su - django`)

### Commands

To login to the production and development instances, make sure you are connected through the WireGuard VPN and run:

1. `ssh reqform01.library.upenn.int` (production) or `ssh reqform-dev.library.upenn.int` (development)
2. `sudo su - django`

- To pull changes from GitLab: `cd /home/django/crf2 && git pull`
- To restart the app (run this after pulling changes): `make restart`
  _This automatically runs `make migrations` and `make static` as well_

Working with the virtual environment:

- Activation: `source /home/dango/crf2/venv/bin/activate`
- Deactivation: `exit`

### Logs

To quickly check the most recent activity:

- `make log` (all levels)
- `make log-info`
- `make log-warning`
- `make log-error`
- `make log-apache`
- `make log-celery`
