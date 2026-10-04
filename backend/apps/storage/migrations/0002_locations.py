from django.db import migrations, models

EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/avif": "avif",
    "application/pdf": "pdf",
}


def to_locations(apps, schema_editor):
    """Files stored so far stay where they are, on the server's disk."""
    StoredObject = apps.get_model("storage", "StoredObject")
    for obj in StoredObject.objects.all():
        obj.location = f"local-{obj.visibility}"
        obj.key = f"{obj.id.hex[:2]}/{obj.id.hex}.{EXTENSIONS[obj.content_type]}"
        # max_size becomes the size; keep the real one where the file arrived.
        obj.max_size = obj.size or obj.max_size
        obj.save(update_fields=("location", "key", "max_size"))


class Migration(migrations.Migration):

    dependencies = [
        ("storage", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="storedobject",
            name="scope",
            field=models.CharField(blank=True, help_text="The app it belongs to.", max_length=50),
        ),
        migrations.AddField(
            model_name="storedobject",
            name="location",
            field=models.CharField(
                default="",
                help_text="Where the file lives: a name in STORAGE_LOCATIONS.",
                max_length=50,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="storedobject",
            name="key",
            field=models.CharField(
                default="", help_text="Its name in the location.", max_length=255
            ),
            preserve_default=False,
        ),
        migrations.RunPython(to_locations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="storedobject",
            name="key",
            field=models.CharField(
                help_text="Its name in the location.", max_length=255, unique=True
            ),
        ),
        migrations.RemoveField(model_name="storedobject", name="visibility"),
        migrations.RemoveField(model_name="storedobject", name="size"),
        migrations.RenameField(model_name="storedobject", old_name="max_size", new_name="size"),
        migrations.AlterField(
            model_name="storedobject",
            name="size",
            field=models.PositiveBigIntegerField(help_text="The exact bytes the upload must be."),
        ),
        migrations.AlterField(
            model_name="storedobject",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Waiting for the upload"),
                    ("checking", "Uploaded, being checked"),
                    ("ready", "Uploaded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
