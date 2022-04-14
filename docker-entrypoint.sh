#!/bin/bash
set -e

# if we are running gunicorn or celery then make sure we are running as the application user (app)
if [ "$1" = "gunicorn" ] || [ "$1" = "celery" ]; then
    # if APP_UID and APP_GID exist then assume we are running in dev mode and update
    # the UID/GID for the node user inside the container
    if [ ! -z "${APP_UID}" ] && [ ! -z "${APP_GID}" ]; then
        usermod -u $APP_UID app
        groupmod -g $APP_GID app
    fi

    # give the app user ownership of the application files
    chown -R app:app .

    if [ "$1" = "gunicorn" ]; then
        while !</dev/tcp/postgres/${POSTGRES_PORT}; do
            echo "sleeping until database is ready..."
            sleep 1
        done

        make migrations

    elif [ "$1" = "celery" ]; then
        while !</dev/tcp/redis/${REDIS_PORT}; do
            echo "sleeping until redis is ready..."
            sleep 1
        done
    fi

    # run the application as the app user
    exec gosu app "$@"
fi

# run any other command
exec "$@"
