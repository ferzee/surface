from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0002_alter_buddyrequest_status')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.TextField(blank=True, default=''),
        ),
    ]
