# Generated migration for test suite request features

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0008_add_script_management'),
    ]

    operations = [
        migrations.AddField(
            model_name='testsuiterequest',
            name='wait_time',
            field=models.IntegerField(default=0, help_text='执行前等待时间', verbose_name='等待时间（秒）'),
        ),
        migrations.AddField(
            model_name='testsuiterequest',
            name='user_inputs',
            field=models.JSONField(default=dict, help_text='运行时需要用户输入的参数', verbose_name='用户输入参数'),
        ),
    ]
