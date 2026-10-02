import uuid

from django.db import migrations, models

SYSTEM_ID = uuid.UUID(int=1)


def create_system_user(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    # "!" marks the password unusable; .invalid is a reserved domain, so no
    # Google account can ever claim this address.
    User.objects.create(id=SYSTEM_ID, email="system@invalid", password="!", is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # Sign-in moved to Google only. The password accounts made before that
        # go, along with everything that hangs off them (profiles, uploads,
        # tokens); purge_storage then clears their files.
        migrations.RunSQL("TRUNCATE accounts_user CASCADE", migrations.RunSQL.noop),
        migrations.RemoveField(
            model_name="user",
            name="is_email_verified",
        ),
        migrations.AddField(
            model_name="user",
            name="google_sub",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.RunPython(create_system_user, migrations.RunPython.noop),
    ]
