# Course Request Form

A site for managing the requesting and creating of Canvas sites in Penn's main Canvas instance. Built with [Django](https://www.djangoproject.com/) and [Django Rest Framework](https://www.django-rest-framework.org/).

Production instance: [reqform01.library.upenn.int/](http://reqform01.library.upenn.int/)  
Development instance: [reqform-dev.library.upenn.int/](http://reqform-dev.library.upenn.int/)  
Server configuration: [https://gitlab.library.upenn.edu/course-request/crf2_config](https://gitlab.library.upenn.edu/course-request/crf2_config)

## Makefile

A Makefile is provided with aliases to common commands. (To install "make" on MacOS, run: `xcode-select --install`)  
_To see the actual commands, inspect the Makefile_

## Local Development

### Access Requirements

- [GlobalProtect VPN](https://www.isc.upenn.edu/how-to/university-vpn-getting-started-guide) (required to connect to the Data Warehouse)

### Installation

1. Install Python 3.6.5 (recommend version management with [pyenv](https://github.com/pyenv/pyenv))
2. Create a [virtual environment](https://docs.python.org/3/tutorial/venv.html) via your preferred method
3. Install project dependencies: `make install`
4. Install [Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html) for your platform
5. Create a "tnsnames.ora" file in your Oracle Instant Client's "network/admin" directory, using the following values:

```
WHSE.UPENN.EDU=
  (DESCRIPTION=
    (ADDRESS=
      (COMMUNITY=isc.penn)
      (PROTOCOL=TCP)
      (HOST=warehouse.isc.upenn.edu)
      (PORT=1521)
    )
    (CONNECT_DATA=
      (GLOBAL_NAME=whse)
      (SID=whse)
    )
  )
```

6. Create a config file at "config/config.ini" (you will need to create the "config" directory) and add the appropriate values. Here is a sample config file:

```ini
[django]
password = password
username = username
secret_key = secret-key
debug = True # for local development and False on the server

[email]
password = password
emailhost = smtp.office365.com
emailhostuser = librarycanvas@pobox.upenn.edu
defaultfromemail = librarycrf@pobox.upenn.edu

[canvas]
prod_env = https://canvas.upenn.edu
prod_key = secret-key
test_env = https://upenn.test.instructure.com
test_key = secret-key

[opendata]
id = opendata-id
key = secret-key
domain = https://esb.isc-seo.upenn.edu/8091/open_data/
id_directory = opendata-id-directory
key_directory = secret-key

[users]
username = password

[datawarehouse]
user = LIBCANVAS
password = password
service = whse.upenn.edu
```

### Commands

- To create a development admin user: `make superuser`
- To populate a local database with real data: `make populate`
  _For more information, see the files in course/management/commands/_
- To run the application: `make run`
- If you make changes to your "models.py" file, you will need to run: `make migrations` (Note the plural!)
  _This is run automatically by `make run`_
- To add CSS or other static file changes to the build, run: `make static`
- To run python interactively using your virtual environment's shell: `make shell`
- To interactively query the sqlite3 database, run `make db`
  - To view tables: `.tables`
  - To inspect tables:
    1. `.headers on` (only required once per session)
    2. `.mode column`(only required once per session)
    3. `pragma table_info(<table_name>)`

To log in as an admin: [http://localhost:8000/admin/](http://localhost:8000/admin/)  
To log in as a user: [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/)

### Data Warehouse

To query the Data Warehouse directly, make sure you are connected through the GlobalProtect VPN and run:

`sqlplus '<username>/<password>@(DESCRIPTION=(ADDRESS=(COMMUNITY=isc.penn)(PROTOCOL=TCP)(HOST=warehouse.isc.upenn.edu)(PORT=1521))(CONNECT_DATA=(GLOBAL_NAME=whse)(SID=whse)))'` (recommend storing this as a [shell alias](https://shapeshed.com/unix-alias/))

Reference: [sqlplus Documentation](https://docs.oracle.com/cd/B19306_01/server.102/b14357/toc.htm)

## Server

### Access Requirements

- WireGuard VPN (must be set up through [Penn IT Help Desk](https://ithelp.library.upenn.edu/support/home))
- SSH access to the production and development domains
- Permissions to "switch user" to user "django" (`sudo su - django`)

### Commands

To login to the production and development instances, make sure you are connected through the WireGuard VPN and run:

1. `make prod` (production) or `make dev` (development)
2. `sudo su - django`

- To pull changes from GitLab: `make pull`
- To restart the app (run this after pulling changes): `make restart`

Working with the virtual environment:

- Activation: `make activate`
- Deactivation: `exit`

### Logs

Log paths:

- /var/log/crf2/crf2_access.log
- /var/log/crf2/crf2_error.log
- /home/django/crf2/logs/ (`pull_instructors`)
- /var/log/celery/ (`pull_courses`)

To quickly check the most recent activity in the "crf2_error.log": `make log`

## Workflow

1. Create a new [issue](https://gitlab.library.upenn.edu/course-request/CRF2/-/issues) explaining the bug or enhancement (use the templates and appropriate tags when possible).
2. Create a branch for the issue.
3. Commit code changes to the issue branch.
4. Push changes from the issue branch to the "develop" branch.
5. Pull the "develop" branch into the CRF development instance and test changes (remember you may need to make manual temporary changes to certain processes to interface with the test instance of Canvas when appropriate).
6. When satisfied with the results when using "develop," merge develop to "master" and close the issue.
7. Pull the "master" branch into the CRF production instance and restart the app (see above).
