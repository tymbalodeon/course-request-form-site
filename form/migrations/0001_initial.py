# Generated by Django 4.0.4 on 2022-05-13 01:16

from django.conf import settings
import django.contrib.auth.models
import django.contrib.auth.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('penn_id', models.IntegerField(null=True, unique=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('TaEnrollment', 'Ta'), ('TeacherEnrollment', 'Instructor'), ('DesignerEnrollment', 'Designer'), ('Librarian', 'Librarian'), ('Observer', 'Observer')], default='TaEnrollment', max_length=18)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleType',
            fields=[
                ('sched_type_code', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('sched_type_desc', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='School',
            fields=[
                ('school_code', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('school_desc_long', models.CharField(max_length=50, unique=True)),
                ('visible', models.BooleanField(default=True)),
                ('canvas_sub_account_id', models.IntegerField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('subject_code', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('subject_desc_long', models.CharField(max_length=255, null=True)),
                ('visible', models.BooleanField(default=True)),
                ('school', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subjects', to='form.school')),
            ],
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('section_code', models.CharField(editable=False, max_length=150, primary_key=True, serialize=False)),
                ('section_id', models.CharField(editable=False, max_length=150)),
                ('course_num', models.CharField(max_length=4)),
                ('section_num', models.CharField(max_length=4)),
                ('term', models.IntegerField()),
                ('title', models.CharField(max_length=250)),
                ('primary_course_id', models.CharField(max_length=150)),
                ('xlist_family', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('also_offered_as', models.ManyToManyField(blank=True, to='form.section')),
                ('course_sections', models.ManyToManyField(blank=True, to='form.section')),
                ('instructors', models.ManyToManyField(blank=True, related_name='sections', to=settings.AUTH_USER_MODEL)),
                ('primary_section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='form.section')),
                ('primary_subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='form.subject')),
                ('schedule_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='form.scheduletype')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='form.school')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='form.subject')),
            ],
        ),
        migrations.CreateModel(
            name='Request',
            fields=[
                ('section', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='form.section')),
                ('title_override', models.CharField(blank=True, default=None, max_length=255, null=True)),
                ('copy_from_course', models.IntegerField(blank=True, default=None, null=True)),
                ('reserves', models.BooleanField(default=False)),
                ('lps_online', models.BooleanField(default=False)),
                ('exclude_announcements', models.BooleanField(default=False)),
                ('additional_instructions', models.TextField(blank=True, default=None, null=True)),
                ('admin_additional_instructions', models.TextField(blank=True, default=None, null=True)),
                ('process_notes', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('Submitted', 'Submitted'), ('Approved', 'Approved'), ('Locked', 'Locked'), ('Canceled', 'Canceled'), ('In Process', 'In Process'), ('Error', 'Error'), ('Completed', 'Completed')], default='Submitted', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('additional_enrollments', models.ManyToManyField(blank=True, to='form.enrollment')),
                ('included_sections', models.ManyToManyField(blank=True, related_name='requests', to='form.section')),
                ('proxy_requester', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='proxy_requests', to=settings.AUTH_USER_MODEL)),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AutoAdd',
            fields=[
                ('enrollment_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='form.enrollment')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='form.school')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='form.subject')),
            ],
            bases=('form.enrollment',),
        ),
    ]
