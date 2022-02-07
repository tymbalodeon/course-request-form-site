# Generated by Django 2.1.2 on 2022-02-07 14:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course", "0009_auto_20211028_2106"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="course_term",
            field=models.CharField(
                choices=[
                    ("A", "Spring"),
                    ("B", "Summer"),
                    ("C", "Fall"),
                    ("A", "Old Spring"),
                    ("B", "Old Summer"),
                    ("C", "Old Fall"),
                ],
                max_length=2,
            ),
        ),
    ]
