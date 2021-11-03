import cx_Oracle
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from config.config import (
    DATA_WAREHOUSE_PASSWORD,
    DATA_WAREHOUSE_SERVICE,
    DATA_WAREHOUSE_USERNAME,
    PASSWORD,
    USERNAME,
)
from course.models import Profile


class Command(BaseCommand):
    help = "Create dummy users."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--total",
            type=int,
            help="Indicates the number of users to be created.",
        )
        parser.add_argument(
            "-p", "--prefix", type=str, help="Define a username prefix."
        )
        parser.add_argument(
            "-a", "--admin", action="store_true", help="Create an admin account."
        )
        parser.add_argument(
            "-c",
            "--courseware",
            action="store_true",
            help="Add Courseware Support team as admins.",
        )
        parser.add_argument(
            "-d",
            "--department",
            type=int,
            help="Add all employees with a certian PRIMARY_DEPT_ORG code.",
        )

    def handle(self, **kwargs):
        total = kwargs["total"]
        prefix = kwargs["prefix"]
        admin = kwargs["admin"]
        courseware = kwargs["courseware"]
        department = kwargs["department"]

        if total:
            for user in range(total):
                try:
                    username = (
                        f"{prefix}_{get_random_string()}"
                        if prefix
                        else get_random_string()
                    )

                    user_object = (
                        User.objects.create_superuser(
                            username=username, email="", password="123"
                        )
                        if admin
                        else User.objects.create_user(
                            username=username, email="", password="123"
                        )
                    )
                    print(f"- ADDED user: {user_object}")
                except Exception:
                    print(f"- FAILED to add user: {username}")

        if courseware:

            try:
                user = User.objects.create_superuser(
                    username=USERNAME, email="", password=PASSWORD
                )
                print(f"- ADDED user: {user}")
            except Exception:
                print(f"- FAILED to add user: {username}")

        if department:
            connection = cx_Oracle.connect(
                DATA_WAREHOUSE_USERNAME, DATA_WAREHOUSE_PASSWORD, DATA_WAREHOUSE_SERVICE
            )
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT first_name, last_name, email_address, penn_id, pennkey
                FROM employee_general
                WHERE primary_dept_org = :department
                """,
                department=department,
            )

            for first_name, last_name, email, penn_id, pennkey in cursor:
                try:
                    user = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "penn_id": penn_id,
                    }
                    first_name = user["first_name"].title()
                    last_name = user["last_name"].title()
                    Profile.objects.create(
                        user=User.objects.create_user(
                            username=pennkey,
                            first_name=first_name,
                            last_name=last_name,
                            email=user["email"],
                        ),
                        penn_id=user["penn_id"],
                    )
                    print(
                        f"- ADDED: {first_name}, {last_name}, {email}, {penn_id},"
                        f" {pennkey}"
                    )
                except Exception:
                    print(f"- FAILED to add user: {pennkey}.")
