from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0003_user_avatar')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='header_color',
            field=models.CharField(default='ocean', max_length=20),
        ),
    ]
