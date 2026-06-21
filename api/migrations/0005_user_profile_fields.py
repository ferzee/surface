from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0004_user_header_color')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='certifications',
            field=models.TextField(blank=True, default='[]'),
        ),
        migrations.AddField(
            model_name='user',
            name='diving_since',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='dive_school',
            field=models.TextField(blank=True, default=''),
        ),
    ]
