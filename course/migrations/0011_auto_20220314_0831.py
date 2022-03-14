# Generated by Django 2.1.2 on 2022-03-14 12:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course", "0010_auto_20220207_0947"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="course_term",
            field=models.CharField(
                choices=[
                    ("10", "Spring"),
                    ("20", "Summer"),
                    ("30", "Fall"),
                    ("A", "Old Spring"),
                    ("B", "Old Summer"),
                    ("C", "Old Fall"),
                ],
                max_length=2,
            ),
        ),
    ]